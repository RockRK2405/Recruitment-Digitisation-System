import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'

const router = Router()

export function createAnalyticsRouter(pool: Pool) {
  router.get('/summary', authenticate, async (_req: AuthRequest, res: Response) => {
    try {
      const [candidates, jobs, matchResult] = await Promise.all([
        pool.query('SELECT COUNT(*) FROM candidates'),
        pool.query("SELECT COUNT(*) FROM job_descriptions WHERE status = 'active'"),
        pool.query('SELECT AVG(overall_score) as avg_score FROM match_results'),
      ])

      res.json({
        totalCandidates: parseInt(candidates.rows[0].count),
        activeJobs: parseInt(jobs.rows[0].count),
        averageMatchScore: Math.round(parseFloat(matchResult.rows[0]?.avg_score || '0')),
        totalMatches: 0,
      })
    } catch (error) {
      console.error('Analytics summary error:', error)
      res.status(500).json({ message: 'Failed to fetch analytics', code: 'ANALYTICS_FAILED' })
    }
  })

  router.get('/skills', authenticate, async (_req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT unnest(skills_list) as skill, COUNT(*) as count
         FROM resumes
         WHERE skills_list IS NOT NULL
         GROUP BY skill
         ORDER BY count DESC
         LIMIT 20`
      )
      res.json(result.rows)
    } catch (error) {
      console.error('Skills analytics error:', error)
      res.status(500).json({ message: 'Failed to fetch skills', code: 'SKILLS_FAILED' })
    }
  })

  router.get('/funnel', authenticate, async (_req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT status as stage, COUNT(*) as count
         FROM candidates
         GROUP BY status
         ORDER BY count DESC`
      )
      res.json(result.rows)
    } catch (error) {
      console.error('Funnel analytics error:', error)
      res.status(500).json({ message: 'Failed to fetch funnel', code: 'FUNNEL_FAILED' })
    }
  })

  router.get('/sources', authenticate, async (_req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT COALESCE(source, 'Unknown') as source, COUNT(*) as count
         FROM candidates
         GROUP BY source
         ORDER BY count DESC`
      )
      res.json(result.rows)
    } catch (error) {
      console.error('Sources analytics error:', error)
      res.status(500).json({ message: 'Failed to fetch sources', code: 'SOURCES_FAILED' })
    }
  })

  return router
}
