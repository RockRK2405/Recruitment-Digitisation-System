import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'

const router = Router()

export function createCandidatesRouter(pool: Pool) {
  router.get('/', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const page = parseInt(req.query.page as string) || 1
      const pageSize = parseInt(req.query.page_size as string) || 20
      const offset = (page - 1) * pageSize
      const search = req.query.search as string
      const status = req.query.status as string
      const domain = req.query.domain as string

      let whereClause = 'WHERE 1=1'
      const params: string[] = []
      let paramIndex = 1

      if (search) {
        // skills_list is TEXT[]; flatten to text for LIKE search
        whereClause += ` AND (c.name ILIKE $${paramIndex} OR c.email ILIKE $${paramIndex} OR array_to_string(r.skills_list, ',') ILIKE $${paramIndex} OR r.primary_domain ILIKE $${paramIndex})`
        params.push(`%${search}%`)
        paramIndex++
      }
      if (status) {
        whereClause += ` AND c.status = $${paramIndex}`
        params.push(status)
        paramIndex++
      }
      if (domain) {
        whereClause += ` AND r.primary_domain = $${paramIndex}`
        params.push(domain)
        paramIndex++
      }

      const countResult = await pool.query(
        `SELECT COUNT(*) FROM candidates c LEFT JOIN resumes r ON r.candidate_id = c.id ${whereClause}`,
        params
      )
      const total = parseInt(countResult.rows[0].count)

      const result = await pool.query(
        `SELECT c.*, r.experience_years, r.skills_list, r.primary_domain, r.education
         FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id
         ${whereClause}
         ORDER BY c.created_at DESC
         LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`,
        [...params, pageSize, offset]
      )

      res.json({
        data: result.rows.map((row) => ({
          id: row.id,
          name: row.name,
          email: row.email,
          phone: row.phone,
          location: row.location,
          status: row.status,
          experienceYears: row.experience_years,
          skills: row.skills_list || [],
          primaryDomain: row.primary_domain,
          education: row.education,
          profileCompleteness: row.profile_completeness,
          createdAt: row.created_at,
          updatedAt: row.updated_at,
        })),
        total,
        page,
        pageSize,
        totalPages: Math.ceil(total / pageSize),
      })
    } catch (error) {
      console.error('List candidates error:', error)
      res.status(500).json({ message: 'Failed to fetch candidates', code: 'FETCH_FAILED' })
    }
  })

  router.get('/:id', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT c.*, r.experience_years, r.skills_list, r.primary_domain, r.education,
                r.raw_text, r.raw_parsed_json, r.industrial_details_json,
                r.languages, r.availability, r.notice_period, r.expected_salary
         FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id
         WHERE c.id = $1`,
        [req.params.id]
      )

      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Candidate not found', code: 'NOT_FOUND' })
      }

      const row = result.rows[0]

      const certResult = await pool.query(
        'SELECT * FROM certifications WHERE candidate_id = $1 ORDER BY issue_date DESC',
        [req.params.id]
      )

      const docResult = await pool.query(
        "SELECT * FROM uploaded_documents WHERE candidate_id = $1 OR id IN (SELECT uploaded_doc_id FROM resumes WHERE candidate_id = $1)",
        [req.params.id]
      )

      res.json({
        id: row.id,
        name: row.name,
        email: row.email,
        phone: row.phone,
        location: row.location,
        status: row.status,
        experienceYears: row.experience_years,
        skills: row.skills_list || [],
        primaryDomain: row.primary_domain,
        education: row.education,
        profileCompleteness: row.profile_completeness,
        aiSummary: row.ai_summary,
        rawText: row.raw_text,
        languages: row.languages,
        availability: row.availability,
        noticePeriod: row.notice_period,
        expectedSalary: row.expected_salary,
        certifications: certResult.rows.map((c) => ({
          id: c.id,
          name: c.name,
          issuer: c.issuer,
          issueDate: c.issue_date,
          expiryDate: c.expiry_date,
          registrationNumber: c.registration_number,
          isSafetyCritical: c.is_safety_critical,
          verificationStatus: c.verification_status,
        })),
        documents: docResult.rows.map((d) => ({
          id: d.id,
          filename: d.filename,
          docType: d.doc_type,
          ocrConfidence: d.ocr_confidence,
          status: d.status,
        })),
        createdAt: row.created_at,
        updatedAt: row.updated_at,
      })
    } catch (error) {
      console.error('Get candidate error:', error)
      res.status(500).json({ message: 'Failed to fetch candidate', code: 'FETCH_FAILED' })
    }
  })

  router.get('/:id/timeline', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT al.id, al.agent_name, al.message, al.timestamp
         FROM agent_logs al
         WHERE al.state_snapshot->>'candidate_id' = $1
         ORDER BY al.timestamp DESC
         LIMIT 50`,
        [req.params.id]
      )

      res.json(result.rows.map((row) => ({
        id: row.id,
        agentName: row.agent_name,
        message: row.message,
        timestamp: row.timestamp,
      })))
    } catch (error) {
      console.error('Get timeline error:', error)
      res.status(500).json({ message: 'Failed to fetch timeline', code: 'FETCH_FAILED' })
    }
  })

  router.patch('/:id/status', authenticate, async (req: AuthRequest, res: Response) => {
    const VALID_STATUSES = ['new', 'screening', 'shortlisted', 'interview', 'offered', 'hired', 'rejected']
    try {
      const { status } = req.body
      if (!status || !VALID_STATUSES.includes(status)) {
        return res.status(400).json({
          message: `Invalid status. Must be one of: ${VALID_STATUSES.join(', ')}`,
          code: 'INVALID_STATUS',
        })
      }
      const result = await pool.query(
        'UPDATE candidates SET status = $1, updated_at = NOW() WHERE id = $2 RETURNING id, name, status',
        [status, req.params.id]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Candidate not found', code: 'NOT_FOUND' })
      }
      res.json({ id: result.rows[0].id, name: result.rows[0].name, status: result.rows[0].status })
    } catch (error) {
      console.error('Update candidate status error:', error)
      res.status(500).json({ message: 'Failed to update candidate status', code: 'UPDATE_FAILED' })
    }
  })

  router.get('/export/csv', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const status = req.query.status as string
      let query = `
        SELECT c.id, c.name, c.email, c.phone, c.location, c.status, c.created_at,
               r.experience_years, r.skills_list, r.primary_domain, r.education,
               r.availability, r.notice_period, r.expected_salary,
               (SELECT string_agg(cert.name, '; ') FROM certifications cert WHERE cert.candidate_id = c.id) as certifications
        FROM candidates c
        LEFT JOIN resumes r ON r.candidate_id = c.id
      `
      const params: string[] = []
      if (status && status !== 'all') {
        query += ' WHERE c.status = $1'
        params.push(status)
      }
      query += ' ORDER BY c.created_at DESC'

      const result = await pool.query(query, params)

      const escape = (v: unknown) => {
        if (v == null) return ''
        const s = String(v).replace(/"/g, '""')
        return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s}"` : s
      }

      const headers = ['ID', 'Name', 'Email', 'Phone', 'Location', 'Status', 'Created At',
        'Experience (yrs)', 'Skills', 'Domain', 'Education', 'Availability',
        'Notice Period', 'Expected Salary', 'Certifications']

      const rows = result.rows.map((r) => [
        r.id, r.name, r.email, r.phone, r.location, r.status, r.created_at,
        r.experience_years, r.skills_list, r.primary_domain, r.education,
        r.availability, r.notice_period, r.expected_salary, r.certifications,
      ].map(escape).join(','))

      const csv = [headers.join(','), ...rows].join('\n')

      res.setHeader('Content-Type', 'text/csv')
      res.setHeader('Content-Disposition', `attachment; filename="candidates-${Date.now()}.csv"`)
      res.send(csv)
    } catch (error) {
      console.error('Export CSV error:', error)
      res.status(500).json({ message: 'Failed to export candidates', code: 'EXPORT_FAILED' })
    }
  })

  // Delete a candidate (cascades to resume, certs, notes, match_results, docs)
  router.delete('/:id', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const r = await pool.query(`DELETE FROM candidates WHERE id = $1`, [req.params.id])
      if (r.rowCount === 0) return res.status(404).json({ message: 'Candidate not found', code: 'NOT_FOUND' })
      res.status(204).send()
    } catch (e) {
      console.error('Delete candidate error:', e)
      res.status(500).json({ message: 'Failed to delete candidate', code: 'DELETE_FAILED' })
    }
  })

  // ─── Notes CRUD ─────────────────────────────────────────────
  router.get('/:id/notes', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { rows } = await pool.query(
        `SELECT id, body, author, created_at, updated_at
         FROM candidate_notes WHERE candidate_id = $1
         ORDER BY created_at DESC`,
        [req.params.id],
      )
      res.json(rows.map((n) => ({
        id: n.id, body: n.body, author: n.author,
        createdAt: n.created_at, updatedAt: n.updated_at,
      })))
    } catch (e) {
      console.error('List notes error:', e)
      res.status(500).json({ message: 'Failed to list notes', code: 'NOTES_LIST_FAILED' })
    }
  })

  router.post('/:id/notes', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { body, author } = req.body
      if (!body || typeof body !== 'string' || !body.trim()) {
        return res.status(400).json({ message: 'Note body is required', code: 'EMPTY_NOTE' })
      }
      const { rows } = await pool.query(
        `INSERT INTO candidate_notes (candidate_id, body, author)
         VALUES ($1, $2, $3)
         RETURNING id, body, author, created_at, updated_at`,
        [req.params.id, body.trim(), author || 'recruiter'],
      )
      const n = rows[0]
      res.status(201).json({
        id: n.id, body: n.body, author: n.author,
        createdAt: n.created_at, updatedAt: n.updated_at,
      })
    } catch (e) {
      console.error('Create note error:', e)
      res.status(500).json({ message: 'Failed to create note', code: 'NOTE_CREATE_FAILED' })
    }
  })

  router.patch('/:id/notes/:noteId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { body } = req.body
      if (!body || typeof body !== 'string' || !body.trim()) {
        return res.status(400).json({ message: 'Note body is required', code: 'EMPTY_NOTE' })
      }
      const { rows } = await pool.query(
        `UPDATE candidate_notes SET body = $1, updated_at = NOW()
         WHERE id = $2 AND candidate_id = $3
         RETURNING id, body, author, created_at, updated_at`,
        [body.trim(), req.params.noteId, req.params.id],
      )
      if (rows.length === 0) return res.status(404).json({ message: 'Note not found', code: 'NOT_FOUND' })
      const n = rows[0]
      res.json({
        id: n.id, body: n.body, author: n.author,
        createdAt: n.created_at, updatedAt: n.updated_at,
      })
    } catch (e) {
      console.error('Update note error:', e)
      res.status(500).json({ message: 'Failed to update note', code: 'NOTE_UPDATE_FAILED' })
    }
  })

  router.delete('/:id/notes/:noteId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const r = await pool.query(
        `DELETE FROM candidate_notes WHERE id = $1 AND candidate_id = $2`,
        [req.params.noteId, req.params.id],
      )
      if (r.rowCount === 0) return res.status(404).json({ message: 'Note not found', code: 'NOT_FOUND' })
      res.status(204).send()
    } catch (e) {
      console.error('Delete note error:', e)
      res.status(500).json({ message: 'Failed to delete note', code: 'NOTE_DELETE_FAILED' })
    }
  })

  return router
}
