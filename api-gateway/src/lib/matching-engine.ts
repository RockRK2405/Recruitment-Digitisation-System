/**
 * AI Matching Engine — two-stage candidate evaluation against a job.
 *
 * Stage 1 (pre-filter): cheap structured scoring — skill overlap + experience
 *   gap. Selects the top N candidates (configurable, default 20).
 *
 * Stage 2 (LLM evaluation): for each shortlisted candidate, sends parsed JD +
 *   full candidate profile to the LLM. LLM returns a strict JSON breakdown
 *   (skill_match, experience_match, education_match, ... + strengths,
 *   weaknesses, missing_skills, interview_focus, recommendation, summary).
 *
 * Final score is a hybrid: weighted blend of the LLM's overall_match and the
 *   component scores. Weights come from the scoring_weights table (configurable
 *   from the Settings page).
 *
 * Results cached in match_results — re-running re-evaluates everyone.
 */

import { Pool } from 'pg'
import { completeLLM } from './llm.js'

const PROMPT_VERSION = 'match_v1'
const DEFAULT_LLM_MODEL_LABEL = process.env.OPENAI_COMPATIBLE_MODEL || process.env.OLLAMA_MODEL || 'unknown'

// ─── Types ────────────────────────────────────────────────────────

export interface LLMEvaluation {
  overall_match: number
  recommendation: string
  skill_match: number
  experience_match: number
  education_match: number
  certification_match: number
  industry_match: number
  leadership_score: number
  communication_score: number
  growth_score: number
  resume_quality: number
  missing_skills: string[]
  strengths: string[]
  weaknesses: string[]
  interview_focus: string[]
  summary: string
}

interface ScoringWeights {
  llm_weight: number
  skill_weight: number
  experience_weight: number
  certification_weight: number
  education_weight: number
  resume_quality_weight: number
}

const DEFAULT_WEIGHTS: ScoringWeights = {
  llm_weight: 0.40,
  skill_weight: 0.25,
  experience_weight: 0.15,
  certification_weight: 0.10,
  education_weight: 0.05,
  resume_quality_weight: 0.05,
}

// ─── Utilities ────────────────────────────────────────────────────

function normalize(s: string): string {
  return s.toLowerCase().trim().replace(/\s+/g, ' ')
}

function asArray(val: unknown): string[] {
  if (Array.isArray(val)) return val.map(String).filter(Boolean)
  if (typeof val === 'string') return val.split(',').map((s) => s.trim()).filter(Boolean)
  return []
}

