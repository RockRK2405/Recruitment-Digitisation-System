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
      // skills_list is a TEXT column with comma-separated values
      const result = await pool.query(
        `SELECT trim(skill) as name, COUNT(*) as count
         FROM resumes,
              unnest(string_to_array(skills_list, ',')) AS skill
         WHERE skills_list IS NOT NULL AND skills_list != ''
           AND trim(skill) != ''
         GROUP BY trim(skill)
         ORDER BY count DESC
         LIMIT 20`
      )
      res.json(result.rows.map((r) => ({ name: r.name, count: parseInt(r.count) })))
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
      // 'source' column may not exist; fall back gracefully
      const result = await pool.query(
        `SELECT COALESCE(source, 'Resume Upload') as source, COUNT(*) as count
         FROM candidates
         GROUP BY source
         ORDER BY count DESC`
      ).catch(() => pool.query(
        `SELECT 'Resume Upload' as source, COUNT(*) as count FROM candidates`
      ))
      res.json(result.rows.map((r) => ({ source: r.source, count: parseInt(r.count) })))
    } catch (error) {
      console.error('Sources analytics error:', error)
      res.status(500).json({ message: 'Failed to fetch sources', code: 'SOURCES_FAILED' })
    }
  })

  router.get('/velocity', authenticate, async (_req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT to_char(date_trunc('month', created_at), 'Mon YYYY') as month,
                COUNT(*) as applications,
                COUNT(*) FILTER (WHERE status = 'hired') as hires
         FROM candidates
         GROUP BY date_trunc('month', created_at)
         ORDER BY date_trunc('month', created_at) DESC
         LIMIT 12`
      )
      res.json(result.rows.map((r) => ({
        month: r.month,
        applications: parseInt(r.applications),
        hires: parseInt(r.hires),
      })))
    } catch (error) {
      console.error('Velocity analytics error:', error)
      res.status(500).json({ message: 'Failed to fetch velocity', code: 'VELOCITY_FAILED' })
    }
  })

  router.get('/departments', authenticate, async (_req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT COALESCE(r.primary_domain, 'Other') as department,
                COUNT(*) as candidates,
                COUNT(*) FILTER (WHERE c.status = 'hired') as hired
         FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id
         GROUP BY r.primary_domain
         ORDER BY candidates DESC
         LIMIT 10`
      )
      res.json(result.rows.map((r) => ({
        department: r.department,
        candidates: parseInt(r.candidates),
        hired: parseInt(r.hired),
      })))
    } catch (error) {
      console.error('Departments analytics error:', error)
      res.status(500).json({ message: 'Failed to fetch departments', code: 'DEPARTMENTS_FAILED' })
    }
  })

  return router
}
