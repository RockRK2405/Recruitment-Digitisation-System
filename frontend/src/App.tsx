import { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/lib/store'
import { authApi } from '@/lib/api'
import { AppLayout } from '@/components/layout/app-layout'
import { ProtectedRoute } from '@/components/shared/protected-route'
import { LoginPage } from '@/pages/login'

const DashboardPage = lazy(() => import('@/pages/dashboard').then(m => ({ default: m.DashboardPage })))
const CandidatesPage = lazy(() => import('@/pages/candidates').then(m => ({ default: m.CandidatesPage })))
const CandidateProfilePage = lazy(() => import('@/pages/candidate-profile').then(m => ({ default: m.CandidateProfilePage })))
const JobsPage = lazy(() => import('@/pages/jobs').then(m => ({ default: m.JobsPage })))
const ResumesPage = lazy(() => import('@/pages/resumes').then(m => ({ default: m.ResumesPage })))
const MatchingPage = lazy(() => import('@/pages/matching').then(m => ({ default: m.MatchingPage })))
const AnalyticsPage = lazy(() => import('@/pages/analytics').then(m => ({ default: m.AnalyticsPage })))
const AgentPage = lazy(() => import('@/pages/agent').then(m => ({ default: m.AgentPage })))
const SettingsPage = lazy(() => import('@/pages/settings').then(m => ({ default: m.SettingsPage })))

function PageLoader() {
  return (
    <div className="flex h-full items-center justify-center p-12">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

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
        <Route path="dashboard" element={<Suspense fallback={<PageLoader />}><DashboardPage /></Suspense>} />
        <Route path="candidates" element={<Suspense fallback={<PageLoader />}><CandidatesPage /></Suspense>} />
        <Route path="candidates/:id" element={<Suspense fallback={<PageLoader />}><CandidateProfilePage /></Suspense>} />
        <Route path="jobs" element={<Suspense fallback={<PageLoader />}><JobsPage /></Suspense>} />
        <Route path="resumes" element={<Suspense fallback={<PageLoader />}><ResumesPage /></Suspense>} />
        <Route path="matching" element={<Suspense fallback={<PageLoader />}><MatchingPage /></Suspense>} />
        <Route path="analytics" element={<Suspense fallback={<PageLoader />}><AnalyticsPage /></Suspense>} />
        <Route path="agent" element={<Suspense fallback={<PageLoader />}><AgentPage /></Suspense>} />
        <Route path="settings" element={<Suspense fallback={<PageLoader />}><SettingsPage /></Suspense>} />
      </Route>
      <Route path="*" element={<Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />} />
    </Routes>
  )
}
