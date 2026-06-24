import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { getInitials } from '@/lib/utils'
import {
  ArrowLeft, MapPin, Mail, Phone, Calendar,
  Briefcase, GraduationCap, Award, FileText,
  Star, Clock, MessageSquare, Share2, Download,
  CheckCircle, XCircle, AlertCircle, ExternalLink
} from 'lucide-react'

const candidate = {
  id: 'c-1',
  name: 'Rajesh Kumar',
  email: 'rajesh.kumar@email.com',
  phone: '+91-9876543210',
  location: 'Delhi, India',
  status: 'screening',
  experience: 12,
  domain: 'Mining',
  education: 'B.Tech in Mining Engineering',
  university: 'IIT Kharagpur',
  profileCompleteness: 88,
  aiSummary: 'Experienced mining engineer with 12+ years in underground and open-pit mining operations. Strong background in safety management, mine planning, and team leadership. Holds DGMS and First Class Mine Manager certifications.',
  skills: ['Mining Engineering', 'Mine Planning', 'Safety Management', 'Blasting Design', 'Ventilation', 'Risk Assessment', 'Team Leadership', 'AutoCAD', 'Surpac', 'DGMS Compliance'],
  certifications: [
    { name: 'First Class Mine Manager', issuer: 'DGMS', date: '2018', expiry: '2025', verified: true },
    { name: 'Shafts & Winding', issuer: 'DGMS', date: '2020', expiry: '2026', verified: true },
    { name: 'Mine Safety Training', issuer: 'ISM', date: '2021', expiry: '2024', verified: false },
    { name: 'Blasting Certificate', issuer: 'IBM', date: '2019', expiry: '2025', verified: true },
  ],
  experience: [
    { role: 'Senior Mining Engineer', company: 'Hindustan Zinc Ltd.', period: '2019-Present', description: 'Leading underground mining operations, production planning, safety audits' },
    { role: 'Mining Engineer', company: 'Coal India Ltd.', period: '2015-2019', description: 'Open-pit mine planning, blasting design, overburden management' },
    { role: 'Junior Mining Engineer', company: 'NMDC Ltd.', period: '2012-2015', description: 'Assisted in mine operations, survey, quality control' },
  ],
  matchHistory: [
    { job: 'Senior Mining Engineer', company: 'Vedanta Ltd.', score: 92, date: '2024-08-15' },
    { job: 'Mine Manager', company: 'Coal India', score: 87, date: '2024-07-20' },
    { job: 'Safety Officer', company: 'Adani Mining', score: 78, date: '2024-06-10' },
  ],
  notes: [
    { author: 'Arun R.', text: 'Strong candidate, DGMS certified. Recommend for interview.', date: '2024-08-16', type: 'positive' },
    { author: 'Simran K.', text: 'Verify work gap between 2015-2016 references.', date: '2024-08-14', type: 'action' },
  ],
}

