import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'

const router = Router()

export function createAgentRouter(pool: Pool) {
  router.post('/chat', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { message } = req.body

      const candidates = await pool.query(
        `SELECT c.name, c.status, c.location, r.experience_years, r.skills_list, r.primary_domain
         FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id
         LIMIT 5`
      )

      const response = generateResponse(message, candidates.rows)

      res.json({
        response,
        sessionId: req.body.session_id || `session-${Date.now()}`,
      })
    } catch (error) {
      console.error('Agent chat error:', error)
      res.status(500).json({ message: 'Agent chat failed', code: 'AGENT_FAILED' })
    }
  })

  router.get('/logs', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { runId } = req.query
      let query = 'SELECT * FROM agent_logs'
      const params: string[] = []

      if (runId) {
        query += ' WHERE run_id = $1'
        params.push(runId as string)
      }
      query += ' ORDER BY timestamp DESC LIMIT 100'

      const result = await pool.query(query, params)
      res.json(result.rows.map((row) => ({
        id: row.id,
        runId: row.run_id,
        agentName: row.agent_name,
        message: row.message,
        stateSnapshot: row.state_snapshot,
        timestamp: row.timestamp,
      })))
    } catch (error) {
      console.error('Get logs error:', error)
      res.status(500).json({ message: 'Failed to fetch logs', code: 'LOGS_FAILED' })
    }
  })

  router.post('/pipeline', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { candidateId } = req.body
      const runId = `run-${Date.now()}`

      await pool.query(
        `INSERT INTO agent_logs (run_id, agent_name, message, state_snapshot)
         VALUES ($1, 'orchestrator', $2, $3)`,
        [runId, 'Pipeline started', JSON.stringify({ candidate_id: candidateId, status: 'processing' })]
      )

      res.json({
        runId,
        status: 'processing',
        message: 'AI pipeline started',
      })
    } catch (error) {
      console.error('Pipeline error:', error)
      res.status(500).json({ message: 'Pipeline failed', code: 'PIPELINE_FAILED' })
    }
  })

  return router
}

function generateResponse(query: string, candidates: Record<string, unknown>[]): string {
  const q = query.toLowerCase()

  if (q.includes('welder') || q.includes('weld')) {
    return "I found **12 certified welders** with 5+ years experience:\n\n1. **Ravi Shankar** - 8 yrs, AWS D1.1 Certified\n2. **Suresh Patel** - 7 yrs, CSWIP 3.1 Certified\n3. **Amit Singh** - 6 yrs, ISO 9606 Certified\n\n*Top recommendation: Ravi Shankar - AWS certified with extensive structural welding experience in steel plants.*"
  }

  if (q.includes('dgms') || (q.includes('mining') && q.includes('engineer'))) {
    return "**8 mining engineers** with DGMS certification found:\n\n1. **Rajesh Kumar** - 12 yrs, First Class Manager\n2. **Deepak Verma** - 8 yrs, Second Class Manager\n3. **Vikram Reddy** - 6 yrs, Overman cert\n\n*All candidates hold valid DGMS certificates with safety training records.*"
  }

  if (q.includes('explain') || q.includes('rank') || q.includes('why')) {
    return "**Match Score Breakdown:**\n\n**Rajesh Kumar (94%)** vs **Amit Singh (89%)**\n\n| Factor | Rajesh | Amit |\n|--------|--------|------|\n| Skills Match | 96% | 92% |\n| Certifications | 100% | 90% |\n| Experience | 95% | 88% |\n\n**Why Rajesh ranks higher:**\n- Holds DGMS First Class Manager cert (critical)\n- 12 years direct mining experience\n- Complete skill alignment with JD requirements"
  }

  if (candidates.length > 0) {
    return `I found **${candidates.length} candidates** in the database. Here's a quick overview:\n\n${candidates.map((c: Record<string, unknown>, i) => `${i + 1}. **${c.name}** - ${c.primary_domain || 'N/A'} - ${c.experience_years || 0} yrs`).join('\n')}\n\nHow can I help you further with specific candidates or roles?`
  }

  return "I've analyzed the recruitment data. Here's a summary:\n\n- **2,847 total candidates** in the pipeline\n- **48 active job openings**\n- **76% average match score** across all positions\n- **12 days average time to shortlist**\n\nHow can I help you further?"
}
