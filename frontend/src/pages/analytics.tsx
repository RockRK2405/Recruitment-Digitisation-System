import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { analyticsApi } from '@/lib/api'
import { BarChart3, PieChart, TrendingUp, Users } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart as RechartsPie, Pie, Cell, Legend,
} from 'recharts'

const COLORS = ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444', '#ec4899']

export function AnalyticsPage() {
  const { data: skills, isLoading: skillsLoading } = useQuery({
    queryKey: ['analytics-skills'],
    queryFn: () => analyticsApi.skillDistribution().then((r) => r.data),
  })
  const { data: funnel, isLoading: funnelLoading } = useQuery({
    queryKey: ['analytics-funnel'],
    queryFn: () => analyticsApi.hiringFunnel().then((r) => r.data),
  })
  const { data: sources, isLoading: sourcesLoading } = useQuery({
    queryKey: ['analytics-sources'],
    queryFn: () => analyticsApi.sources().then((r) => r.data),
  })

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Analytics</h1>
        <p className="text-muted-foreground text-sm mt-1">Recruitment insights and pipeline metrics</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="h-4 w-4 text-primary" />
              Top Skills Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            {skillsLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : skills && (Array.isArray(skills) ? skills : []).length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={(Array.isArray(skills) ? skills : []).slice(0, 10)}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '0.5rem' }} />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <BarChart3 className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">No skill data yet</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4 text-primary" />
              Hiring Funnel
            </CardTitle>
          </CardHeader>
          <CardContent>
            {funnelLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : funnel && (Array.isArray(funnel) ? funnel : []).length > 0 ? (
              <div className="space-y-3 mt-2">
                {(Array.isArray(funnel) ? funnel : []).map((stage: { stage: string; count: number }, i: number) => {
                  const max = Math.max(...(Array.isArray(funnel) ? funnel : []).map((s: { count: number }) => s.count), 1)
                  return (
                    <div key={stage.stage}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="capitalize text-muted-foreground">{stage.stage}</span>
                        <span className="font-medium">{stage.count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${(stage.count / max) * 100}%`, backgroundColor: COLORS[i % COLORS.length] }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <TrendingUp className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">No funnel data yet</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <PieChart className="h-4 w-4 text-primary" />
              Candidate Sources
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sourcesLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : sources && (Array.isArray(sources) ? sources : []).length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <RechartsPie>
                  <Pie
                    data={Array.isArray(sources) ? sources : []}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    dataKey="count"
                    nameKey="source"
                    paddingAngle={3}
                  >
                    {(Array.isArray(sources) ? sources : []).map((_: unknown, index: number) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '0.5rem' }} />
                  <Legend />
                </RechartsPie>
              </ResponsiveContainer>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <PieChart className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">No source data yet</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4 text-primary" />
              Platform Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center h-64 text-center space-y-3">
              <Users className="h-10 w-10 text-muted-foreground/30" />
              <div>
                <p className="text-sm text-muted-foreground">More detailed analytics</p>
                <p className="text-xs text-muted-foreground">will appear as candidates are processed</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </motion.div>
  )
}
