import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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
import type { JobDescription } from '@/types'
import {
  GitCompare, MapPin, Briefcase, Star, Search, Brain, Sparkles,
  CheckCircle2, AlertTriangle, Lightbulb, RefreshCw, Filter,
} from 'lucide-react'
import toast from 'react-hot-toast'

interface RankedCandidate {
  id: string
  candidateId: string
  ranking: number
  overallScore: number
  llmScore: number
  skillScore: number
  experienceMatch: number
  educationMatch: number
  certificationScore: number
  industryMatch: number
  leadershipScore: number
  communicationScore: number
  growthScore: number
  resumeQuality: number
  strengths: string[]
  weaknesses: string[]
  missingSkills: string[]
  matchedSkills: string[]
  interviewFocus: string[]
  recommendation: string | null
  llmSummary: string | null
  matchExplanation: string | null
  llmModelUsed: string | null
  evaluatedAt: string | null
  stage: 'prefilter' | 'llm'
  candidate: {
    id: string
    name: string
    email: string
    location: string
    status: string
    primaryDomain: string
    experienceYears: number
    skills: string[]
  }
}

const RECOMMENDATION_STYLES: Record<string, string> = {
  'Highly Recommended': 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30',
  'Recommended': 'bg-blue-500/10 text-blue-600 border-blue-500/30',
  'Recommended with Training': 'bg-amber-500/10 text-amber-600 border-amber-500/30',
  'Potential Candidate': 'bg-violet-500/10 text-violet-600 border-violet-500/30',
  'Not Recommended': 'bg-red-500/10 text-red-600 border-red-500/30',
}

function scoreColor(s: number): string {
  if (s >= 85) return 'text-emerald-500'
  if (s >= 70) return 'text-blue-500'
  if (s >= 55) return 'text-amber-500'
  return 'text-muted-foreground'
}