function skillOverlap(required: string[], candidate: string[]): { score: number; matched: string[]; missing: string[] } {
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

export async function getWeights(pool: Pool): Promise<ScoringWeights> {
  try {
    const { rows } = await pool.query(`SELECT key, value FROM scoring_weights`)
    const w: Partial<ScoringWeights> = {}
    for (const r of rows) (w as Record<string, number>)[r.key] = r.value
    // Backfill anything missing with defaults
    return { ...DEFAULT_WEIGHTS, ...w }
  } catch {
    return DEFAULT_WEIGHTS
  }
}

// ─── LLM evaluation ───────────────────────────────────────────────

function buildEvalPrompt(job: Record<string, unknown>, candidate: Record<string, unknown>, certs: string[]): string {
  const jobBlock = {
    title: job.title,
    department: job.department || '',
    location: job.location || '',
    employment_type: job.employment_type || '',
    industry: job.industry || '',
    experience_years_required: job.experience_years_required || 0,
    mandatory_skills: asArray(job.mandatory_skills),
    preferred_skills: asArray(job.preferred_skills),
    required_certifications: asArray(job.required_certifications),
    education_required: job.education_required || '',
    responsibilities: job.responsibilities || job.description || '',
    soft_skills: asArray(job.soft_skills),
  }
  const candBlock = {
    name: candidate.name,
    experience_years: candidate.experience_years || 0,
    primary_domain: candidate.primary_domain || '',
    location: candidate.location || '',
    skills: asArray(candidate.skills_list),
    equipment: asArray(candidate.equipment_handled),
    languages: asArray(candidate.languages),
    education: candidate.education || '',
    certifications: certs,
    ai_summary: candidate.ai_summary || '',
    resume_text_excerpt: typeof candidate.raw_text === 'string' ? (candidate.raw_text as string).slice(0, 3500) : '',
  }

  return `You are a senior Talent Acquisition Manager for industrial recruitment. Evaluate this candidate against this job. Reason like an experienced HR — consider career progression, domain relevance, transferable skills, gaps, growth signals. Return ONLY a strict JSON object — no markdown, no preamble.

Required schema (every field is required; use 0 / [] / "" if unknown):
{
  "overall_match": number 0-100,
  "recommendation": "Highly Recommended" | "Recommended" | "Recommended with Training" | "Potential Candidate" | "Not Recommended",
  "skill_match": number 0-100,
  "experience_match": number 0-100,
  "education_match": number 0-100,
  "certification_match": number 0-100,
  "industry_match": number 0-100,
  "leadership_score": number 0-100,
  "communication_score": number 0-100,
  "growth_score": number 0-100,
  "resume_quality": number 0-100,
  "missing_skills": string[],
  "strengths": string[] (3-5 bullets, specific to this candidate's actual experience),
  "weaknesses": string[] (2-4 bullets, specific gaps vs this job),
  "interview_focus": string[] (3-5 topics the interviewer should probe),
  "summary": string (2-3 sentences referencing actual resume facts)
}

JOB:
${JSON.stringify(jobBlock, null, 2)}

CANDIDATE:
${JSON.stringify(candBlock, null, 2)}

Return the JSON evaluation now.`
}

function extractJsonObject(raw: string): unknown {
  const trimmed = raw.trim().replace(/^```(?:json)?/, '').replace(/```$/, '').trim()
  const start = trimmed.indexOf('{')
  const end = trimmed.lastIndexOf('}')
  if (start === -1 || end === -1) throw new Error('no JSON object in LLM response')
  return JSON.parse(trimmed.slice(start, end + 1))
}

function validateEvaluation(raw: unknown): LLMEvaluation {
  const e = (raw && typeof raw === 'object') ? raw as Record<string, unknown> : {}
  const num = (v: unknown, fallback = 0): number => {
    const n = typeof v === 'number' ? v : parseFloat(String(v))
    if (!Number.isFinite(n)) return fallback
    return Math.max(0, Math.min(100, Math.round(n)))
  }
  const arr = (v: unknown): string[] => Array.isArray(v) ? v.map(String).filter(Boolean) : []
  const str = (v: unknown): string => typeof v === 'string' ? v : ''
  return {
    overall_match: num(e.overall_match),
    recommendation: str(e.recommendation) || 'Potential Candidate',
    skill_match: num(e.skill_match),
    experience_match: num(e.experience_match),
    education_match: num(e.education_match),
    certification_match: num(e.certification_match),
    industry_match: num(e.industry_match),
    leadership_score: num(e.leadership_score),
    communication_score: num(e.communication_score),
    growth_score: num(e.growth_score),
    resume_quality: num(e.resume_quality),
    missing_skills: arr(e.missing_skills),
    strengths: arr(e.strengths),
    weaknesses: arr(e.weaknesses),
    interview_focus: arr(e.interview_focus),
    summary: str(e.summary),
  }
}

async function evaluateWithLLM(job: Record<string, unknown>, candidate: Record<string, unknown>, certs: string[]): Promise<LLMEvaluation | null> {
  try {
    const prompt = buildEvalPrompt(job, candidate, certs)
    const raw = await completeLLM(prompt)
    if (!raw || raw.toLowerCase().startsWith("i'm unable")) return null
    return validateEvaluation(extractJsonObject(raw))
  } catch (e) {
    console.warn('LLM eval failed for candidate:', e instanceof Error ? e.message : e)
    return null
  }
}

function hybridScore(llmOverall: number, struct: { skill: number; exp: number; cert: number; edu: number; resQuality: number }, weights: ScoringWeights): number {
  const denom = weights.llm_weight + weights.skill_weight + weights.experience_weight + weights.certification_weight + weights.education_weight + weights.resume_quality_weight
  if (denom <= 0) return llmOverall
  const num =
    llmOverall * weights.llm_weight +
    struct.skill * weights.skill_weight +
    struct.exp * weights.experience_weight +
    struct.cert * weights.certification_weight +
    struct.edu * weights.education_weight +
    struct.resQuality * weights.resume_quality_weight
  return Math.round(num / denom)
}

// ─── Main entry: two-stage matching ───────────────────────────────

export interface RunOptions {
  prefilterTopN?: number   // default 20
  llmTopN?: number         // run LLM only on the first N (default = same as prefilterTopN)
  forceReeval?: boolean    // ignore cached LLM evals
}

export async function runMatchingForJob(
  pool: Pool,
  jobId: string,
  opts: RunOptions = {},
): Promise<{ totalCandidates: number; llmEvaluated: number; errors: string[] }> {
  const errors: string[] = []
  const prefilterTopN = opts.prefilterTopN ?? 20
  const llmTopN = opts.llmTopN ?? prefilterTopN
  console.log(`[AI-MATCH] ▶ start job=${jobId} prefilterTopN=${prefilterTopN} llmTopN=${llmTopN} forceReeval=${!!opts.forceReeval}`)

  const jobRes = await pool.query(`SELECT * FROM job_descriptions WHERE id = $1`, [jobId])
  if (jobRes.rows.length === 0) {
    console.error(`[AI-MATCH] ✗ job not found: ${jobId}`)
    throw new Error('Job not found')
  }
  const job = jobRes.rows[0]
  console.log(`[AI-MATCH] ✓ job loaded: "${job.title}"`)

  const requiredSkills = [...asArray(job.mandatory_skills), ...asArray(job.preferred_skills), ...asArray(job.required_skills)]
  const requiredCerts = asArray(job.required_certifications)
  const requiredExp: number = job.experience_years_required || 0

  // Pull all candidates with their resume + cert names
  const candRes = await pool.query(
    `SELECT c.id, c.name, c.email, c.location, c.experience_years, c.primary_domain,
            c.ai_summary, r.skills_list, r.equipment_handled, r.languages, r.education,
            r.raw_text
     FROM candidates c
     LEFT JOIN resumes r ON r.candidate_id = c.id`,
  )
  console.log(`[AI-MATCH] ✓ loaded ${candRes.rows.length} candidates`)

  if (candRes.rows.length === 0) {
    console.warn('[AI-MATCH] no candidates in DB — nothing to score')
    return { totalCandidates: 0, llmEvaluated: 0, errors: ['No candidates in database. Upload resumes first.'] }
  }

  const weights = await getWeights(pool)
  console.log(`[AI-MATCH] ✓ weights: llm=${weights.llm_weight} skill=${weights.skill_weight} exp=${weights.experience_weight} cert=${weights.certification_weight} edu=${weights.education_weight} rq=${weights.resume_quality_weight}`)

  // Stage 1: fast structured scoring for every candidate
  type Prefiltered = {
    candidateId: string
    name: string
    rec: Record<string, unknown>
    skill: ReturnType<typeof skillOverlap>
    cert: ReturnType<typeof skillOverlap>
    exp: number
    structScore: number
    certs: string[]
  }
  const prefiltered: Prefiltered[] = []

  for (const cand of candRes.rows) {
    const candSkills = [...asArray(cand.skills_list), ...asArray(cand.equipment_handled)]
    const skill = skillOverlap(requiredSkills, candSkills)

    const certRes = await pool.query(`SELECT name FROM certifications WHERE candidate_id = $1`, [cand.id])
    const certs = certRes.rows.map((r) => String(r.name))
    const cert = skillOverlap(requiredCerts, certs)

    const exp = experienceScore(requiredExp, cand.experience_years || 0)
    // Pre-filter score: heavier on skills, lighter on experience
    const structScore = Math.round(skill.score * 0.7 + exp * 0.3)

    prefiltered.push({ candidateId: cand.id, name: cand.name, rec: cand, skill, cert, exp, structScore, certs })
  }

  prefiltered.sort((a, b) => b.structScore - a.structScore)
  const shortlist = prefiltered.slice(0, Math.max(prefilterTopN, llmTopN))

  // Stage 1: write baseline row for every candidate so the dashboard has data
  let prefilterWritten = 0
  for (const p of prefiltered) {
    try {
      await pool.query(
        `INSERT INTO match_results (
           candidate_id, job_id, vector_score, skill_score, agent_score,
           overall_score, llm_score, experience_match, education_match,
           certification_match, industry_match, leadership_score, communication_score,
           growth_score, resume_quality, matched_skills, missing_skills,
           strengths, weaknesses, interview_focus, recommendation, match_explanation,
           llm_summary, llm_model_used, prompt_version, evaluated_at, stage)
         VALUES ($1, $2, 0, $3, $4, $5, 0, $6, 0, $4, 0, 0, 0, 0, 0, $7, $8,
                 '{}', '{}', '{}', NULL, '', NULL, NULL, NULL, NULL, 'prefilter')
         ON CONFLICT (candidate_id, job_id) DO UPDATE SET
           skill_score = EXCLUDED.skill_score,
           agent_score = EXCLUDED.agent_score,
           experience_match = EXCLUDED.experience_match,
           certification_match = EXCLUDED.certification_match,
           matched_skills = EXCLUDED.matched_skills,
           missing_skills = EXCLUDED.missing_skills,
           overall_score = CASE WHEN match_results.stage = 'llm' THEN match_results.overall_score ELSE EXCLUDED.overall_score END`,
        [p.candidateId, jobId, p.skill.score, p.cert.score, p.structScore, p.exp, p.skill.matched, p.skill.missing],
      )
      prefilterWritten++
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      errors.push(`Prefilter insert failed for candidate ${p.candidateId}: ${msg}`)
      console.error(`[AI-MATCH] ✗ prefilter insert failed for ${p.name} (${p.candidateId}):`, msg)
    }
  }
  console.log(`[AI-MATCH] ✓ stage 1 done: ${prefilterWritten}/${prefiltered.length} prefilter rows written`)

  // Stage 2: LLM evaluation for the shortlist
  let llmCount = 0
  for (const p of shortlist.slice(0, llmTopN)) {
    // Cache: skip if we already have an LLM eval at the current prompt version and
    // candidate hasn't been updated since (unless forceReeval)
    if (!opts.forceReeval) {
      const cached = await pool.query(
        `SELECT mr.evaluated_at, mr.prompt_version, c.updated_at AS candidate_updated, j.updated_at AS job_updated
         FROM match_results mr
         JOIN candidates c ON c.id = mr.candidate_id
         JOIN job_descriptions j ON j.id = mr.job_id
         WHERE mr.candidate_id = $1 AND mr.job_id = $2`,
        [p.candidateId, jobId],
      )
      const row = cached.rows[0]
      if (row && row.evaluated_at && row.prompt_version === PROMPT_VERSION &&
          (!row.candidate_updated || new Date(row.candidate_updated) <= new Date(row.evaluated_at)) &&
          (!row.job_updated || new Date(row.job_updated) <= new Date(row.evaluated_at))) {
        continue
      }
    }

    console.log(`[AI-MATCH] ↻ LLM eval ${p.name} (${p.candidateId.slice(0, 8)})`)
    const evalResult = await evaluateWithLLM(job, p.rec, p.certs)
    if (!evalResult) {
      const reason = `LLM eval returned null for ${p.name} — provider may be unreachable, response not valid JSON, or model refused. Check LLM_PROVIDER + OPENAI_COMPATIBLE_* env vars.`
      errors.push(reason)
      console.warn(`[AI-MATCH] ✗ ${reason}`)
      continue
    }
    llmCount++
    console.log(`[AI-MATCH] ✓ LLM eval ${p.name}: overall=${evalResult.overall_match} rec=${evalResult.recommendation}`)

    const overall = hybridScore(evalResult.overall_match, {
      skill: evalResult.skill_match || p.skill.score,
      exp: evalResult.experience_match || p.exp,
      cert: evalResult.certification_match || p.cert.score,
      edu: evalResult.education_match,
      resQuality: evalResult.resume_quality,
    }, weights)

    try {
      await pool.query(
        `UPDATE match_results SET
           llm_score = $1,
           overall_score = $2,
           skill_score = $3,
           experience_match = $4,
           education_match = $5,
           certification_match = $6,
           industry_match = $7,
           leadership_score = $8,
           communication_score = $9,
           growth_score = $10,
           resume_quality = $11,
           missing_skills = $12,
           strengths = $13,
           weaknesses = $14,
           interview_focus = $15,
           recommendation = $16,
           llm_summary = $17,
           match_explanation = $17,
           llm_model_used = $18,
           prompt_version = $19,
           evaluated_at = NOW(),
           stage = 'llm'
         WHERE candidate_id = $20 AND job_id = $21`,
        [
          evalResult.overall_match, overall, evalResult.skill_match,
          evalResult.experience_match, evalResult.education_match,
          evalResult.certification_match, evalResult.industry_match,
          evalResult.leadership_score, evalResult.communication_score,
          evalResult.growth_score, evalResult.resume_quality,
          evalResult.missing_skills.length > 0 ? evalResult.missing_skills : p.skill.missing,
          evalResult.strengths, evalResult.weaknesses, evalResult.interview_focus,
          evalResult.recommendation, evalResult.summary,
          DEFAULT_LLM_MODEL_LABEL, PROMPT_VERSION,
          p.candidateId, jobId,
        ],
      )
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      errors.push(`Stage 2 UPDATE failed for ${p.candidateId}: ${msg}`)
      console.error(`[AI-MATCH] ✗ stage 2 update failed for ${p.name}:`, msg)
    }
  }

  console.log(`[AI-MATCH] ▷ done job=${jobId} prefilter=${prefilterWritten} llm_evaluated=${llmCount} errors=${errors.length}`)
  return { totalCandidates: prefiltered.length, llmEvaluated: llmCount, errors }
}

export { PROMPT_VERSION as MATCH_PROMPT_VERSION }
