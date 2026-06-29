import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'
import axios from 'axios'
import { config } from '../config/index.js'
import { parseJobDescription, persistParsedJD } from '../lib/jd-parser.js'
import { runMatchingForJob } from '../lib/matching-engine.js'

const router = Router()
const aiClient = axios.create({ baseURL: config.aiService.url, timeout: 60000 })

export function createJobsRouter(pool: Pool) {
  router.get('/', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const status = req.query.status as string
      let query = 'SELECT j.*, (SELECT COUNT(*) FROM match_results m WHERE m.job_id = j.id) as candidate_count FROM job_descriptions j'
      const params: string[] = []

      if (status && status !== 'all') {
        query += ' WHERE j.status = $1'
        params.push(status)
      }

      query += ' ORDER BY j.created_at DESC'

      const result = await pool.query(query, params)
      res.json(result.rows.map((row) => ({
        id: row.id,
        title: row.title,
        description: row.description,
        requiredSkills: row.required_skills || [],
        requiredCertifications: row.required_certifications || [],
        location: row.location,
        experienceYearsRequired: row.experience_years_required,
        educationRequired: row.education_required,
        industry: row.industry,
        status: row.status,
        candidateCount: parseInt(row.candidate_count),
        createdAt: row.created_at,
        updatedAt: row.updated_at,
      })))
    } catch (error) {
      console.error('List jobs error:', error)
      res.status(500).json({ message: 'Failed to fetch jobs', code: 'FETCH_FAILED' })
    }
  })

  router.get('/:id', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        'SELECT * FROM job_descriptions WHERE id = $1',
        [req.params.id]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Job not found', code: 'NOT_FOUND' })
      }
      const row = result.rows[0]
      res.json({
        id: row.id,
        title: row.title,
        description: row.description,
        requiredSkills: row.required_skills || [],
        requiredCertifications: row.required_certifications || [],
        location: row.location,
        experienceYearsRequired: row.experience_years_required,
        educationRequired: row.education_required,
        industry: row.industry,
        status: row.status,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
      })
    } catch (error) {
      console.error('Get job error:', error)
      res.status(500).json({ message: 'Failed to fetch job', code: 'FETCH_FAILED' })
    }
  })

  router.post('/', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { title, description, requiredSkills, requiredCertifications, location, experienceYearsRequired, educationRequired, industry } = req.body
      const result = await pool.query(
        `INSERT INTO job_descriptions (title, description, required_skills, required_certifications, location, experience_years_required, education_required, industry, status)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active')
         RETURNING *`,
        [title, description, requiredSkills || [], requiredCertifications || [], location, experienceYearsRequired, educationRequired, industry]
      )
      const row = result.rows[0]
      const jobResponse = {
        id: row.id,
        title: row.title,
        description: row.description,
        requiredSkills: row.required_skills || [],
        requiredCertifications: row.required_certifications || [],
        location: row.location,
        experienceYearsRequired: row.experience_years_required,
        educationRequired: row.education_required,
        industry: row.industry,
        status: row.status,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
      }
      res.status(201).json(jobResponse)

      // Background: LLM-parse the JD, then run two-stage matching against all candidates
      ;(async () => {
        try {
          if (description) {
            const parsed = await parseJobDescription(title, description)
            await persistParsedJD(pool, row.id, parsed)
            console.log(`✓ JD parsed for job ${row.id}: ${parsed.mandatory_skills.length} mandatory skills`)
          }
          await runMatchingForJob(pool, row.id)
        } catch (e) {
          console.warn(`Background JD parse/match failed for ${row.id}:`, e instanceof Error ? e.message : e)
        }
      })()
    } catch (error) {
      console.error('Create job error:', error)
      res.status(500).json({ message: 'Failed to create job', code: 'CREATE_FAILED' })
    }
  })

  // Manual JD re-parse + re-match trigger
  router.post('/:id/parse', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { rows } = await pool.query(`SELECT title, description FROM job_descriptions WHERE id = $1`, [req.params.id])
      if (rows.length === 0) return res.status(404).json({ message: 'Job not found', code: 'NOT_FOUND' })
      const { title, description } = rows[0]
      if (!description) return res.status(400).json({ message: 'No description to parse', code: 'NO_DESCRIPTION' })

      const parsed = await parseJobDescription(title, description)
      await persistParsedJD(pool, req.params.id, parsed)

      res.json({ ok: true, parsed })

      // Re-run matching in background
      runMatchingForJob(pool, req.params.id).catch((e) => {
        console.warn(`Re-match after parse failed for ${req.params.id}:`, e instanceof Error ? e.message : e)
      })
    } catch (error) {
      console.error('Parse JD error:', error)
      res.status(500).json({ message: 'Failed to parse JD', code: 'PARSE_FAILED', detail: error instanceof Error ? error.message : String(error) })
    }
  })

  router.put('/:id', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { title, description, requiredSkills, requiredCertifications, location, experienceYearsRequired, educationRequired, industry, status } = req.body
      const result = await pool.query(
        `UPDATE job_descriptions SET title = $1, description = $2, required_skills = $3, required_certifications = $4,
         location = $5, experience_years_required = $6, education_required = $7, industry = $8, status = $9, updated_at = NOW()
         WHERE id = $10 RETURNING *`,
        [title, description, requiredSkills, requiredCertifications, location, experienceYearsRequired, educationRequired, industry, status, req.params.id]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Job not found', code: 'NOT_FOUND' })
      }
      res.json(result.rows[0])
    } catch (error) {
      console.error('Update job error:', error)
      res.status(500).json({ message: 'Failed to update job', code: 'UPDATE_FAILED' })
    }
  })

  router.delete('/:id', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      await pool.query('DELETE FROM match_results WHERE job_id = $1', [req.params.id])
      await pool.query('DELETE FROM job_descriptions WHERE id = $1', [req.params.id])
      res.json({ message: 'Job deleted' })
    } catch (error) {
      console.error('Delete job error:', error)
      res.status(500).json({ message: 'Failed to delete job', code: 'DELETE_FAILED' })
    }
  })

  return router
}
