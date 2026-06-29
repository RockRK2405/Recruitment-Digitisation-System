import axios, { type AxiosError, type AxiosInstance } from 'axios'
import { useAuthStore } from './store'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          useAuthStore.getState().logout()
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  get clientApi(): AxiosInstance {
    return this.client
  }
}

export const api = new ApiClient().clientApi

export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
  refresh: () => api.post('/auth/refresh'),
}

export const candidatesApi = {
  list: (params?: Record<string, unknown>) =>
    api.get('/candidates', { params }),
  get: (id: string) => api.get(`/candidates/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/candidates/${id}`, data),
  delete: (id: string) => api.delete(`/candidates/${id}`),
  timeline: (id: string) => api.get(`/candidates/${id}/timeline`),
  tags: (id: string) => api.get(`/candidates/${id}/tags`),
  listNotes: (id: string) => api.get(`/candidates/${id}/notes`),
  createNote: (id: string, body: string) => api.post(`/candidates/${id}/notes`, { body }),
  updateNote: (id: string, noteId: string, body: string) => api.patch(`/candidates/${id}/notes/${noteId}`, { body }),
  deleteNote: (id: string, noteId: string) => api.delete(`/candidates/${id}/notes/${noteId}`),
}

export const jobsApi = {
  list: (params?: Record<string, unknown>) => api.get('/jobs', { params }),
  get: (id: string) => api.get(`/jobs/${id}`),
  create: (data: Record<string, unknown>) => api.post('/jobs', data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/jobs/${id}`, data),
  delete: (id: string) => api.delete(`/jobs/${id}`),
  generateSuggestion: (prompt: string) =>
    api.post('/jobs/generate-suggestion', { prompt }),
}

export const matchingApi = {
  rank: (jobId: string) => api.get(`/matching/rank/${jobId}`),
  score: (candidateId: string, jobId: string) =>
    api.get(`/matching/score`, { params: { candidateId, jobId } }),
  semanticSearch: (query: string, params?: Record<string, unknown>) =>
    api.post('/matching/semantic', { query, ...params }),
  recommendations: (candidateId: string) =>
    api.get(`/matching/recommendations/${candidateId}`),
  explain: (candidateId: string, jobId: string) =>
    api.get(`/matching/explain/${candidateId}/${jobId}`),
  evaluate: (jobId: string, opts?: { prefilterTopN?: number; llmTopN?: number; forceReeval?: boolean }) =>
    api.post(`/matching/evaluate/${jobId}`, opts || {}),
  parseJob: (jobId: string) => api.post(`/jobs/${jobId}/parse`),
}

export const settingsApi = {
  getWeights: () => api.get('/settings/weights'),
  updateWeights: (weights: Record<string, number>) => api.put('/settings/weights', { weights }),
}

export const resumesApi = {
  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/resumes/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  bulkUpload: (files: File[]) => {
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))
    return api.post('/resumes/bulk-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  profile: (id: string) => api.get(`/resumes/profile/${id}`),
  document: (id: string) => api.get(`/resumes/document/${id}`),
  ocrStatus: (id: string) => api.get(`/resumes/ocr-status/${id}`),
}

export const analyticsApi = {
  summary: () => api.get('/analytics/summary'),
  skillDistribution: () => api.get('/analytics/skills'),
  hiringFunnel: () => api.get('/analytics/funnel'),
  velocity: () => api.get('/analytics/velocity'),
  departmentTrends: () => api.get('/analytics/departments'),
  sources: () => api.get('/analytics/sources'),
}

export const agentApi = {
  chat: (message: string) => api.post('/agent/chat', { message }),
  logs: (runId?: string) => api.get('/agent/logs', { params: { runId } }),
  status: (runId: string) => api.get(`/agent/status/${runId}`),
  pipeline: (candidateId: string) =>
    api.post('/agent/pipeline', { candidateId }),
}

export const dashboardApi = {
  metrics: () => api.get('/dashboard/metrics'),
  activity: () => api.get('/dashboard/activity'),
}

export const documentsApi = {
  uploadBatch: (files: File[], candidateId?: string) => {
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))
    if (candidateId) formData.append('candidateId', candidateId)
    return api.post('/documents/upload-batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  classify: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/documents/classify', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: (candidateId: string) =>
    api.get(`/documents/candidate/${candidateId}`),
}
