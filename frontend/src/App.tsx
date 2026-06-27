import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/lib/store'
import { authApi } from '@/lib/api'
import { AppLayout } from '@/components/layout/app-layout'
import { ProtectedRoute } from '@/components/shared/protected-route'
import { LoginPage } from '@/pages/login'
import { DashboardPage } from '@/pages/dashboard'
import { CandidatesPage } from '@/pages/candidates'
import { CandidateProfilePage } from '@/pages/candidate-profile'
import { JobsPage } from '@/pages/jobs'
import { ResumesPage } from '@/pages/resumes'
import { MatchingPage } from '@/pages/matching'
import { AnalyticsPage } from '@/pages/analytics'
import { AgentPage } from '@/pages/agent'
import { SettingsPage } from '@/pages/settings'

export default function App() {
  const { setAuth, logout, setLoading, isAuthenticated } = useAuthStore()

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }
    authApi.me()
      .then((res) => setAuth(res.data, token))
      .catch(() => {
        logout()
      })
  }, [])

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="candidates" element={<CandidatesPage />} />
        <Route path="candidates/:id" element={<CandidateProfilePage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="resumes" element={<ResumesPage />} />
        <Route path="matching" element={<MatchingPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="agent" element={<AgentPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />} />
    </Routes>
  )
}
