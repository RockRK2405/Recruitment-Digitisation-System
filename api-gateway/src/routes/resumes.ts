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
import { completeLLM } from '../lib/llm.js'
import { runMatchingForJob } from '../lib/matching-engine.js'

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

interface ParsedProfile {
  name: string
  email: string | null
  phone: string
  location: string
  address: string
  experience_years: number
  primary_domain: string
  skills: string[]
  equipment_handled: string[]
  languages: string[]
  education: string
  availability: string
  certifications: Array<{
    name: string
    issuer: string
    issue_date: string | null
    expiry_date: string | null
    registration_number: string
    is_safety_critical: boolean
    confidence: number
  }>
}

interface ParseResponse {
  ok: boolean
  reason?: string
  ocr_confidence: number
  ocr_engine_used: string
  total_pages?: number
  raw_text: string
  parsed: ParsedProfile
}

async function callParseEndpoint(filePath: string, originalName: string): Promise<ParseResponse | null> {
  try {
    const form = new FormData()
    form.append('file', fs.createReadStream(filePath), { filename: originalName })
    const res = await aiClient.post<ParseResponse>('/api/resumes/parse', form, { headers: form.getHeaders() })
    return res.data
  } catch (err) {
    console.warn('Parse endpoint failed:', err instanceof Error ? err.message : err)
    return null
  }
}

async function persistParsedProfile(
  pool: Pool,
  candidateId: string,
  docId: string,
  result: ParseResponse,
) {
  const p = result.parsed
  // Update candidate with enriched fields. Don't overwrite name unless we got a real one.
  await pool.query(
    `UPDATE candidates SET
       name = COALESCE(NULLIF($1, ''), name),
       email = COALESCE($2, email),
       phone = COALESCE(NULLIF($3, ''), phone),
       location = COALESCE(NULLIF($4, ''), location),
       address = COALESCE(NULLIF($5, ''), address),
       primary_domain = COALESCE(NULLIF($6, ''), primary_domain),
       experience_years = $7,
       profile_completeness = $8,
       ai_summary = $9,
       updated_at = NOW()
     WHERE id = $10`,
    [
      p.name,
      p.email,
      p.phone,
      p.location,
      p.address,
      p.primary_domain,
      p.experience_years || 0,
      computeCompleteness(p),
      buildAiSummary(p),
      candidateId,
    ],
  )

  // Upsert resume row
  await pool.query(
    `INSERT INTO resumes (
       candidate_id, uploaded_doc_id, raw_text, experience_years,
       skills_list, primary_domain, equipment_handled, languages,
       education, availability, raw_parsed_json
     )
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
     ON CONFLICT (candidate_id) DO UPDATE SET
       uploaded_doc_id = EXCLUDED.uploaded_doc_id,
       raw_text = EXCLUDED.raw_text,
       experience_years = EXCLUDED.experience_years,
       skills_list = EXCLUDED.skills_list,
       primary_domain = EXCLUDED.primary_domain,
       equipment_handled = EXCLUDED.equipment_handled,
       languages = EXCLUDED.languages,
       education = EXCLUDED.education,
       availability = EXCLUDED.availability,
       raw_parsed_json = EXCLUDED.raw_parsed_json,
       updated_at = NOW()`,
    [
      candidateId,
      docId,
      result.raw_text?.slice(0, 100000) || '',
      p.experience_years || 0,
      p.skills,
      p.primary_domain || null,
      p.equipment_handled,
      p.languages,
      p.education || null,
      p.availability || null,
      JSON.stringify(p),
    ],
  )

  // Insert certifications (idempotent by name+candidate)
  for (const cert of p.certifications) {
    if (!cert.name) continue
    await pool.query(
      `INSERT INTO certifications (
         candidate_id, name, issuer, issue_date, expiry_date,
         registration_number, is_safety_critical, verification_status,
         confidence, source_document_id, raw_parsed_data
       )
       VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8, $9, $10)`,
      [
        candidateId,
        cert.name,
        cert.issuer || null,
        cert.issue_date,
        cert.expiry_date,
        cert.registration_number || null,
        cert.is_safety_critical,
        cert.confidence || 0,
        docId,
        JSON.stringify(cert),
      ],
    )
  }

  // Mark document completed
  await pool.query(
    `UPDATE uploaded_documents
     SET status = 'completed',
         ocr_text = $1,
         ocr_confidence = $2,
         ocr_engine_used = $3,
         total_pages = $4
     WHERE id = $5`,
    [
      result.raw_text?.slice(0, 100000) || '',
      result.ocr_confidence,
      result.ocr_engine_used,
      result.total_pages || 1,
      docId,
    ],
  )

  // LLM-generated narrative summary (fire-and-forget, replaces template)
  generateAndStoreSummary(pool, candidateId, p).catch((e) => {
    console.warn(`AI summary generation failed for ${candidateId}:`, e instanceof Error ? e.message : e)
  })

  // Re-rank this candidate against every active job (cheap pre-filter writes a
  // baseline row; LLM eval only kicks in if they make the shortlist)
  reEvaluateActiveJobs(pool).catch((e) => {
    console.warn(`Active-job re-eval failed:`, e instanceof Error ? e.message : e)
  })
}

