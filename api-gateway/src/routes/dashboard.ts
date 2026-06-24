import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'

const router = Router()

export function createDashboardRouter(pool: Pool) {
  router.get('/metrics', authenticate, async (_req: AuthRequest, res: Response) => {
    try {
      const [candidates, jobs, screened, shortlisted, matchResult, auditResult] = await Promise.all([
        pool.query('SELECT COUNT(*) FROM candidates'),
        pool.query("SELECT COUNT(*) FROM job_descriptions WHERE status = 'active'"),
        pool.query("SELECT COUNT(*) FROM candidates WHERE status IN ('screening', 'shortlisted', 'interviewed')"),
        pool.query("SELECT COUNT(*) FROM candidates WHERE status IN ('shortlisted', 'interviewed', 'offered', 'hired')"),
        pool.query('SELECT AVG(overall_score) as avg_score FROM match_results'),
        pool.query('SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10'),
      ])

      res.json({
        totalCandidates: parseInt(candidates.rows[0].count),
        activeJobs: parseInt(jobs.rows[0].count),
        candidatesScreened: parseInt(screened.rows[0].count),
        candidatesShortlisted: parseInt(shortlisted.rows[0].count),
        averageMatchScore: Math.round(parseFloat(matchResult.rows[0]?.avg_score || '0')),
        hiringVelocity: 12,
        recentActivity: auditResult.rows.map((row) => ({
          id: row.id,
          type: 'activity',
          message: row.action,
          timestamp: row.timestamp,
          userId: 'system',
        })),
      })
    } catch (error) {
      console.error('Dashboard metrics error:', error)
      res.status(500).json({ message: 'Failed to fetch metrics', code: 'METRICS_FAILED' })
    }
  })

  router.get('/activity', authenticate, async (_req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        'SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 20'
      )
      res.json(result.rows.map((row) => ({
        id: row.id,
        type: 'activity',
        message: row.action,
        details: row.details,
        timestamp: row.timestamp,
      })))
    } catch (error) {
      console.error('Activity error:', error)
      res.status(500).json({ message: 'Failed to fetch activity', code: 'ACTIVITY_FAILED' })
    }
  })

  return router
}
