import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'

const ALLOWED_KEYS = new Set([
  'llm_weight',
  'skill_weight',
  'experience_weight',
  'certification_weight',
  'education_weight',
  'resume_quality_weight',
])

export function createSettingsRouter(pool: Pool) {
  const router = Router()

  router.get('/weights', authenticate, async (_req: AuthRequest, res: Response) => {
    try {
      const { rows } = await pool.query(`SELECT key, value FROM scoring_weights ORDER BY key`)
      const weights: Record<string, number> = {}
      for (const r of rows) weights[r.key] = r.value
      res.json({ weights })
    } catch (e) {
      console.error('Get weights error:', e)
      res.status(500).json({ message: 'Failed to load weights', code: 'WEIGHTS_FAILED' })
    }
  })

  router.put('/weights', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const incoming = (req.body?.weights || {}) as Record<string, unknown>
      const updates: Array<[string, number]> = []
      for (const [k, v] of Object.entries(incoming)) {
        if (!ALLOWED_KEYS.has(k)) continue
        const n = typeof v === 'number' ? v : parseFloat(String(v))
        if (!Number.isFinite(n) || n < 0 || n > 1) {
          return res.status(400).json({ message: `Invalid weight ${k}: must be 0-1`, code: 'INVALID_WEIGHT' })
        }
        updates.push([k, n])
      }
      if (updates.length === 0) {
        return res.status(400).json({ message: 'No valid weights provided', code: 'NO_WEIGHTS' })
      }
      for (const [k, v] of updates) {
        await pool.query(
          `INSERT INTO scoring_weights (key, value) VALUES ($1, $2)
           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()`,
          [k, v],
        )
      }
      const { rows } = await pool.query(`SELECT key, value FROM scoring_weights ORDER BY key`)
      const weights: Record<string, number> = {}
      for (const r of rows) weights[r.key] = r.value
      res.json({ weights, updated: updates.length })
    } catch (e) {
      console.error('Update weights error:', e)
      res.status(500).json({ message: 'Failed to update weights', code: 'WEIGHTS_UPDATE_FAILED' })
    }
  })

  return router
}