async function reEvaluateActiveJobs(pool: Pool): Promise<void> {
  const { rows } = await pool.query(`SELECT id FROM job_descriptions WHERE status = 'active'`)
  for (const j of rows) {
    try {
      await runMatchingForJob(pool, j.id, { prefilterTopN: 30, llmTopN: 0 })
    } catch (e) {
      console.warn(`Re-eval for job ${j.id} failed:`, e instanceof Error ? e.message : e)
    }
  }
}

async function generateAndStoreSummary(pool: Pool, candidateId: string, p: ParsedProfile): Promise<void> {
  const prompt = `You are an HR analyst at an industrial recruitment firm. Write a concise 3-4 sentence professional summary of this candidate, suitable for a recruiter dashboard. Cover their experience, domain expertise, key skills, notable certifications, and any standout strengths. Be factual; do not invent details.

Candidate profile:
- Name: ${p.name || 'Unknown'}
- Experience: ${p.experience_years || 0} years
- Domain: ${p.primary_domain || 'unspecified'}
- Location: ${p.location || 'unspecified'}
- Skills: ${p.skills.join(', ') || 'none listed'}
- Equipment handled: ${p.equipment_handled.join(', ') || 'none listed'}
- Languages: ${p.languages.join(', ') || 'unspecified'}
- Education: ${p.education || 'unspecified'}
- Certifications: ${p.certifications.map((c) => c.name).join(', ') || 'none'}

Write the summary directly, no preamble.`

  const summary = await completeLLM(prompt)
  if (summary && summary.length > 20 && !summary.toLowerCase().startsWith("i'm unable")) {
    await pool.query(
      `UPDATE candidates SET ai_summary = $1, updated_at = NOW() WHERE id = $2`,
      [summary.slice(0, 4000), candidateId],
    )
  }
}

function computeCompleteness(p: ParsedProfile): number {
  const fields = [
    p.name, p.email, p.phone, p.location, p.education,
    p.skills.length > 0, p.certifications.length > 0,
    p.experience_years > 0, p.primary_domain,
  ]
  const score = fields.filter(Boolean).length / fields.length
  return Math.round(score * 100)
}

function buildAiSummary(p: ParsedProfile): string {
  const parts: string[] = []
  if (p.name) parts.push(p.name)
  if (p.experience_years > 0) parts.push(`has ${p.experience_years} years of experience`)
  if (p.primary_domain) parts.push(`in ${p.primary_domain}`)
  if (p.skills.length > 0) parts.push(`with expertise in ${p.skills.slice(0, 5).join(', ')}`)
  if (p.certifications.length > 0) {
    const certNames = p.certifications.slice(0, 3).map((c) => c.name).join(', ')
    parts.push(`holds certifications: ${certNames}`)
  }
  if (p.education) parts.push(`Education: ${p.education}`)
  return parts.length > 0 ? parts.join('. ') + '.' : ''
}

