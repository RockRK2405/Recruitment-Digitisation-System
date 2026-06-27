import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { dashboardApi } from '@/lib/api'
import {
  Users, Briefcase, CheckCircle, Brain, Activity, FileText, TrendingUp,
} from 'lucide-react'

const statCards = [
  { key: 'totalCandidates', label: 'Total Candidates', icon: Users, color: 'text-blue-500', bg: 'bg-blue-500/10' },
  { key: 'activeJobs', label: 'Active Jobs', icon: Briefcase, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  { key: 'candidatesScreened', label: 'Screened', icon: CheckCircle, color: 'text-violet-500', bg: 'bg-violet-500/10' },
  { key: 'averageMatchScore', label: 'Avg Match Score', icon: Brain, color: 'text-amber-500', bg: 'bg-amber-500/10', suffix: '%' },
]

export function DashboardPage() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['dashboard-metrics'],
    queryFn: () => dashboardApi.metrics().then((r) => r.data),
  })
  const { data: activity, isLoading: activityLoading } = useQuery({
    queryKey: ['dashboard-activity'],
    queryFn: () => dashboardApi.activity().then((r) => r.data),
  })

  const stats = metrics || {
    totalCandidates: 0, activeJobs: 0, candidatesScreened: 0,
    candidatesShortlisted: 0, averageMatchScore: 0, hiringVelocity: 0,
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">Industrial Recruitment Intelligence Overview</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((s) => (
          <Card key={s.key}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{s.label}</p>
                  {isLoading ? (
                    <Skeleton className="h-8 w-24 mt-1" />
                  ) : (
                    <p className="text-3xl font-bold mt-1">
                      {(stats[s.key as keyof typeof stats] as number)?.toLocaleString()}{s.suffix || ''}
                    </p>
                  )}
                </div>
                <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${s.bg}`}>
                  <s.icon className={`h-6 w-6 ${s.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-primary" />
              Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            {activityLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-8 w-8 rounded-full" />
                    <div className="flex-1"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-3 w-1/2 mt-1" /></div>
                  </div>
                ))}
              </div>
            ) : activity && activity.length > 0 ? (
              <div className="space-y-3">
                {activity.map((item: { id: string; type: string; message: string; timestamp: string }) => (
                  <div key={item.id} className="flex items-start gap-3 rounded-lg p-2 hover:bg-muted/50 transition-colors">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
                      <FileText className="h-4 w-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm">{item.message}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{new Date(item.timestamp).toLocaleString()}</p>
                    </div>
                    <Badge variant="outline" className="text-xs shrink-0 capitalize">
                      {item.type.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Activity className="h-10 w-10 text-muted-foreground/40 mb-3" />
                <p className="text-sm text-muted-foreground">No recent activity</p>
                <p className="text-xs text-muted-foreground mt-1">Upload resumes to get started</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4 text-primary" />
              Pipeline Summary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { label: 'New', value: stats.totalCandidates, color: 'bg-blue-500' },
              { label: 'Screening', value: stats.candidatesScreened, color: 'bg-violet-500' },
              { label: 'Shortlisted', value: stats.candidatesShortlisted, color: 'bg-amber-500' },
              { label: 'Avg Match', value: stats.averageMatchScore, color: 'bg-emerald-500', suffix: '%' },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`h-2 w-2 rounded-full ${item.color}`} />
                  <span className="text-sm text-muted-foreground">{item.label}</span>
                </div>
                {isLoading ? (
                  <Skeleton className="h-4 w-12" />
                ) : (
                  <span className="text-sm font-medium">{(item.value as number)?.toLocaleString()}{item.suffix || ''}</span>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </motion.div>
  )
}
