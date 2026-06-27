import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { candidatesApi } from '@/lib/api'
import { getInitials } from '@/lib/utils'
import type { Candidate } from '@/types'
import { Search, Users, MapPin, Briefcase, ChevronRight, SlidersHorizontal } from 'lucide-react'

const statusColors: Record<string, string> = {
  new: 'bg-blue-500/10 text-blue-600',
  screening: 'bg-violet-500/10 text-violet-600',
  shortlisted: 'bg-amber-500/10 text-amber-600',
  interviewed: 'bg-orange-500/10 text-orange-600',
  offered: 'bg-emerald-500/10 text-emerald-600',
  hired: 'bg-green-500/10 text-green-700',
  rejected: 'bg-red-500/10 text-red-600',
}

export function CandidatesPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const { data, isLoading } = useQuery({
    queryKey: ['candidates', search, statusFilter],
    queryFn: () =>
      candidatesApi.list({ search: search || undefined, status: statusFilter !== 'all' ? statusFilter : undefined })
        .then((r) => r.data),
    staleTime: 15000,
  })

  const candidates: Candidate[] = Array.isArray(data) ? data : data?.data || []

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Candidates</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {isLoading ? 'Loading...' : `${candidates.length} candidates in system`}
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name, skill, domain..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full sm:w-44">
            <SlidersHorizontal className="h-4 w-4 mr-2 text-muted-foreground" />
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="new">New</SelectItem>
            <SelectItem value="screening">Screening</SelectItem>
            <SelectItem value="shortlisted">Shortlisted</SelectItem>
            <SelectItem value="interviewed">Interviewed</SelectItem>
            <SelectItem value="offered">Offered</SelectItem>
            <SelectItem value="hired">Hired</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="grid gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4 flex items-center gap-4">
                <Skeleton className="h-11 w-11 rounded-full" />
                <div className="flex-1"><Skeleton className="h-4 w-40" /><Skeleton className="h-3 w-60 mt-2" /></div>
                <Skeleton className="h-6 w-20" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : candidates.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Users className="h-14 w-14 text-muted-foreground/30 mb-4" />
          <h3 className="text-lg font-semibold">No candidates found</h3>
          <p className="text-sm text-muted-foreground mt-1">
            {search ? 'Try adjusting your search terms.' : 'Upload resumes to populate this list.'}
          </p>
          {!search && (
            <Button className="mt-4" onClick={() => navigate('/resumes')}>
              Upload Resumes
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-3">
          {candidates.map((c) => (
            <Card
              key={c.id}
              className="cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => navigate(`/candidates/${c.id}`)}
            >
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  <Avatar className="h-11 w-11 shrink-0">
                    <AvatarFallback className="bg-primary/10 text-primary text-sm font-medium">
                      {getInitials(c.name)}
                    </AvatarFallback>
                  </Avatar>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold truncate">{c.name}</span>
                      <Badge
                        className={`text-xs capitalize ${statusColors[c.status] || 'bg-muted text-muted-foreground'}`}
                        variant="secondary"
                      >
                        {c.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground flex-wrap">
                      {c.primaryDomain && (
                        <span className="flex items-center gap-1">
                          <Briefcase className="h-3 w-3" />{c.primaryDomain}
                        </span>
                      )}
                      {c.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3" />{c.location}
                        </span>
                      )}
                      {c.experienceYears != null && (
                        <span>{c.experienceYears} yrs exp</span>
                      )}
                    </div>
                    {c.skills && c.skills.length > 0 && (
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {(c.skills as string[]).slice(0, 4).map((s: string) => (
                          <Badge key={s} variant="secondary" className="text-[10px] px-1.5 py-0">{s}</Badge>
                        ))}
                        {(c.skills as string[]).length > 4 && (
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                            +{(c.skills as string[]).length - 4}
                          </Badge>
                        )}
                      </div>
                    )}
                  </div>

                  {c.matchScore != null && (
                    <div className="shrink-0 text-right">
                      <p className={`text-lg font-bold ${c.matchScore >= 80 ? 'text-emerald-500' : c.matchScore >= 60 ? 'text-amber-500' : 'text-muted-foreground'}`}>
                        {c.matchScore}%
                      </p>
                      <p className="text-[10px] text-muted-foreground">match</p>
                    </div>
                  )}

                  <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </motion.div>
  )
}
