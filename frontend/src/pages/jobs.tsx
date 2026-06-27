import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog'
import { jobsApi } from '@/lib/api'
import type { JobDescription } from '@/types'
import { Briefcase, Plus, MapPin, Clock, Search, Users } from 'lucide-react'
import toast from 'react-hot-toast'

const schema = z.object({
  title: z.string().min(2, 'Title required'),
  description: z.string().min(10, 'Description too short'),
  location: z.string().optional(),
  experienceYearsRequired: z.coerce.number().min(0),
  requiredSkills: z.string().optional(),
  requiredCertifications: z.string().optional(),
  industry: z.string().optional(),
})
type FormData = z.infer<typeof schema>

export function JobsPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list().then((r) => r.data),
  })
  const jobs: JobDescription[] = Array.isArray(data) ? data : data?.data || []
  const filtered = search
    ? jobs.filter((j) => j.title.toLowerCase().includes(search.toLowerCase()))
    : jobs

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { experienceYearsRequired: 0 },
  })

  const create = useMutation({
    mutationFn: (d: FormData) =>
      jobsApi.create({
        ...d,
        requiredSkills: d.requiredSkills?.split(',').map((s) => s.trim()).filter(Boolean) || [],
        requiredCertifications: d.requiredCertifications?.split(',').map((s) => s.trim()).filter(Boolean) || [],
      }),
    onSuccess: () => {
      toast.success('Job description created')
      qc.invalidateQueries({ queryKey: ['jobs'] })
      reset()
      setOpen(false)
    },
    onError: () => toast.error('Failed to create job'),
  })

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Job Descriptions</h1>
          <p className="text-muted-foreground text-sm mt-1">{filtered.length} open positions</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button><Plus className="mr-2 h-4 w-4" />New Job</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create Job Description</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit((d) => create.mutate(d))} className="space-y-4 pt-2">
              <div>
                <label className="text-sm font-medium">Job Title *</label>
                <Input placeholder="e.g. Senior Mining Engineer" className="mt-1" {...register('title')} />
                {errors.title && <p className="text-xs text-destructive mt-1">{errors.title.message}</p>}
              </div>
              <div>
                <label className="text-sm font-medium">Description *</label>
                <textarea
                  className="w-full mt-1 rounded-md border bg-background px-3 py-2 text-sm min-h-[100px] focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Role responsibilities and requirements..."
                  {...register('description')}
                />
                {errors.description && <p className="text-xs text-destructive mt-1">{errors.description.message}</p>}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Location</label>
                  <Input placeholder="e.g. Jharkhand" className="mt-1" {...register('location')} />
                </div>
                <div>
                  <label className="text-sm font-medium">Min Experience (yrs)</label>
                  <Input type="number" min={0} className="mt-1" {...register('experienceYearsRequired')} />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium">Required Skills (comma-separated)</label>
                <Input placeholder="e.g. Mine Planning, AutoCAD, Blasting" className="mt-1" {...register('requiredSkills')} />
              </div>
              <div>
                <label className="text-sm font-medium">Required Certifications (comma-separated)</label>
                <Input placeholder="e.g. DGMS, Blasting Certificate" className="mt-1" {...register('requiredCertifications')} />
              </div>
              <div>
                <label className="text-sm font-medium">Industry</label>
                <Input placeholder="e.g. Mining, Steel, Power" className="mt-1" {...register('industry')} />
              </div>
              <Button type="submit" className="w-full" disabled={isSubmitting || create.isPending}>
                {create.isPending ? 'Creating...' : 'Create Job'}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input placeholder="Search jobs..." className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}><CardContent className="p-5"><Skeleton className="h-5 w-48 mb-2" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-3/4 mt-1" /></CardContent></Card>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Briefcase className="h-14 w-14 text-muted-foreground/30 mb-4" />
          <h3 className="text-lg font-semibold">No jobs found</h3>
          <p className="text-sm text-muted-foreground mt-1">Create your first job description to start matching candidates.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {filtered.map((job) => (
            <Card key={job.id} className="hover:border-primary/50 transition-colors">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base leading-tight">{job.title}</CardTitle>
                  <Badge variant={job.status === 'active' ? 'default' : 'secondary'} className="shrink-0 capitalize">
                    {job.status}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-0 space-y-3">
                <p className="text-sm text-muted-foreground line-clamp-2">{job.description}</p>
                <Separator />
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                  {job.location && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{job.location}</span>}
                  <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{job.experienceYearsRequired}+ yrs</span>
                  <span className="flex items-center gap-1"><Users className="h-3 w-3" />{job.candidateCount || 0} candidates</span>
                </div>
                {job.requiredSkills && job.requiredSkills.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {(Array.isArray(job.requiredSkills) ? job.requiredSkills : (job.requiredSkills as string).split(',')).slice(0, 4).map((s: string) => (
                      <Badge key={s.trim()} variant="secondary" className="text-[10px]">{s.trim()}</Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </motion.div>
  )
}
