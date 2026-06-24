import { Router, Response } from 'express'
import multer from 'multer'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'
import { config } from '../config/index.js'
import path from 'path'
import { v4 as uuidv4 } from 'uuid'
import fs from 'fs'

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
})

export function createDocumentsRouter(pool: Pool) {
  router.post('/upload-batch', authenticate, upload.array('files', 50), async (req: AuthRequest, res: Response) => {
    try {
      const files = req.files as Express.Multer.File[]
      const candidateId = req.body.candidateId

      if (!files || files.length === 0) {
        return res.status(400).json({ message: 'No files provided', code: 'NO_FILES' })
      }

      const batchResult = await pool.query(
        `INSERT INTO document_upload_batches (candidate_id, total_documents, status)
         VALUES ($1, $2, 'uploaded')
         RETURNING *`,
        [candidateId || null, files.length]
      )

      const documents = []
      for (const file of files) {
        const docResult = await pool.query(
          `INSERT INTO uploaded_documents (filename, filepath, mime_type, status, doc_type, batch_id, candidate_id)
           VALUES ($1, $2, $3, 'uploaded', 'document', $4, $5)
           RETURNING *`,
          [file.originalname, file.path, file.mimetype, batchResult.rows[0].id, candidateId || null]
        )
        documents.push(docResult.rows[0])
      }

      res.status(201).json({
        batchId: batchResult.rows[0].id,
        totalDocuments: documents.length,
        documents: documents.map((d) => ({ id: d.id, filename: d.filename })),
      })
    } catch (error) {
      console.error('Batch upload error:', error)
      res.status(500).json({ message: 'Batch upload failed', code: 'BATCH_UPLOAD_FAILED' })
    }
  })

  router.post('/classify', authenticate, upload.single('file'), async (req: AuthRequest, res: Response) => {
    try {
      const file = req.file
      if (!file) {
        return res.status(400).json({ message: 'No file provided', code: 'NO_FILE' })
      }

      const ext = path.extname(file.originalname).toLowerCase()
      let docType = 'unknown'

      if (ext === '.pdf') docType = 'resume'
      else if (['.jpg', '.jpeg', '.png', '.tiff'].includes(ext)) docType = 'certificate'

      res.json({
        filename: file.originalname,
        docType,
        confidence: 0.85,
      })
    } catch (error) {
      console.error('Classify error:', error)
      res.status(500).json({ message: 'Classification failed', code: 'CLASSIFY_FAILED' })
    }
  })

  router.get('/candidate/:candidateId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT * FROM uploaded_documents WHERE candidate_id = $1 OR id IN (SELECT uploaded_doc_id FROM resumes WHERE candidate_id = $1)
         ORDER BY created_at DESC`,
        [req.params.candidateId]
      )
      res.json(result.rows.map((row) => ({
        id: row.id,
        filename: row.filename,
        docType: row.doc_type,
        ocrConfidence: row.ocr_confidence,
        status: row.status,
        createdAt: row.created_at,
      })))
    } catch (error) {
      console.error('List documents error:', error)
      res.status(500).json({ message: 'Failed to fetch documents', code: 'DOCUMENTS_FAILED' })
    }
  })

  return router
}
