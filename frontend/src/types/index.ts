export interface User {
  id: string
  username: string
  displayName: string
  email: string
  role: 'admin' | 'recruiter' | 'viewer'
  avatar?: string
  isActive: boolean
  createdAt: string
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

export interface Candidate {
  id: string
  name: string
  email: string
  phone: string
  location: string
  status: 'new' | 'screening' | 'shortlisted' | 'interviewed' | 'offered' | 'hired' | 'rejected'
  experienceYears: number
  skills: string[]
  primaryDomain: string
  education: string
  certifications: Certification[]
  matchScore?: number
  profileCompleteness: number
  avatar?: string
  tags: string[]
  createdAt: string
  updatedAt: string
}

export interface Certification {
  id: string
  name: string
  issuer: string
  issueDate: string
  expiryDate: string
  registrationNumber: string
  isSafetyCritical: boolean
  verificationStatus: 'pending' | 'verified' | 'failed'
}

export interface JobDescription {
  id: string
  title: string
  description: string
  requiredSkills: string[]
  requiredCertifications: string[]
  location: string
  experienceYearsRequired: number
  educationRequired: string
  industry: string
  status: 'active' | 'closed' | 'draft'
  candidateCount: number
  createdAt: string
  updatedAt: string
}

export interface MatchResult {
  id: string
  candidateId: string
  jobId: string
  candidate: Candidate
  job: JobDescription
  vectorScore: number
  skillScore: number
  certificationScore: number
  overallScore: number
  matchExplanation: string
  missingSkills: string[]
  matchedSkills: string[]
  ranking: number
}

export interface DashboardMetrics {
  totalCandidates: number
  activeJobs: number
  candidatesScreened: number
  candidatesShortlisted: number
  averageMatchScore: number
  hiringVelocity: number
  recentActivity: ActivityItem[]
}

export interface ActivityItem {
  id: string
  type: 'candidate_added' | 'match_completed' | 'jd_created' | 'shortlist' | 'interview'
  message: string
  timestamp: string
  userId: string
}

export interface AgentLog {
  id: string
  runId: string
  agentName: string
  message: string
  stateSnapshot: Record<string, unknown>
  timestamp: string
}

export interface AnalyticsData {
  skillDistribution: { name: string; count: number }[]
  candidateSources: { source: string; count: number }[]
  hiringFunnel: { stage: string; count: number }[]
  recruitmentVelocity: { month: string; hires: number; applications: number }[]
  departmentTrends: { department: string; candidates: number; hired: number }[]
  domainDistribution: { domain: string; count: number }[]
}

export interface ResumeUploadResult {
  candidateId: string
  status: 'processing' | 'completed' | 'failed'
  parsedData: Partial<Candidate>
  ocrConfidence: number
  errors: string[]
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export interface ApiError {
  message: string
  code: string
  status: number
}
