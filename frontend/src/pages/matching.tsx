import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { matchingApi, jobsApi } from '@/lib/api'
import { getInitials } from '@/lib/utils'
import type { JobDescription, MatchResult } from '@/types'
import { GitCompare, MapPin, Briefcase, Star, Search, Brain } from 'lucide-react'

export function MatchingPage() {
  const [selectedJob, setSelectedJob] = useState<string>('')
  const [semanticQuery, setSemanticQuery] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list().then((r) => r.data),
  })
  const jobs: JobDescription[] = Array.isArray(jobsData) ? jobsData : jobsData?.data || []

  const { data: rankings, isLoading: rankLoading } = useQuery({
    queryKey: ['matching-rank', selectedJob],
    queryFn: () => matchingApi.rank(selectedJob).then((r) => r.data),
    enabled: !!selectedJob,
  })

  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['semantic-search', searchQuery],
    queryFn: () => matchingApi.semanticSearch(searchQuery).then((r) => r.data),
    enabled: !!searchQuery,
    staleTime: 5000,
  })

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">AI Matching</h1>
        <p className="text-muted-foreground text-sm mt-1">Semantic candidate ranking and intelligent search</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <GitCompare className="h-4 w-4 text-primary" />
              Rank Candidates for Job
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select value={selectedJob} onValueChange={setSelectedJob}>
              <SelectTrigger>
                <SelectValue placeholder={jobsLoading ? 'Loading jobs...' : 'Select a job description'} />
              </SelectTrigger>
              <SelectContent>
                {jobs.map((j) => (
                  <SelectItem key={j.id} value={String(j.id)}>{j.title}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {rankLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-10 w-10 rounded-full" />
                    <div className="flex-1"><Skeleton className="h-4 w-40" /><Skeleton className="h-3 w-24 mt-1" /></div>
                    <Skeleton className="h-6 w-12" />
                  </div>
                ))}
              </div>
            ) : rankings && rankings.length > 0 ? (
              <div className="space-y-3">
                {(rankings as MatchResult[]).map((r, idx) => (
                  <div key={r.id} className="rounded-lg border p-3 hover:border-primary/50 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold
                        ${idx === 0 ? 'bg-amber-500 text-white' : idx === 1 ? 'bg-slate-400 text-white' : idx === 2 ? 'bg-amber-700 text-white' : 'bg-muted text-muted-foreground'}`}>
                        {idx + 1}
                      </div>
                      <Avatar className="h-9 w-9 shrink-0">
                        <AvatarFallback className="bg-primary/10 text-primary text-xs">
                          {getInitials(r.candidate?.name || '')}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{r.candidate?.name}</p>
                        <div className="flex gap-2 text-xs text-muted-foreground flex-wrap">
                          {r.candidate?.primaryDomain && <span className="flex items-center gap-1"><Briefcase className="h-3 w-3" />{r.candidate.primaryDomain}</span>}
                          {r.candidate?.location && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{r.candidate.location}</span>}
                        </div>
                        <div className="flex gap-3 mt-1">
                          <span className="text-[10px] text-muted-foreground">Skills {r.skillScore}%</span>
                          <span className="text-[10px] text-muted-foreground">Semantic {r.vectorScore}%</span>
                          <span className="text-[10px] text-muted-foreground">Certs {r.certificationScore}%</span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className={`text-xl font-bold ${r.overallScore >= 80 ? 'text-emerald-500' : r.overallScore >= 60 ? 'text-amber-500' : 'text-muted-foreground'}`}>
                          {r.overallScore}%
                        </p>
                        <Progress value={r.overallScore} className="w-16 h-1.5 mt-1" />
                      </div>
                    </div>
                    {r.matchExplanation && (
                      <p className="text-xs text-muted-foreground mt-2 pl-12 line-clamp-2">{r.matchExplanation}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : selectedJob ? (
              <div className="flex flex-col items-center py-10 text-center">
                <Star className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">No matches found for this job.</p>
                <p className="text-xs text-muted-foreground mt-1">Upload candidate resumes first.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center py-10 text-center">
                <GitCompare className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">Select a job to rank candidates</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Brain className="h-4 w-4 text-primary" />
              Semantic Search
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={(e) => { e.preventDefault(); setSearchQuery(semanticQuery) }} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pl-9"
                  placeholder="e.g. DGMS certified mining engineer 10 years..."
                  value={semanticQuery}
                  onChange={(e) => setSemanticQuery(e.target.value)}
                />
              </div>
              <Button type="submit">Search</Button>
            </form>

            {searchLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-10 w-10 rounded-full" />
                    <div className="flex-1"><Skeleton className="h-4 w-40" /><Skeleton className="h-3 w-24 mt-1" /></div>
                  </div>
                ))}
              </div>
            ) : searchResults && (searchResults as unknown[]).length > 0 ? (
              <div className="space-y-2">
                {(searchResults as Array<{ id: string; name: string; primaryDomain: string; location: string; experienceYears: number; skills: string[] }>).map((c) => (
                  <div key={c.id} className="rounded-lg border p-3 hover:border-primary/50 transition-colors">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-9 w-9 shrink-0">
                        <AvatarFallback className="bg-primary/10 text-primary text-xs">{getInitials(c.name)}</AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{c.name}</p>
                        <div className="flex gap-2 text-xs text-muted-foreground">
                          {c.primaryDomain && <span>{c.primaryDomain}</span>}
                          {c.experienceYears && <span>· {c.experienceYears} yrs</span>}
                        </div>
                        {c.skills && c.skills.length > 0 && (
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {(Array.isArray(c.skills) ? c.skills : (c.skills as string).split(',')).slice(0, 3).map((s: string) => (
                              <Badge key={s} variant="secondary" className="text-[10px]">{s.trim()}</Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : searchQuery ? (
              <div className="flex flex-col items-center py-10 text-center">
                <Search className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">No candidates matched your search.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center py-10 text-center">
                <Brain className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">Enter a search query to find candidates</p>
                <p className="text-xs text-muted-foreground mt-1">Uses semantic similarity across skills, domain, and experience</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </motion.div>
  )
}
