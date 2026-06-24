export interface User {
  id: string
  username: string
  display_name: string
  email: string
  password_hash: string
  role: 'admin' | 'recruiter' | 'viewer'
  is_active: boolean
  created_at: string
}

export interface Candidate {
  id: string
  name: string
  email: string
  phone: string
  location: string
  status: string
  experience_years: number
  primary_domain: string
  education: string
  profile_completeness: number
  ai_summary?: string
  created_at: string
  updated_at: string
}

export interface JobDescription {
  id: string
  title: string
  description: string
  required_skills: string[]
  required_certifications: string[]
  location: string
  experience_years_required: number
  education_required: string
  industry: string
  status: 'active' | 'closed' | 'draft'
  created_at: string
  updated_at: string
}

export interface MatchResult {
  id: string
  candidate_id: string
  job_id: string
  vector_score: number
  skill_score: number
  certification_score: number
  overall_score: number
  match_explanation: string
  missing_skills: string[]
  matched_skills: string[]
  ranking: number
}

export interface UploadedDocument {
  id: string
  filename: string
  filepath: string
  mime_type: string
  ocr_text?: string
  ocr_confidence: number
  status: string
  doc_type: string
  created_at: string
}

export interface DashboardMetrics {
  total_candidates: number
  active_jobs: number
  candidates_screened: number
  candidates_shortlisted: number
  average_match_score: number
  hiring_velocity: number
  recent_activity: ActivityItem[]
}

export interface ActivityItem {
  id: string
  type: string
  message: string
  timestamp: string
  user_id: string
}

export interface PaginatedQuery {
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  search?: string
  status?: string
  domain?: string
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AiPipelineRequest {
  candidate_id: string
  pipeline_type: 'full' | 'ocr_only' | 'parse_only'
}

export interface ChatRequest {
  message: string
  session_id?: string
}

export interface ChatResponse {
  response: string
  session_id: string
  sources?: string[]
}
