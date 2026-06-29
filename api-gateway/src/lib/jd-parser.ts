import { Pool } from 'pg'
import { completeLLM } from './llm.js'

export interface ParsedJD {
  title: string
  department: string
  location: string
  employment_type: string
  experience_years_required: number
  mandatory_skills: string[]
  preferred_skills: string[]
  required_certifications: string[]
  education_required: string
  responsibilities: string
  soft_skills: string[]
  industry: string
  salary_range: string
  keywords: string[]
}

const JD_PROMPT_VERSION = 'jd_v1'

function buildJdPrompt(title: string, description: string): string {
  return `You are an HR analyst. Read this Job Description and extract structured fields. Return ONLY a JSON object — no preamble, no markdown fences.

Schema:
{
  "title": string,
  "department": string,
  "location": string,
  "employment_type": "Full-time" | "Part-time" | "Contract" | "Internship" | "",
  "experience_years_required": number,
  "mandatory_skills": string[],
  "preferred_skills": string[],
  "required_certifications": string[],
  "education_required": string,
  "responsibilities": string,
  "soft_skills": string[],
  "industry": string,
  "salary_range": string,
  "keywords": string[]
}

Rules:
- Use empty string "" or [] when info isn't present
- experience_years_required: parse "5+", "5-7 years", "minimum 3" all to a single number (lower bound)
- mandatory_skills: hard requirements; preferred_skills: nice-to-haves
- keywords: 5-15 industry/role keywords for indexing
- All skill/cert strings should be canonical and short (e.g. "Python" not "Python programming language")

Job Title: ${title}

Job Description:
${description.slice(0, 8000)}

Return the JSON object only.`
}

function extractJsonObject(raw: string): unknown {
  const trimmed = raw.trim().replace(/^```(?:json)?/, '').replace(/```$/, '').trim()
  const start = trimmed.indexOf('{')
  const end = trimmed.lastIndexOf('}')
  if (start === -1 || end === -1) throw new Error('no JSON object in LLM response')
  return JSON.parse(trimmed.slice(start, end + 1))
}

export async function parseJobDescription(title: string, description: string): Promise<ParsedJD> {
  const prompt = buildJdPrompt(title, description)
  const raw = await completeLLM(prompt)
  try {
    const parsed = extractJsonObject(raw) as Partial<ParsedJD>
    return normalizeParsedJD(parsed, title)
  } catch (e) {
    console.warn('JD parse failed, returning heuristic fallback:', e instanceof Error ? e.message : e)
    return heuristicParse(title, description)
  }
}

function normalizeParsedJD(p: Partial<ParsedJD>, fallbackTitle: string): ParsedJD {
  const arr = (v: unknown): string[] => Array.isArray(v) ? v.map(String).filter(Boolean) : []
  return {
    title: typeof p.title === 'string' && p.title ? p.title : fallbackTitle,
    department: typeof p.department === 'string' ? p.department : '',
    location: typeof p.location === 'string' ? p.location : '',
    employment_type: typeof p.employment_type === 'string' ? p.employment_type : '',
    experience_years_required: typeof p.experience_years_required === 'number' ? p.experience_years_required : 0,
    mandatory_skills: arr(p.mandatory_skills),
    preferred_skills: arr(p.preferred_skills),
    required_certifications: arr(p.required_certifications),
    education_required: typeof p.education_required === 'string' ? p.education_required : '',
    responsibilities: typeof p.responsibilities === 'string' ? p.responsibilities : '',
    soft_skills: arr(p.soft_skills),
    industry: typeof p.industry === 'string' ? p.industry : '',
    salary_range: typeof p.salary_range === 'string' ? p.salary_range : '',
    keywords: arr(p.keywords),
  }
}

// Used when LLM is unreachable — keeps the pipeline alive
function heuristicParse(title: string, description: string): ParsedJD {
  const text = description.toLowerCase()
  const expMatch = text.match(/(\d+)\+?\s*(?:years|yrs)/)
  const expYears = expMatch ? parseInt(expMatch[1], 10) : 0
  return {
    title, department: '', location: '', employment_type: '',
    experience_years_required: expYears,
    mandatory_skills: [], preferred_skills: [],
    required_certifications: [], education_required: '',
    responsibilities: description.slice(0, 1000),
    soft_skills: [], industry: '', salary_range: '', keywords: [],
  }
}

export async function persistParsedJD(pool: Pool, jobId: string, parsed: ParsedJD): Promise<void> {
  await pool.query(
    `UPDATE job_descriptions SET
       department = $1,
       employment_type = $2,
       location = COALESCE(NULLIF($3, ''), location),
       experience_years_required = COALESCE($4, experience_years_required),
       mandatory_skills = $5,
       preferred_skills = $6,
       required_certifications = $7,
       required_skills = $5 || $6,
       education_required = COALESCE(NULLIF($8, ''), education_required),
       responsibilities = $9,
       soft_skills = $10,
       industry = COALESCE(NULLIF($11, ''), industry),
       salary_range = $12,
       keywords = $13,
       parsed_json = $14,
       parsed_at = NOW(),
       updated_at = NOW()
     WHERE id = $15`,
    [
      parsed.department,
      parsed.employment_type,
      parsed.location,
      parsed.experience_years_required || null,
      parsed.mandatory_skills,
      parsed.preferred_skills,
      parsed.required_certifications,
      parsed.education_required,
      parsed.responsibilities,
      parsed.soft_skills,
      parsed.industry,
      parsed.salary_range,
      parsed.keywords,
      JSON.stringify(parsed),
      jobId,
    ],
  )
}

export const JD_VERSION = JD_PROMPT_VERSION
