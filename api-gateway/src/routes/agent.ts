import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'
import axios from 'axios'
import { config } from '../config/index.js'

const router = Router()

const aiClient = axios.create({
  baseURL: config.aiService.url,
  timeout: 120000, // 2 min for LLM responses
})

export function createAgentRouter(pool: Pool) {
  router.post('/chat', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { message, session_id } = req.body
      if (!message || typeof message !== 'string') {
        return res.status(400).json({ message: 'Message is required', code: 'MISSING_MESSAGE' })
      }

      // Try to forward to Python AI service which has full Ollama/Gemini integration
      try {
        const aiRes = await aiClient.post('/api/agent/chat', {
          message,
          session_id: session_id || `session-${Date.now()}`,
        })
        return res.json(aiRes.data)
      } catch (aiError) {
        console.warn('AI service unavailable, falling back to direct Ollama call')
      }

      // Fallback: call Ollama directly from gateway if AI service is down
      const ollamaUrl = process.env.OLLAMA_URL || 'http://localhost:11434'
      const ollamaModel = process.env.OLLAMA_MODEL || 'llama3'

      // Build candidate context from DB
      let candidateContext = ''
      try {
        const candidates = await pool.query(
          `SELECT c.id, c.name, c.status, c.location, r.experience_years, r.skills_list, r.primary_domain
           FROM candidates c
           LEFT JOIN resumes r ON r.candidate_id = c.id
           ORDER BY c.created_at DESC
           LIMIT 20`
        )
        if (candidates.rows.length > 0) {
          candidateContext = 'Available candidates:\n' + candidates.rows.map((c, i) =>
            `${i + 1}. ${c.name || 'Unknown'} | Domain: ${c.primary_domain || 'N/A'} | Exp: ${c.experience_years || 0} yrs | Skills: ${c.skills_list || 'N/A'} | Status: ${c.status} | Location: ${c.location || 'N/A'}`
          ).join('\n')
        }
      } catch (dbErr) {
        console.error('DB context fetch failed:', dbErr)
      }

      let jobContext = ''
      try {
        const jobs = await pool.query(
          `SELECT title, location, experience_years_required, required_skills
           FROM job_descriptions WHERE status = 'active' LIMIT 10`
        )
        if (jobs.rows.length > 0) {
          jobContext = 'Active job openings:\n' + jobs.rows.map((j) =>
            `- ${j.title} | Location: ${j.location || 'N/A'} | Exp: ${j.experience_years_required || 0}+ yrs | Skills: ${j.required_skills || 'N/A'}`
          ).join('\n')
        }
      } catch (dbErr) {
        console.error('Jobs context fetch failed:', dbErr)
      }

      const systemPrompt = `You are an AI HR Assistant for an industrial recruitment platform.
You help recruiters find, evaluate, and compare candidates for heavy industry roles (Mining, Steel, Power Plants, Manufacturing, Logistics).

${candidateContext ? candidateContext + '\n\n' : ''}${jobContext ? jobContext + '\n\n' : ''}

Guidelines:
- Base answers on the actual candidate data provided above
- Highlight safety certifications (DGMS, OSHA, Boiler, Crane, Blasting) as critical
- Be concise, professional, and data-driven
- If asked about a candidate not in the list, say they are not in the database
- Suggest interview questions when asked about specific candidates`

      try {
        const ollamaRes = await axios.post(
          `${ollamaUrl}/api/chat`,
          {
            model: ollamaModel,
            messages: [
              { role: 'system', content: systemPrompt },
              { role: 'user', content: message },
            ],
            stream: false,
          },
          { timeout: 120000 }
        )

        const response = ollamaRes.data?.message?.content || 'No response from LLM.'
        return res.json({
          response,
          sessionId: session_id || `session-${Date.now()}`,
          provider: 'ollama',
        })
      } catch (ollamaErr) {
        console.error('Ollama call failed:', ollamaErr)
        return res.status(503).json({
          message: 'AI service unavailable. Ensure Ollama is running with a model loaded, or the Python AI service is started.',
          code: 'LLM_UNAVAILABLE',
        })
      }
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

  router.get('/status/:runId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        `SELECT * FROM agent_logs WHERE run_id = $1 ORDER BY timestamp DESC LIMIT 1`,
        [req.params.runId]
      )
      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'Run not found', code: 'NOT_FOUND' })
      }
      const row = result.rows[0]
      res.json({
        runId: row.run_id,
        agentName: row.agent_name,
        lastMessage: row.message,
        stateSnapshot: row.state_snapshot,
        timestamp: row.timestamp,
      })
    } catch (error) {
      console.error('Get status error:', error)
      res.status(500).json({ message: 'Failed to get status', code: 'STATUS_FAILED' })
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

      // Forward to Python AI service for actual processing
      try {
        await aiClient.post('/api/agent/pipeline', { candidateId, runId })
      } catch {
        console.warn('Could not forward pipeline to AI service')
      }

      res.json({ runId, status: 'processing', message: 'AI pipeline started' })
    } catch (error) {
      console.error('Pipeline error:', error)
      res.status(500).json({ message: 'Pipeline failed', code: 'PIPELINE_FAILED' })
    }
  })

  return router
}