export function MatchingPage() {
  const qc = useQueryClient()
  const [selectedJob, setSelectedJob] = useState<string>('')
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null)
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [minScore, setMinScore] = useState(0)
  const [search, setSearch] = useState('')

  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list().then((r) => r.data),
  })
  const jobs: JobDescription[] = Array.isArray(jobsData) ? jobsData : jobsData?.data || []

  const { data: rankings = [], isLoading: rankLoading, refetch: refetchRankings } = useQuery<RankedCandidate[]>({
    queryKey: ['matching-rank', selectedJob],
    queryFn: () => matchingApi.rank(selectedJob).then((r) => r.data),
    enabled: !!selectedJob,
  })

  const evaluate = useMutation({
    mutationFn: (opts: { forceReeval?: boolean }) =>
      matchingApi.evaluate(selectedJob, { llmTopN: 20, prefilterTopN: 20, forceReeval: opts.forceReeval }),
    onSuccess: (r) => {
      toast.success(`Evaluated ${r.data.totalCandidates} candidates (LLM: ${r.data.llmEvaluated})`)
      qc.invalidateQueries({ queryKey: ['matching-rank', selectedJob] })
    },
    onError: () => toast.error('Evaluation failed'),
  })

  const parseJob = useMutation({
    mutationFn: () => matchingApi.parseJob(selectedJob),
    onSuccess: () => {
      toast.success('Job description re-parsed; re-ranking in background')
      setTimeout(() => refetchRankings(), 2000)
    },
    onError: () => toast.error('Parse failed'),
  })

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase()
    return rankings.filter((r) => {
      if (r.overallScore < minScore) return false
      if (s && !(r.candidate.name || '').toLowerCase().includes(s) &&
          !(r.candidate.primaryDomain || '').toLowerCase().includes(s)) return false
      return true
    })
  }, [rankings, minScore, search])

  const selectedCandidate = selectedCandidateId
    ? rankings.find((r) => r.candidateId === selectedCandidateId)
    : null

  const comparison = compareIds.map((id) => rankings.find((r) => r.candidateId === id)).filter(Boolean) as RankedCandidate[]

  const toggleCompare = (id: string) => {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= 3) {
        toast('Max 3 candidates for side-by-side')
        return prev
      }
      return [...prev, id]
    })
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">AI Matching</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Hybrid LLM + structured scoring ranks every candidate against the selected job.
          </p>
        </div>
        <div className="flex items-end gap-2">
          <Select value={selectedJob} onValueChange={(v) => { setSelectedJob(v); setSelectedCandidateId(null); setCompareIds([]) }}>
            <SelectTrigger className="w-72">
              <SelectValue placeholder={jobsLoading ? 'Loading jobs...' : 'Select a job description'} />
            </SelectTrigger>
            <SelectContent>
              {jobs.map((j) => (
                <SelectItem key={j.id} value={String(j.id)}>{j.title}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            disabled={!selectedJob || parseJob.isPending}
            onClick={() => parseJob.mutate()}
            title="Re-parse the JD with the LLM (also re-runs matching)"
          >
            <Sparkles className="h-4 w-4 mr-1.5" />
            {parseJob.isPending ? 'Parsing...' : 'Re-parse JD'}
          </Button>
          <Button
            size="sm"
            disabled={!selectedJob || evaluate.isPending}
            onClick={() => evaluate.mutate({ forceReeval: true })}
            title="Force LLM re-evaluation for the top 20 candidates"
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${evaluate.isPending ? 'animate-spin' : ''}`} />
            {evaluate.isPending ? 'Evaluating...' : 'Run Evaluation'}
          </Button>
        </div>
      </div>

      {!selectedJob ? (
        <Card>
          <CardContent className="flex flex-col items-center py-20 text-center">
            <GitCompare className="h-12 w-12 text-muted-foreground/30 mb-3" />
            <p className="text-sm text-muted-foreground">Select a job above to rank candidates with AI</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-5">
          <Card className="lg:col-span-2">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <GitCompare className="h-4 w-4 text-primary" />
                  Ranked Candidates
                </CardTitle>
                <Badge variant="outline" className="text-xs">{filtered.length} of {rankings.length}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="pl-8 h-8 text-sm"
                    placeholder="Filter by name or domain..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <Select value={String(minScore)} onValueChange={(v) => setMinScore(parseInt(v, 10))}>
                  <SelectTrigger className="w-28 h-8 text-xs">
                    <Filter className="h-3 w-3" />
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">Any score</SelectItem>
                    <SelectItem value="50">≥ 50%</SelectItem>
                    <SelectItem value="70">≥ 70%</SelectItem>
                    <SelectItem value="85">≥ 85%</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {rankLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-20" />
                  ))}
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center py-10 text-center">
                  <Star className="h-10 w-10 text-muted-foreground/30 mb-3" />
                  <p className="text-sm text-muted-foreground">No matches yet for this job.</p>
                  <p className="text-xs text-muted-foreground mt-1">Click "Run Evaluation" to score candidates.</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[640px] overflow-y-auto pr-1">
                  {filtered.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => setSelectedCandidateId(r.candidateId)}
                      className={`w-full text-left rounded-lg border p-3 transition-colors ${selectedCandidateId === r.candidateId ? 'border-primary bg-primary/5' : 'hover:border-primary/40'}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${r.ranking === 1 ? 'bg-amber-500 text-white' : r.ranking === 2 ? 'bg-slate-400 text-white' : r.ranking === 3 ? 'bg-amber-700 text-white' : 'bg-muted text-muted-foreground'}`}>
                          {r.ranking}
                        </div>
                        <Avatar className="h-9 w-9 shrink-0">
                          <AvatarFallback className="bg-primary/10 text-primary text-xs">
                            {getInitials(r.candidate?.name || '')}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium truncate">{r.candidate?.name || 'Unknown'}</p>
                            {r.stage === 'llm' && <Badge variant="secondary" className="text-[9px] h-4 px-1">AI</Badge>}
                          </div>
                          <div className="flex gap-2 text-[10px] text-muted-foreground flex-wrap">
                            {r.candidate?.primaryDomain && <span className="flex items-center gap-0.5"><Briefcase className="h-3 w-3" />{r.candidate.primaryDomain}</span>}
                            {r.candidate?.location && <span className="flex items-center gap-0.5"><MapPin className="h-3 w-3" />{r.candidate.location}</span>}
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <p className={`text-xl font-bold ${scoreColor(r.overallScore)}`}>{r.overallScore}</p>
                          <Progress value={r.overallScore} className="w-12 h-1 mt-0.5" />
                        </div>
                      </div>
                      <div className="flex items-center justify-between mt-2 pl-9">
                        {r.recommendation && (
                          <Badge variant="outline" className={`text-[9px] h-4 px-1.5 ${RECOMMENDATION_STYLES[r.recommendation] || ''}`}>
                            {r.recommendation}
                          </Badge>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleCompare(r.candidateId) }}
                          className={`text-[10px] ${compareIds.includes(r.candidateId) ? 'text-primary font-medium' : 'text-muted-foreground hover:text-foreground'}`}
                        >
                          {compareIds.includes(r.candidateId) ? '✓ in compare' : '+ compare'}
                        </button>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <div className="lg:col-span-3 space-y-6">
            {comparison.length >= 2 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <GitCompare className="h-4 w-4 text-primary" /> Side-by-side
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-muted-foreground">
                          <th className="py-1 pr-2">Metric</th>
                          {comparison.map((c) => (
                            <th key={c.id} className="py-1 px-2 font-normal">{c.candidate.name}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ['Overall', 'overallScore'],
                          ['Skills', 'skillScore'],
                          ['Experience', 'experienceMatch'],
                          ['Education', 'educationMatch'],
                          ['Certifications', 'certificationScore'],
                          ['Industry', 'industryMatch'],
                          ['Resume Quality', 'resumeQuality'],
                          ['Growth', 'growthScore'],
                        ].map(([label, key]) => (
                          <tr key={label} className="border-t">
                            <td className="py-1.5 pr-2 text-xs text-muted-foreground">{label}</td>
                            {comparison.map((c) => (
                              <td key={c.id} className={`py-1.5 px-2 font-medium ${scoreColor((c as unknown as Record<string, number>)[key])}`}>
                                {(c as unknown as Record<string, number>)[key]}%
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            {selectedCandidate ? (
              <CandidateDetail r={selectedCandidate} />
            ) : (
              <Card>
                <CardContent className="flex flex-col items-center py-20 text-center">
                  <Brain className="h-12 w-12 text-muted-foreground/30 mb-3" />
                  <p className="text-sm text-muted-foreground">Select a candidate from the list</p>
                  <p className="text-xs text-muted-foreground mt-1">to view full AI evaluation breakdown</p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </motion.div>
  )
}

function CandidateDetail({ r }: { r: RankedCandidate }) {
  const breakdown = [
    { label: 'Skills', value: r.skillScore },
    { label: 'Experience', value: r.experienceMatch },
    { label: 'Education', value: r.educationMatch },
    { label: 'Certifications', value: r.certificationScore },
    { label: 'Industry', value: r.industryMatch },
    { label: 'Leadership', value: r.leadershipScore },
    { label: 'Communication', value: r.communicationScore },
    { label: 'Growth', value: r.growthScore },
    { label: 'Resume Quality', value: r.resumeQuality },
  ]

  return (
    <Card>
      <CardContent className="p-6 space-y-5">
        <div className="flex items-start gap-4">
          <Avatar className="h-14 w-14">
            <AvatarFallback className="bg-primary/10 text-primary">{getInitials(r.candidate.name)}</AvatarFallback>
          </Avatar>
          <div className="flex-1">
            <h2 className="text-lg font-bold">{r.candidate.name}</h2>
            <div className="flex gap-2 text-xs text-muted-foreground flex-wrap mt-1">
              {r.candidate.primaryDomain && <span>{r.candidate.primaryDomain}</span>}
              {r.candidate.experienceYears > 0 && <span>· {r.candidate.experienceYears} yrs</span>}
              {r.candidate.location && <span>· {r.candidate.location}</span>}
            </div>
            {r.recommendation && (
              <Badge variant="outline" className={`mt-2 ${RECOMMENDATION_STYLES[r.recommendation] || ''}`}>
                {r.recommendation}
              </Badge>
            )}
          </div>
          <div className="text-right">
            <p className={`text-4xl font-bold ${scoreColor(r.overallScore)}`}>{r.overallScore}</p>
            <p className="text-xs text-muted-foreground">overall match</p>
          </div>
        </div>

        {r.llmSummary && (
          <div className="rounded-lg bg-primary/5 border border-primary/10 p-3">
            <div className="flex gap-2">
              <Sparkles className="h-4 w-4 text-primary shrink-0 mt-0.5" />
              <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap">{r.llmSummary}</p>
            </div>
          </div>
        )}

        <div>
          <h3 className="text-sm font-semibold mb-2">Score Breakdown</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {breakdown.map((b) => (
              <div key={b.label}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-muted-foreground">{b.label}</span>
                  <span className={`font-medium tabular-nums ${scoreColor(b.value)}`}>{b.value}%</span>
                </div>
                <Progress value={b.value} className="h-1.5" />
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {r.strengths.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" /> Strengths
              </h3>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {r.strengths.map((s, i) => (
                  <li key={i} className="flex gap-1.5"><span className="text-emerald-500">·</span>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {r.weaknesses.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                <AlertTriangle className="h-4 w-4 text-amber-500" /> Gaps
              </h3>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {r.weaknesses.map((w, i) => (
                  <li key={i} className="flex gap-1.5"><span className="text-amber-500">·</span>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {r.missingSkills.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold mb-2">Skill Gap</h3>
            <div className="flex flex-wrap gap-1.5">
              {r.missingSkills.map((s) => (
                <Badge key={s} variant="outline" className="text-xs text-amber-600 border-amber-500/30">{s}</Badge>
              ))}
            </div>
          </div>
        )}

        {r.interviewFocus.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
              <Lightbulb className="h-4 w-4 text-blue-500" /> Suggested Interview Focus
            </h3>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {r.interviewFocus.map((f, i) => (
                <li key={i} className="flex gap-1.5"><span className="text-blue-500">·</span>{f}</li>
              ))}
            </ul>
          </div>
        )}

        {r.evaluatedAt && (
          <p className="text-[10px] text-muted-foreground border-t pt-3">
            Evaluated {new Date(r.evaluatedAt).toLocaleString()} · {r.llmModelUsed || 'unknown model'} · stage: {r.stage}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
