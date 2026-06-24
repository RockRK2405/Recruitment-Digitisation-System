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
  fileFilter: (_req, file, cb) => {
    if (config.upload.allowedMimeTypes.includes(file.mimetype)) {
      cb(null, true)
    } else {
      cb(new Error('File type not supported'))
    }
  },
})

export function createResumesRouter(pool: Pool) {
  router.post('/upload', authenticate, upload.single('file'), async (req: AuthRequest, res: Response) => {
    try {
      const file = req.file
      if (!file) {
        return res.status(400).json({ message: 'No file provided', code: 'NO_FILE' })
      }

      const docResult = await pool.query(
        `INSERT INTO uploaded_documents (filename, filepath, mime_type, status, doc_type)
         VALUES ($1, $2, $3, 'uploaded', 'resume')
         RETURNING *`,
        [file.originalname, file.path, file.mimetype]
      )

      res.status(201).json({
        id: docResult.rows[0].id,
        filename: docResult.rows[0].filename,
        status: 'uploaded',
        message: 'Resume uploaded successfully. AI pipeline will process it.',
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
         VALUES ($1, 'uploaded')
         RETURNING *`,
        [files.length]
      )

      const documents = []
      for (const file of files) {
        const docResult = await pool.query(
          `INSERT INTO uploaded_documents (filename, filepath, mime_type, status, doc_type, batch_id)
           VALUES ($1, $2, $3, 'uploaded', 'resume', $4)
           RETURNING *`,
          [file.originalname, file.path, file.mimetype, batchResult.rows[0].id]
        )
        documents.push(docResult.rows[0])
      }

      res.status(201).json({
        batchId: batchResult.rows[0].id,
        totalFiles: documents.length,
        documents: documents.map((d) => ({ id: d.id, filename: d.filename })),
        message: 'Bulk upload complete. AI pipeline processing started.',
      })
    } catch (error) {
      console.error('Bulk upload error:', error)
      res.status(500).json({ message: 'Bulk upload failed', code: 'BULK_UPLOAD_FAILED' })
    }
  })

  router.get('/profile/:candidateId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT c.*, r.* FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id
         WHERE c.id = $1`,
        [req.params.candidateId]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Candidate not found', code: 'NOT_FOUND' })
      }
      res.json(result.rows[0])
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

  return router
}