export function createResumesRouter(pool: Pool) {
  // Derive a friendly candidate name from a filename (strip ext, normalize separators)
  const nameFromFilename = (filename: string): string => {
    const base = filename.replace(/\.[^.]+$/, '')
    return base
      .replace(/[_\-.]+/g, ' ')
      .replace(/\b(cv|resume|profile)\b/gi, '')
      .replace(/\s+/g, ' ')
      .trim() || 'Unnamed Candidate'
  }

  router.post('/upload', authenticate, upload.single('file'), async (req: AuthRequest, res: Response) => {
    try {
      const file = req.file
      if (!file) {
        return res.status(400).json({ message: 'No file provided', code: 'NO_FILE' })
      }

      // Create a candidate row immediately so the user sees it on /candidates
      const candidateResult = await pool.query(
        `INSERT INTO candidates (name, status, source, primary_domain, profile_completeness)
         VALUES ($1, 'new', 'upload', 'unknown', 10)
         RETURNING id`,
        [nameFromFilename(file.originalname)]
      )
      const candidateId = candidateResult.rows[0].id

      // Record upload, linked to the candidate
      const docResult = await pool.query(
        `INSERT INTO uploaded_documents (candidate_id, filename, filepath, mime_type, status, doc_type)
         VALUES ($1, $2, $3, $4, 'uploaded', 'resume')
         RETURNING *`,
        [candidateId, file.originalname, file.path, file.mimetype]
      )
      const docId = docResult.rows[0].id

      // Return success to the user immediately — AI processing runs in background
      res.status(201).json({
        id: docId,
        candidateId,
        filename: file.originalname,
        status: 'uploaded',
        message: 'Resume uploaded. AI parsing will enrich the profile in the background.',
      })

      // Background OCR + parse + persist
      callParseEndpoint(file.path, file.originalname)
        .then(async (result) => {
          if (!result || !result.ok) {
            await pool.query(
              `UPDATE uploaded_documents SET status = 'failed' WHERE id = $1`,
              [docId],
            )
            console.warn(`AI parse failed for ${docId}: ${result?.reason || 'no response'}`)
            return
          }
          try {
            await persistParsedProfile(pool, candidateId, docId, result)
            console.log(`✓ Enriched candidate ${candidateId} from ${file.originalname}`)
          } catch (e) {
            console.error(`Persist failed for ${docId}:`, e instanceof Error ? e.message : e)
            await pool.query(
              `UPDATE uploaded_documents SET status = 'failed' WHERE id = $1`,
              [docId],
            )
          }
        })
        .catch((err) => {
          console.warn(`Background AI processing for ${docId} failed:`, err instanceof Error ? err.message : err)
        })
    } catch (error) {
      console.error('Upload resume error:', error)
      res.status(500).json({ message: 'Upload failed', code: 'UPLOAD_FAILED', detail: error instanceof Error ? error.message : String(error) })
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
          const candidateResult = await pool.query(
            `INSERT INTO candidates (name, status, source, primary_domain, profile_completeness)
             VALUES ($1, 'new', 'upload', 'unknown', 10)
             RETURNING id`,
            [nameFromFilename(file.originalname)]
          )
          const candidateId = candidateResult.rows[0].id

          const docResult = await pool.query(
            `INSERT INTO uploaded_documents (candidate_id, filename, filepath, mime_type, status, doc_type, batch_id)
             VALUES ($1, $2, $3, $4, 'uploaded', 'resume', $5)
             RETURNING *`,
            [candidateId, file.originalname, file.path, file.mimetype, batchResult.rows[0].id]
          )
          const docId = docResult.rows[0].id

          // Background OCR + parse + persist
          callParseEndpoint(file.path, file.originalname)
            .then(async (result) => {
              if (!result || !result.ok) {
                await pool.query(
                  `UPDATE uploaded_documents SET status = 'failed' WHERE id = $1`,
                  [docId],
                )
                return
              }
              try {
                await persistParsedProfile(pool, candidateId, docId, result)
              } catch (e) {
                console.error(`Bulk persist failed for ${docId}:`, e instanceof Error ? e.message : e)
              }
            })
            .catch((err) => {
              console.warn(`Background AI processing for ${docId} failed:`, err instanceof Error ? err.message : err)
            })

          results.push({
            filename: file.originalname,
            status: 'uploaded',
            documentId: docId,
            candidateId,
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
      const result = await pool.query(
        `SELECT c.id, c.name, c.email, c.phone, c.location, c.address, c.status,
                c.low_literacy_flag, c.created_at, c.updated_at, c.experience_years,
                c.primary_domain, c.profile_completeness, c.ai_summary,
                r.skills_list, r.equipment_handled, r.languages, r.education,
                r.availability, r.raw_text
         FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id
         WHERE c.id = $1`,
        [req.params.candidateId],
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Candidate not found', code: 'NOT_FOUND' })
      }
      const row = result.rows[0]
      const toArray = (v: unknown): string[] => Array.isArray(v) ? v.map(String) : (typeof v === 'string' && v ? v.split(',').map((s) => s.trim()).filter(Boolean) : [])

      const certs = await pool.query(
        `SELECT id, name, issuer, issue_date, expiry_date, registration_number,
                is_safety_critical, verification_status, confidence
         FROM certifications WHERE candidate_id = $1
         ORDER BY issue_date DESC NULLS LAST`,
        [req.params.candidateId],
      )

      res.json({
        id: row.id,
        name: row.name,
        email: row.email,
        phone: row.phone,
        location: row.location,
        address: row.address,
        status: row.status,
        primaryDomain: row.primary_domain,
        experienceYears: row.experience_years || 0,
        profileCompleteness: row.profile_completeness || 0,
        aiSummary: row.ai_summary,
        education: row.education,
        low_literacy_flag: row.low_literacy_flag,
        created_at: row.created_at,
        updated_at: row.updated_at,
        resume: {
          experience_years: row.experience_years || 0,
          skills: toArray(row.skills_list),
          skills_list: toArray(row.skills_list).join(', '),
          primary_domain: row.primary_domain,
          equipment_handled: toArray(row.equipment_handled),
          languages: toArray(row.languages),
          education: row.education,
          availability: row.availability,
          raw_text_preview: typeof row.raw_text === 'string' ? row.raw_text.slice(0, 500) : '',
        },
        certifications: certs.rows.map((c) => ({
          id: c.id,
          name: c.name,
          issuer: c.issuer,
          issueDate: c.issue_date,
          expiryDate: c.expiry_date,
          registrationNumber: c.registration_number,
          isSafetyCritical: c.is_safety_critical,
          status: c.verification_status,
          confidence: c.confidence,
        })),
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
