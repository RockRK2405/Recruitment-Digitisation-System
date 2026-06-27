import { Router, Response } from 'express'
import multer from 'multer'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'
import { config } from '../config/index.js'
import path from 'path'
import { v4 as uuidv4 } from 'uuid'
import fs from 'fs'
import axios from 'axios'
import FormData from 'form-data'

const router = Router()
const uploadDir = path.join(process.cwd(), 'uploads')

if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true })
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname)
    cb(null, `${uuidv4()}${ext}`)
  },
})

const upload = multer({
  storage,
  limits: { fileSize: config.upload.maxFileSize },
  fileFilter: (_req, file, cb) => {
    if (config.upload.allowedMimeTypes.includes(file.mimetype)) {
      cb(null, true)
    } else {
      cb(new Error(`File type '${file.mimetype}' not supported`))
    }
  },
})

const aiClient = axios.create({
  baseURL: config.aiService.url,
  timeout: 300000, // 5 min for OCR+AI processing
})

async function forwardToAiPipeline(filePath: string, originalName: string): Promise<Record<string, unknown> | null> {
  try {
    const form = new FormData()
    form.append('file', fs.createReadStream(filePath), { filename: originalName })

    const res = await aiClient.post('/api/resumes/upload', form, {
      headers: form.getHeaders(),
    })
    return res.data
  } catch (err) {
    console.warn('AI pipeline forwarding failed (will store file only):', err instanceof Error ? err.message : err)
    return null
  }
}

