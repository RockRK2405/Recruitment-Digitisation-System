import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'

const router = Router()

export function createMatchingRouter(pool: Pool) {
  router.get('/rank/:jobId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT m.*, c.name as candidate_name, c.email, c.location, c.status,
                c.primary_domain, r.experience_years, r.skills_list
         FROM match_results m
         JOIN candidates c ON c.id = m.candidate_id
         LEFT JOIN resumes r ON r.candidate_id = c.id
         WHERE m.job_id = $1
         ORDER BY m.overall_score DESC
         LIMIT 50`,
        [req.params.jobId]
      )

      res.json(result.rows.map((row, i) => ({
        id: row.id,
        candidateId: row.candidate_id,
        jobId: row.job_id,
        ranking: i + 1,
        overallScore: Math.round(row.overall_score),
        vectorScore: Math.round(row.vector_score),
        skillScore: Math.round(row.skill_score),
        certificationScore: Math.round(row.agent_score || row.skill_score * 0.3),
        matchExplanation: row.match_explanation,
        candidate: {
          id: row.candidate_id,
          name: row.candidate_name,
          email: row.email,
          location: row.location,
          status: row.status,
          primaryDomain: row.primary_domain || row.r_primary_domain,
          experienceYears: row.experience_years,
          skills: row.skills_list || [],
        },
      })))
    } catch (error) {
      console.error('Rank candidates error:', error)
      res.status(500).json({ message: 'Failed to rank candidates', code: 'RANK_FAILED' })
    }
  })

  router.get('/score', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { candidateId, jobId } = req.query
      const result = await pool.query(
        'SELECT * FROM match_results WHERE candidate_id = $1 AND job_id = $2',
        [candidateId, jobId]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Match not found', code: 'NOT_FOUND' })
      }
      const row = result.rows[0]
      res.json({
        id: row.id,
        candidateId: row.candidate_id,
        jobId: row.job_id,
        overallScore: Math.round(row.overall_score),
        vectorScore: Math.round(row.vector_score),
        skillScore: Math.round(row.skill_score),
        certificationScore: Math.round(row.agent_score || row.skill_score * 0.3),
        matchExplanation: row.match_explanation,
      })
    } catch (error) {
      console.error('Get score error:', error)
      res.status(500).json({ message: 'Failed to get score', code: 'SCORE_FAILED' })
    }
  })

  router.get('/recommendations/:candidateId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT m.*, j.title as job_title, j.location, j.required_skills
         FROM match_results m
         JOIN job_descriptions j ON j.id = m.job_id
         WHERE m.candidate_id = $1 AND m.overall_score >= 60
         ORDER BY m.overall_score DESC
         LIMIT 10`,
        [req.params.candidateId]
      )
      res.json(result.rows.map((row) => ({
        jobId: row.job_id,
        jobTitle: row.job_title,
        location: row.location,
        requiredSkills: row.required_skills,
        overallScore: Math.round(row.overall_score),
      })))
    } catch (error) {
      console.error('Recommendations error:', error)
      res.status(500).json({ message: 'Failed to get recommendations', code: 'RECOMMEND_FAILED' })
    }
  })

  router.post('/semantic', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { query } = req.body
      const result = await pool.query(
        `SELECT c.*, r.experience_years, r.skills_list, r.primary_domain
         FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id
         WHERE r.raw_text ILIKE $1 OR c.name ILIKE $1 OR r.skills_list ILIKE $1 OR r.primary_domain ILIKE $1
         LIMIT 20`,
        [`%${query}%`]
      )
      res.json(result.rows.map((row) => ({
        id: row.id,
        name: row.name,
        experienceYears: row.experience_years,
        skills: row.skills_list || [],
        primaryDomain: row.primary_domain,
        status: row.status,
      })))
    } catch (error) {
      console.error('Semantic search error:', error)
      res.status(500).json({ message: 'Search failed', code: 'SEARCH_FAILED' })
    }
  })

  router.get('/explain/:candidateId/:jobId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT m.*, c.name as candidate_name, j.title as job_title
         FROM match_results m
         JOIN candidates c ON c.id = m.candidate_id
         JOIN job_descriptions j ON j.id = m.job_id
         WHERE m.candidate_id = $1 AND m.job_id = $2`,
        [req.params.candidateId, req.params.jobId]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Match not found', code: 'NOT_FOUND' })
      }
      const row = result.rows[0]
      res.json({
        candidateName: row.candidate_name,
        jobTitle: row.job_title,
        breakdown: {
          vectorSimilarity: Math.round(row.vector_score),
          skillsMatch: Math.round(row.skill_score),
          certifications: Math.round(row.agent_score || row.skill_score * 0.3),
          overall: Math.round(row.overall_score),
        },
        explanation: row.match_explanation,
      })
    } catch (error) {
      console.error('Explain error:', error)
      res.status(500).json({ message: 'Failed to get explanation', code: 'EXPLAIN_FAILED' })
    }
  })

  return router
}
