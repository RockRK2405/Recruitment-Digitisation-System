import { Router, Response } from 'express'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'
import axios from 'axios'
import { config } from '../config/index.js'
import { completeLLM } from '../lib/llm.js'

const router = Router()
const aiClient = axios.create({ baseURL: config.aiService.url, timeout: 30000 })

function normalize(s: string): string {
  return s.toLowerCase().trim().replace(/\s+/g, ' ')
}

function asArray(val: unknown): string[] {
  if (Array.isArray(val)) return val.map((v) => String(v))
  if (typeof val === 'string') return val.split(',').map((s) => s.trim()).filter(Boolean)
  return []
}

function skillOverlapScore(required: string[], candidate: string[]): { score: number; matched: string[]; missing: string[] } {
  const req = required.map(normalize).filter(Boolean)
  const cand = new Set(candidate.map(normalize).filter(Boolean))
  if (req.length === 0) return { score: 100, matched: [], missing: [] }
  const matched: string[] = []
  const missing: string[] = []
  for (const r of req) {
    const hit = Array.from(cand).some((c) => c === r || c.includes(r) || r.includes(c))
    if (hit) matched.push(r)
    else missing.push(r)
  }
  return { score: Math.round((matched.length / req.length) * 100), matched, missing }
}

function experienceScore(required: number | null, actual: number | null): number {
  const req = required || 0
  const act = actual || 0
  if (req === 0) return 100
  if (act >= req) return 100
  return Math.round((act / req) * 100)
}

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
      const { query, limit = 10 } = req.body
      if (!query) return res.status(400).json({ message: 'query is required', code: 'MISSING_QUERY' })

      // Try Python vector search first for semantic accuracy
      try {
        const aiRes = await aiClient.post('/api/match/semantic', { query, limit })
        const candidates = aiRes.data?.candidates || aiRes.data || []
        return res.json(candidates.map((c: Record<string, unknown>) => ({
          id: c.candidate_id || c.id,
          name: c.name,
          experienceYears: c.experience_years,
          skills: Array.isArray(c.skills) ? c.skills : [],
          primaryDomain: c.primary_domain,
          location: c.location,
          status: c.status,
          vectorScore: c.vector_similarity_score,
        })))
      } catch {
        // Fall back to DB ILIKE search
      }

      const result = await pool.query(
        `SELECT c.id, c.name, c.status, c.location, r.experience_years, r.skills_list, r.primary_domain
         FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id
         WHERE r.raw_text ILIKE $1 OR c.name ILIKE $1 OR r.skills_list ILIKE $1 OR r.primary_domain ILIKE $1
         LIMIT $2`,
        [`%${query}%`, limit]
      )
      res.json(result.rows.map((row) => ({
        id: row.id,
        name: row.name,
        experienceYears: row.experience_years,
        skills: row.skills_list ? row.skills_list.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
        primaryDomain: row.primary_domain,
        location: row.location,
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

  // Run scoring for a given job against every candidate in the DB.
  // Writes/updates rows in match_results. Optionally generates LLM explanations
  // for the top N candidates (skipExplanation=true to skip the LLM step).
  router.post('/run/:jobId', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const jobId = req.params.jobId
      const { explainTopN = 5, skipExplanation = false } = req.body || {}

      const jobRes = await pool.query(`SELECT * FROM job_descriptions WHERE id = $1`, [jobId])
      if (jobRes.rows.length === 0) {
        return res.status(404).json({ message: 'Job not found', code: 'NOT_FOUND' })
      }
      const job = jobRes.rows[0]
      const requiredSkills = asArray(job.required_skills)
      const requiredCerts = asArray(job.required_certifications)
      const requiredExp: number = job.experience_years_required || 0

      const candRes = await pool.query(
        `SELECT c.id, c.name, c.location, c.experience_years, c.primary_domain, c.ai_summary,
                r.skills_list, r.equipment_handled, r.education
         FROM candidates c
         LEFT JOIN resumes r ON r.candidate_id = c.id`,
      )

      const candidatesWithScore: Array<{ candidateId: string; overall: number; skill: number; exp: number; cert: number; matched: string[]; missing: string[]; name: string }> = []

      for (const cand of candRes.rows) {
        const candSkills = asArray(cand.skills_list)
        const candEquipment = asArray(cand.equipment_handled)
        const skillRes = skillOverlapScore(requiredSkills, [...candSkills, ...candEquipment])

        const certRes2 = await pool.query(`SELECT name FROM certifications WHERE candidate_id = $1`, [cand.id])
        const candCerts = certRes2.rows.map((r) => String(r.name))
        const certRes = skillOverlapScore(requiredCerts, candCerts)

        const expScore = experienceScore(requiredExp, cand.experience_years || 0)

        // Weighted overall — skills + experience only. Certifications tracked
        // separately so candidates without specific cert documents aren't
        // unfairly penalized; certs act as a bonus signal in the LLM
        // explanation rather than a numeric weight.
        const overall = Math.round(skillRes.score * 0.7 + expScore * 0.3)

        candidatesWithScore.push({
          candidateId: cand.id,
          name: cand.name,
          overall,
          skill: skillRes.score,
          exp: expScore,
          cert: certRes.score,
          matched: skillRes.matched,
          missing: skillRes.missing,
        })
      }

      candidatesWithScore.sort((a, b) => b.overall - a.overall)

      // Upsert match_results for every candidate. Initial explanation is empty;
      // top-N get an LLM-generated explanation right after.
      for (const c of candidatesWithScore) {
        await pool.query(
          `INSERT INTO match_results (candidate_id, job_id, vector_score, skill_score, agent_score, overall_score, matched_skills, missing_skills, match_explanation)
           VALUES ($1, $2, 0, $3, $4, $5, $6, $7, '')
           ON CONFLICT (candidate_id, job_id) DO UPDATE SET
             skill_score = EXCLUDED.skill_score,
             agent_score = EXCLUDED.agent_score,
             overall_score = EXCLUDED.overall_score,
             matched_skills = EXCLUDED.matched_skills,
             missing_skills = EXCLUDED.missing_skills`,
          [c.candidateId, jobId, c.skill, c.cert, c.overall, c.matched, c.missing],
        )
      }

      // LLM explanations for top N — fire-and-forget so the response is fast
      if (!skipExplanation && candidatesWithScore.length > 0) {
        const top = candidatesWithScore.slice(0, explainTopN)
        Promise.all(top.map(async (c) => {
          try {
            const prompt = `You are an HR analyst. In 2 sentences, explain why this candidate scored ${c.overall}/100 for this job. Be specific about strengths and gaps. No preamble.

Job: ${job.title}
Required skills: ${requiredSkills.join(', ') || 'none specified'}
Required experience: ${requiredExp} years
Required certifications: ${requiredCerts.join(', ') || 'none'}

Candidate: ${c.name}
Matched skills: ${c.matched.join(', ') || 'none'}
Missing skills: ${c.missing.join(', ') || 'none'}
Skill score: ${c.skill}/100  |  Experience score: ${c.exp}/100  |  Certification score: ${c.cert}/100`

            const explanation = await completeLLM(prompt)
            if (explanation && explanation.length > 20 && !explanation.toLowerCase().startsWith("i'm unable")) {
              await pool.query(
                `UPDATE match_results SET match_explanation = $1 WHERE candidate_id = $2 AND job_id = $3`,
                [explanation.slice(0, 4000), c.candidateId, jobId],
              )
            }
          } catch (e) {
            console.warn(`LLM explanation failed for ${c.candidateId}:`, e instanceof Error ? e.message : e)
          }
        })).catch(() => {})
      }

      res.json({
        jobId,
        jobTitle: job.title,
        totalCandidates: candidatesWithScore.length,
        explainedTopN: skipExplanation ? 0 : Math.min(explainTopN, candidatesWithScore.length),
        top: candidatesWithScore.slice(0, 10).map((c) => ({
          candidateId: c.candidateId,
          candidateName: c.name,
          overallScore: c.overall,
          skillScore: c.skill,
          experienceScore: c.exp,
          certificationScore: c.cert,
          matchedSkills: c.matched,
          missingSkills: c.missing,
        })),
      })
    } catch (error) {
      console.error('Matching run error:', error)
      res.status(500).json({ message: 'Failed to run matching', code: 'RUN_FAILED', detail: error instanceof Error ? error.message : String(error) })
    }
  })

  return router
}
