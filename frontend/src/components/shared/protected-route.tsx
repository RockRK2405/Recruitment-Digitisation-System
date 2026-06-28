// Auth disabled — all routes are publicly accessible
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
