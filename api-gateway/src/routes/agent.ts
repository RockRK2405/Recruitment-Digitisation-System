import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'
import axios from 'axios'
import { config } from '../config/index.js'
import { chatLLM, ChatMessage } from '../lib/llm.js'

const router = Router()

const aiClient = axios.create({
  baseURL: config.aiService.url,
  timeout: 120000,
})

// In-memory session store. Survives restarts only as long as the process runs.
// For prod, persist to Redis — but for single-tenant use this is fine.
const sessions = new Map<string, ChatMessage[]>()

function getHistory(id: string): ChatMessage[] {
  if (!sessions.has(id)) sessions.set(id, [])
  return sessions.get(id)!
}

async function buildRagContext(pool: Pool, message: string): Promise<string> {
  const sections: string[] = []

  // Recent candidates — always included for general context
  try {
    const { rows } = await pool.query(
      `SELECT c.id, c.name, c.email, c.phone, c.location, c.status, c.experience_years,
              c.primary_domain, c.ai_summary, r.skills_list, r.education, r.languages,
              r.equipment_handled
       FROM candidates c
       LEFT JOIN resumes r ON r.candidate_id = c.id
       ORDER BY c.updated_at DESC NULLS LAST, c.created_at DESC
       LIMIT 30`,
    )
    if (rows.length > 0) {
      sections.push(
        'CANDIDATE DATABASE:\n' + rows.map((c, i) => {
          const skills = Array.isArray(c.skills_list) ? c.skills_list.join(', ') : (c.skills_list || 'N/A')
          return `${i + 1}. ${c.name || 'Unknown'} | ID: ${c.id} | ${c.experience_years || 0} yrs | ${c.primary_domain || 'N/A'} | ${c.location || 'N/A'} | Skills: ${skills} | Status: ${c.status}`
        }).join('\n'),
      )
    }
  } catch (e) {
    console.warn('candidate context fetch failed:', e instanceof Error ? e.message : e)
  }

  // Active jobs
  try {
    const { rows } = await pool.query(
      `SELECT id, title, location, experience_years_required, required_skills, required_certifications, industry
       FROM job_descriptions WHERE status = 'active' ORDER BY created_at DESC LIMIT 15`,
    )
    if (rows.length > 0) {
      sections.push(
        'ACTIVE JOB OPENINGS:\n' + rows.map((j) => {
          const skills = Array.isArray(j.required_skills) ? j.required_skills.join(', ') : (j.required_skills || 'N/A')
          const certs = Array.isArray(j.required_certifications) ? j.required_certifications.join(', ') : (j.required_certifications || 'none')
          return `- [${j.id}] ${j.title} | ${j.location || 'N/A'} | ${j.experience_years_required || 0}+ yrs | Industry: ${j.industry || 'N/A'} | Skills: ${skills} | Certs: ${certs}`
        }).join('\n'),
      )
    }
  } catch (e) {
    console.warn('jobs context fetch failed:', e instanceof Error ? e.message : e)
  }

  // Targeted: if user mentions a candidate by name, pull full profile + certs
  try {
    const lower = message.toLowerCase()
    const { rows: matches } = await pool.query(
      `SELECT c.id, c.name, c.email, c.phone, c.location, c.experience_years, c.primary_domain,
              c.ai_summary, r.skills_list, r.education, r.languages, r.equipment_handled, r.raw_text
       FROM candidates c
       LEFT JOIN resumes r ON r.candidate_id = c.id
       WHERE LOWER(c.name) <> '' AND POSITION(LOWER(c.name) IN $1) > 0
       LIMIT 3`,
      [lower],
    )
    for (const c of matches) {
      const { rows: certs } = await pool.query(
        `SELECT name, issuer, issue_date, expiry_date FROM certifications WHERE candidate_id = $1`,
        [c.id],
      )
      sections.push(
        `DETAILED PROFILE — ${c.name}:\n` +
        `Email: ${c.email || 'N/A'} | Phone: ${c.phone || 'N/A'} | Location: ${c.location || 'N/A'}\n` +
        `Experience: ${c.experience_years || 0} yrs | Domain: ${c.primary_domain || 'N/A'}\n` +
        `Skills: ${Array.isArray(c.skills_list) ? c.skills_list.join(', ') : (c.skills_list || 'N/A')}\n` +
        `Equipment: ${Array.isArray(c.equipment_handled) ? c.equipment_handled.join(', ') : (c.equipment_handled || 'N/A')}\n` +
        `Languages: ${Array.isArray(c.languages) ? c.languages.join(', ') : (c.languages || 'N/A')}\n` +
        `Education: ${c.education || 'N/A'}\n` +
        `Summary: ${c.ai_summary || 'N/A'}\n` +
        `Certifications: ${certs.map((ce) => `${ce.name}${ce.issuer ? ' (' + ce.issuer + ')' : ''}`).join('; ') || 'none'}`,
      )
    }
  } catch (e) {
    console.warn('detailed candidate fetch failed:', e instanceof Error ? e.message : e)
  }

  return sections.join('\n\n')
}

export function createAgentRouter(pool: Pool) {
  router.post('/chat', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const { message, session_id } = req.body
      if (!message || typeof message !== 'string') {
        return res.status(400).json({ message: 'Message is required', code: 'MISSING_MESSAGE' })
      }

      const sessionId: string = session_id || `session-${Date.now()}`
      const history = getHistory(sessionId)

      const ragContext = await buildRagContext(pool, message)

      const systemPrompt = `You are Kshamata, an AI HR Assistant for an industrial recruitment platform serving heavy industry (Mining, Steel, Power Plants, Manufacturing, Logistics, Construction).

${ragContext || '(No candidate or job data in the system yet.)'}

Guidelines:
- Ground every answer in the data provided above — never invent candidates or jobs.
- For safety-critical industrial roles, flag relevant certifications: DGMS, OSHA, Boiler, Crane, Blasting, Mines Manager, First Aid.
- Be concise, professional, data-driven. Use bullets and tables when comparing multiple candidates.
- When asked to rank or match candidates to a job, compute and explain the match: skill overlap, experience gap, missing certifications, recommendation.
- When asked to interview a candidate, generate 5-7 role-specific questions based on their actual skills and experience.
- If a candidate or job isn't in the database, say so plainly.`

      const messages: ChatMessage[] = [
        { role: 'system', content: systemPrompt },
        ...history.slice(-10),
        { role: 'user', content: message },
      ]

      const { text, provider } = await chatLLM(messages)

      history.push({ role: 'user', content: message })
      history.push({ role: 'assistant', content: text })

      return res.json({ response: text, sessionId, provider })
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