export function createResumesRouter(pool: Pool) {
  router.post('/upload', authenticate, upload.single('file'), async (req: AuthRequest, res: Response) => {
    try {
      const file = req.file
      if (!file) {
        return res.status(400).json({ message: 'No file provided', code: 'NO_FILE' })
      }

      // Record upload in DB immediately
      const docResult = await pool.query(
        `INSERT INTO uploaded_documents (filename, filepath, mime_type, status, doc_type)
         VALUES ($1, $2, $3, 'processing', 'resume')
         RETURNING *`,
        [file.originalname, file.path, file.mimetype]
      )

      // Forward to Python AI service for OCR + parsing (async-friendly)
      const aiResult = await forwardToAiPipeline(file.path, file.originalname)

      // Update document status based on AI result
      if (aiResult) {
        await pool.query(
          `UPDATE uploaded_documents SET status = 'processed', ocr_confidence = $1 WHERE id = $2`,
          [aiResult.ocr_confidence ? (aiResult.ocr_confidence as number) / 100 : null, docResult.rows[0].id]
        )
      } else {
        await pool.query(
          `UPDATE uploaded_documents SET status = 'uploaded' WHERE id = $2`,
          [docResult.rows[0].id]
        )
      }

      res.status(201).json({
        id: docResult.rows[0].id,
        filename: file.originalname,
        status: aiResult ? 'processed' : 'uploaded',
        message: aiResult
          ? 'Resume processed successfully by AI pipeline.'
          : 'Resume uploaded. AI service unavailable — processing will resume when service is restarted.',
        ...(aiResult || {}),
      })
    } catch (error) {
      console.error('Upload resume error:', error)
      res.status(500).json({ message: 'Upload failed', code: 'UPLOAD_FAILED' })
    }
  })

  router.post('/bulk-upload', authenticate, upload.array('files', 50), async (req: AuthRequest, res: Response) => {
    try {
      const files = req.files as Express.Multer.File[]
      if (!files || files.length === 0) {
        return res.status(400).json({ message: 'No files provided', code: 'NO_FILES' })
      }

      const batchResult = await pool.query(
        `INSERT INTO document_upload_batches (total_documents, status)
         VALUES ($1, 'processing')
         RETURNING *`,
        [files.length]
      )

      const results = []
      for (const file of files) {
        try {
          const docResult = await pool.query(
            `INSERT INTO uploaded_documents (filename, filepath, mime_type, status, doc_type, batch_id)
             VALUES ($1, $2, $3, 'processing', 'resume', $4)
             RETURNING *`,
            [file.originalname, file.path, file.mimetype, batchResult.rows[0].id]
          )

          const aiResult = await forwardToAiPipeline(file.path, file.originalname)

          if (aiResult) {
            await pool.query(
              `UPDATE uploaded_documents SET status = 'processed', ocr_confidence = $1 WHERE id = $2`,
              [aiResult.ocr_confidence ? (aiResult.ocr_confidence as number) / 100 : null, docResult.rows[0].id]
            )
          }

          results.push({
            filename: file.originalname,
            status: aiResult ? 'processed' : 'uploaded',
            documentId: docResult.rows[0].id,
            candidateId: aiResult?.candidate_id || null,
            candidateName: (aiResult?.parsed_profile as Record<string, unknown>)?.name || null,
          })
        } catch (fileErr) {
          results.push({
            filename: file.originalname,
            status: 'failed',
            error: fileErr instanceof Error ? fileErr.message : 'Processing failed',
          })
        }
      }

      await pool.query(
        `UPDATE document_upload_batches SET status = 'completed' WHERE id = $1`,
        [batchResult.rows[0].id]
      )

      res.status(201).json({
        batchId: batchResult.rows[0].id,
        totalFiles: files.length,
        processed: results.filter((r) => r.status === 'processed').length,
        failed: results.filter((r) => r.status === 'failed').length,
        results,
      })
    } catch (error) {
      console.error('Bulk upload error:', error)
      res.status(500).json({ message: 'Bulk upload failed', code: 'BULK_UPLOAD_FAILED' })
    }
  })

  router.get('/profile/:candidateId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      // Try Python AI service first for richer data
      try {
        const aiRes = await aiClient.get(`/api/resumes/profile/${req.params.candidateId}`)
        return res.json(aiRes.data)
      } catch {
        // Fall back to direct DB query
      }

      const result = await pool.query(
        `SELECT c.id, c.name, c.email, c.phone, c.location, c.status, c.low_literacy_flag, c.created_at,
                r.experience_years, r.skills_list, r.primary_domain, r.equipment_handled,
                r.languages, r.education, r.availability
         FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id
         WHERE c.id = $1`,
        [req.params.candidateId]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Candidate not found', code: 'NOT_FOUND' })
      }
      const row = result.rows[0]

      const certs = await pool.query(
        `SELECT name, issuer, verification_status as status FROM certifications WHERE candidate_id = $1`,
        [req.params.candidateId]
      )

      res.json({
        id: row.id,
        name: row.name,
        email: row.email,
        phone: row.phone,
        location: row.location,
        status: row.status,
        low_literacy_flag: row.low_literacy_flag,
        created_at: row.created_at,
        resume: {
          experience_years: row.experience_years,
          skills_list: row.skills_list,
          skills: row.skills_list ? row.skills_list.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
          primary_domain: row.primary_domain,
          equipment_handled: row.equipment_handled,
          languages: row.languages,
          education: row.education,
          availability: row.availability,
        },
        certifications: certs.rows,
      })
    } catch (error) {
      console.error('Get profile error:', error)
      res.status(500).json({ message: 'Failed to get profile', code: 'PROFILE_FAILED' })
    }
  })

  router.get('/document/:docId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        'SELECT * FROM uploaded_documents WHERE id = $1',
        [req.params.docId]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Document not found', code: 'NOT_FOUND' })
      }
      res.json(result.rows[0])
    } catch (error) {
      console.error('Get document error:', error)
      res.status(500).json({ message: 'Failed to get document', code: 'DOCUMENT_FAILED' })
    }
  })

  router.get('/ocr-status/:docId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT id, filename, status, ocr_confidence, mime_type, created_at FROM uploaded_documents WHERE id = $1`,
        [req.params.docId]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Document not found', code: 'NOT_FOUND' })
      }
      res.json(result.rows[0])
    } catch (error) {
      console.error('OCR status error:', error)
      res.status(500).json({ message: 'Failed to get OCR status', code: 'OCR_STATUS_FAILED' })
    }
  })

  return router
}