export function CandidateProfilePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')

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
                  {getInitials(candidate.name)}
                </AvatarFallback>
              </Avatar>
              <h2 className="text-xl font-bold">{candidate.name}</h2>
              <p className="text-sm text-muted-foreground">{candidate.domain} Professional</p>
              <Badge variant="outline" className="mt-2 capitalize">{candidate.status}</Badge>

              <Separator className="my-4" />

              <div className="w-full space-y-3 text-sm">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <MapPin className="h-4 w-4" />
                  <span>{candidate.location}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Mail className="h-4 w-4" />
                  <span>{candidate.email}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Phone className="h-4 w-4" />
                  <span>{candidate.phone}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Briefcase className="h-4 w-4" />
                  <span>{candidate.experience} years experience</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <GraduationCap className="h-4 w-4" />
                  <span>{candidate.education}</span>
                </div>
              </div>

              <Separator className="my-4" />

              <div className="w-full">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-muted-foreground">Profile Completeness</span>
                  <span className="font-medium">{candidate.profileCompleteness}%</span>
                </div>
                <Progress value={candidate.profileCompleteness} />
              </div>

              <div className="flex gap-2 mt-4 w-full">
                <Button className="flex-1" size="sm">
                  <MessageSquare className="mr-2 h-4 w-4" />
                  Contact
                </Button>
                <Button variant="outline" size="icon">
                  <Share2 className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="icon">
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardContent className="p-6">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="mb-6">
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="experience">Experience</TabsTrigger>
                  <TabsTrigger value="skills">Skills</TabsTrigger>
                  <TabsTrigger value="certifications">Certifications</TabsTrigger>
                  <TabsTrigger value="matching">Matching</TabsTrigger>
                  <TabsTrigger value="notes">Notes</TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="space-y-6">
                  <div>
                    <h3 className="font-semibold mb-2">AI Summary</h3>
                    <div className="rounded-lg bg-primary/5 border border-primary/10 p-4">
                      <div className="flex gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/10">
                          <Star className="h-4 w-4 text-accent" />
                        </div>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                          {candidate.aiSummary}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold mb-3">Key Skills</h3>
                    <div className="flex flex-wrap gap-2">
                      {candidate.skills.map((skill) => (
                        <Badge key={skill} variant="secondary">{skill}</Badge>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold mb-3">Certifications</h3>
                    <div className="grid gap-3">
                      {candidate.certifications.map((cert) => (
                        <div key={cert.name} className="flex items-center justify-between rounded-lg border p-3">
                          <div className="flex items-start gap-3">
                            <Award className="h-5 w-5 text-amber-500 mt-0.5" />
                            <div>
                              <p className="font-medium text-sm">{cert.name}</p>
                              <p className="text-xs text-muted-foreground">{cert.issuer} · Expires {cert.expiry}</p>
                            </div>
                          </div>
                          <Badge variant={cert.verified ? 'success' : 'warning'}>
                            {cert.verified ? 'Verified' : 'Pending'}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="experience" className="space-y-4">
                  {candidate.experience.map((exp, i) => (
                    <div key={i} className="rounded-lg border p-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-semibold">{exp.role}</h4>
                          <p className="text-sm text-muted-foreground">{exp.company}</p>
                        </div>
                        <Badge variant="outline">{exp.period}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mt-2">{exp.description}</p>
                    </div>
                  ))}
                </TabsContent>

                <TabsContent value="skills">
                  <div className="grid gap-2">
                    {candidate.skills.map((skill) => (
                      <div key={skill} className="flex items-center justify-between rounded-lg border p-3">
                        <span className="text-sm font-medium">{skill}</span>
                        <Badge variant="success">Matched</Badge>
                      </div>
                    ))}
                  </div>
                </TabsContent>

                <TabsContent value="certifications">
                  <div className="space-y-3">
                    {candidate.certifications.map((cert) => (
                      <div key={cert.name} className="rounded-lg border p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-3">
                            <Award className="h-5 w-5 text-amber-500 mt-0.5" />
                            <div>
                              <h4 className="font-medium">{cert.name}</h4>
                              <p className="text-xs text-muted-foreground">Issued by {cert.issuer}</p>
                              <p className="text-xs text-muted-foreground">{cert.date} - {cert.expiry}</p>
                            </div>
                          </div>
                          {cert.verified ? (
                            <CheckCircle className="h-5 w-5 text-emerald-500" />
                          ) : (
                            <AlertCircle className="h-5 w-5 text-amber-500" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </TabsContent>

                <TabsContent value="matching">
                  <div className="space-y-4">
                    <h3 className="font-semibold">Match History</h3>
                    {candidate.matchHistory.map((match, i) => (
                      <div key={i} className="rounded-lg border p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">{match.job}</p>
                            <p className="text-sm text-muted-foreground">{match.company}</p>
                          </div>
                          <div className="text-right">
                            <div className="flex items-center gap-2">
                              <Progress value={match.score} className="w-16 h-2" />
                              <span className={cn(
                                'text-lg font-bold',
                                match.score >= 90 ? 'text-emerald-500' : 
                                match.score >= 80 ? 'text-amber-500' : 'text-muted-foreground'
                              )}>
                                {match.score}%
                              </span>
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">{match.date}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </TabsContent>

                <TabsContent value="notes">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold">Recruiter Notes</h3>
                      <Button size="sm">
                        <MessageSquare className="mr-2 h-4 w-4" />
                        Add Note
                      </Button>
                    </div>
                    {candidate.notes.map((note, i) => (
                      <div key={i} className="rounded-lg border p-4">
                        <div className="flex items-start gap-3">
                          <Avatar className="h-8 w-8">
                            <AvatarFallback className="bg-primary/10 text-primary text-xs">
                              {getInitials(note.author)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-medium">{note.author}</span>
                              <Badge variant={note.type === 'positive' ? 'success' : 'warning'}>
                                {note.type}
                              </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">{note.text}</p>
                            <p className="text-xs text-muted-foreground mt-1">{note.date}</p>
                          </div>
                        </div>
                      </div>
                    ))}
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


