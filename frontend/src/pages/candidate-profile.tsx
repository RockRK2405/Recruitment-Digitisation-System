import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { cn, getInitials } from '@/lib/utils'
import { candidatesApi, resumesApi } from '@/lib/api'
import {
  ArrowLeft, MapPin, Mail, Phone,
  Briefcase, GraduationCap, Award,
  Star, MessageSquare, Share2, Download,
  CheckCircle, AlertCircle,
} from 'lucide-react'

export function CandidateProfilePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')

  const { data: candidate, isLoading } = useQuery({
    queryKey: ['candidate', id],
    queryFn: () => resumesApi.profile(id!).then((r) => r.data),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
        <Skeleton className="h-9 w-40" />
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-80" />
          <div className="lg:col-span-2"><Skeleton className="h-80" /></div>
        </div>
      </motion.div>
    )
  }

  if (!candidate) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center py-20">
        <p className="text-muted-foreground">Candidate not found.</p>
        <Button className="mt-4" onClick={() => navigate('/candidates')}>Back to Candidates</Button>
      </motion.div>
    )
  }

  const skills: string[] = Array.isArray(candidate.resume?.skills)
    ? candidate.resume.skills
    : (candidate.resume?.skills_list || '').split(',').map((s: string) => s.trim()).filter(Boolean)

  const certifications = candidate.certifications || []
  const experienceYears = candidate.resume?.experience_years || 0
  const domain = candidate.resume?.primary_domain || candidate.primaryDomain || ''
  const education = candidate.resume?.education || candidate.education || ''

  const profileFields = [candidate.name, candidate.email, candidate.phone, candidate.location, domain, education]
  const profileCompleteness = Math.round((profileFields.filter(Boolean).length / profileFields.length) * 100)

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <Button variant="ghost" className="gap-2 -ml-2" onClick={() => navigate('/candidates')}>
        <ArrowLeft className="h-4 w-4" />
        Back to Candidates
      </Button>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardContent className="p-6">
            <div className="flex flex-col items-center text-center">
              <Avatar className="h-20 w-20 mb-4">
                <AvatarFallback className="bg-primary/10 text-primary text-xl">
                  {getInitials(candidate.name || '')}
                </AvatarFallback>
              </Avatar>
              <h2 className="text-xl font-bold">{candidate.name}</h2>
              {domain && <p className="text-sm text-muted-foreground">{domain} Professional</p>}
              <Badge variant="outline" className="mt-2 capitalize">{candidate.status}</Badge>

              <Separator className="my-4" />

              <div className="w-full space-y-3 text-sm">
                {candidate.location && (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <MapPin className="h-4 w-4 shrink-0" /><span>{candidate.location}</span>
                  </div>
                )}
                {candidate.email && (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Mail className="h-4 w-4 shrink-0" /><span className="truncate">{candidate.email}</span>
                  </div>
                )}
                {candidate.phone && (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Phone className="h-4 w-4 shrink-0" /><span>{candidate.phone}</span>
                  </div>
                )}
                {experienceYears > 0 && (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Briefcase className="h-4 w-4 shrink-0" /><span>{experienceYears} years experience</span>
                  </div>
                )}
                {education && (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <GraduationCap className="h-4 w-4 shrink-0" /><span className="truncate">{education}</span>
                  </div>
                )}
              </div>

              <Separator className="my-4" />

              <div className="w-full">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-muted-foreground">Profile Completeness</span>
                  <span className="font-medium">{profileCompleteness}%</span>
                </div>
                <Progress value={profileCompleteness} />
              </div>

              <div className="flex gap-2 mt-4 w-full">
                <Button className="flex-1" size="sm">
                  <MessageSquare className="mr-2 h-4 w-4" />
                  Contact
                </Button>
                <Button variant="outline" size="icon"><Share2 className="h-4 w-4" /></Button>
                <Button variant="outline" size="icon"><Download className="h-4 w-4" /></Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardContent className="p-6">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="mb-6 flex-wrap h-auto gap-1">
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="skills">Skills</TabsTrigger>
                  <TabsTrigger value="certifications">Certifications</TabsTrigger>
                  <TabsTrigger value="notes">Notes</TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="space-y-6">
                  <div className="rounded-lg bg-primary/5 border border-primary/10 p-4">
                    <div className="flex gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/10">
                        <Star className="h-4 w-4 text-accent" />
                      </div>
                      <div>
                        <p className="text-sm font-medium mb-1">Candidate Summary</p>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                          {domain && `${candidate.name} is a ${domain} professional`}
                          {experienceYears > 0 && ` with ${experienceYears} years of experience`}.
                          {skills.length > 0 && ` Key skills include ${skills.slice(0, 5).join(', ')}.`}
                          {certifications.length > 0 && ` Holds ${certifications.length} certification(s).`}
                        </p>
                      </div>
                    </div>
                  </div>

                  {skills.length > 0 && (
                    <div>
                      <h3 className="font-semibold mb-3">Key Skills</h3>
                      <div className="flex flex-wrap gap-2">
                        {skills.map((skill: string) => (
                          <Badge key={skill} variant="secondary">{skill}</Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {certifications.length > 0 && (
                    <div>
                      <h3 className="font-semibold mb-3">Certifications</h3>
                      <div className="grid gap-3">
                        {certifications.map((cert: { name: string; issuer: string; status: string }) => (
                          <div key={cert.name} className="flex items-center justify-between rounded-lg border p-3">
                            <div className="flex items-start gap-3">
                              <Award className="h-5 w-5 text-amber-500 mt-0.5" />
                              <div>
                                <p className="font-medium text-sm">{cert.name}</p>
                                {cert.issuer && <p className="text-xs text-muted-foreground">{cert.issuer}</p>}
                              </div>
                            </div>
                            <Badge variant="outline" className={cert.status === 'verified' ? 'text-emerald-500 border-emerald-500/30' : ''}>
                              {cert.status || 'Pending'}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="skills">
                  {skills.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">No skills extracted yet.</p>
                  ) : (
                    <div className="grid gap-2">
                      {skills.map((skill: string) => (
                        <div key={skill} className="flex items-center justify-between rounded-lg border p-3">
                          <span className="text-sm font-medium">{skill}</span>
                          <Badge variant="secondary">Extracted</Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="certifications">
                  {certifications.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">No certifications found.</p>
                  ) : (
                    <div className="space-y-3">
                      {certifications.map((cert: { name: string; issuer: string; status: string }) => (
                        <div key={cert.name} className="rounded-lg border p-4">
                          <div className="flex items-start justify-between">
                            <div className="flex items-start gap-3">
                              <Award className="h-5 w-5 text-amber-500 mt-0.5" />
                              <div>
                                <h4 className="font-medium">{cert.name}</h4>
                                {cert.issuer && <p className="text-xs text-muted-foreground">Issued by {cert.issuer}</p>}
                              </div>
                            </div>
                            {cert.status === 'verified' ? (
                              <CheckCircle className="h-5 w-5 text-emerald-500" />
                            ) : (
                              <AlertCircle className="h-5 w-5 text-amber-500" />
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="notes">
                  <div className="flex flex-col items-center justify-center py-10 text-center">
                    <MessageSquare className="h-10 w-10 text-muted-foreground/30 mb-3" />
                    <p className="text-sm text-muted-foreground">Recruiter notes coming soon.</p>
                    <p className="text-xs text-muted-foreground mt-1">Use the AI Agent to generate notes and recommendations.</p>
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </div>
    </motion.div>
  )
}


