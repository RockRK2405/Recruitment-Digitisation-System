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
        whereClause += ` AND (c.name ILIKE $${paramIndex} OR c.email ILIKE $${paramIndex} OR r.skills_list ILIKE $${paramIndex} OR r.primary_domain ILIKE $${paramIndex})`
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

  return router
}
