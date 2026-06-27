import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { resumesApi } from '@/lib/api'
import {
  Upload, FileText, CheckCircle, XCircle, Loader2,
  CloudUpload, Info, Zap,
} from 'lucide-react'
import toast from 'react-hot-toast'

type UploadStatus = 'pending' | 'uploading' | 'success' | 'error'

interface UploadItem {
  id: string
  file: File
  status: UploadStatus
  progress: number
  result?: Record<string, unknown>
  error?: string
}

const ACCEPTED = '.pdf,.png,.jpg,.jpeg,.tiff,.bmp,.doc,.docx,.zip'
const MAX_MB = 50

export function ResumesPage() {
  const [items, setItems] = useState<UploadItem[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const updateItem = (id: string, patch: Partial<UploadItem>) =>
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)))

  const processFile = async (item: UploadItem) => {
    updateItem(item.id, { status: 'uploading', progress: 20 })
    try {
      updateItem(item.id, { progress: 50 })
      const res = await resumesApi.upload(item.file)
      updateItem(item.id, { status: 'success', progress: 100, result: res.data })
      toast.success(`${item.file.name} processed successfully`)
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string; message?: string } } }).response?.data?.detail ||
            (err as { response?: { data?: { message?: string } } }).response?.data?.message ||
            'Upload failed'
          : 'Upload failed'
      updateItem(item.id, { status: 'error', progress: 0, error: msg })
      toast.error(`Failed: ${item.file.name}`)
    }
  }

  const addFiles = (files: FileList | File[]) => {
    const validFiles = Array.from(files).filter((f) => {
      if (f.size > MAX_MB * 1024 * 1024) {
        toast.error(`${f.name} exceeds ${MAX_MB}MB limit`)
        return false
      }
      return true
    })

    const newItems: UploadItem[] = validFiles.map((f) => ({
      id: `${f.name}-${Date.now()}-${Math.random()}`,
      file: f,
      status: 'pending',
      progress: 0,
    }))

    setItems((prev) => [...prev, ...newItems])
    newItems.forEach((item) => processFile(item))
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    addFiles(e.dataTransfer.files)
  }

  const successCount = items.filter((i) => i.status === 'success').length
  const failCount = items.filter((i) => i.status === 'error').length
  const pendingCount = items.filter((i) => i.status === 'uploading').length

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Resume Intelligence</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Upload resumes in any format — OCR, AI parsing, and profile creation run automatically
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { label: 'Processed', value: successCount, icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
          { label: 'Processing', value: pendingCount, icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-500/10' },
          { label: 'Failed', value: failCount, icon: XCircle, color: 'text-red-500', bg: 'bg-red-500/10' },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4 flex items-center gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${s.bg}`}>
                <s.icon className={`h-5 w-5 ${s.color} ${s.label === 'Processing' && pendingCount > 0 ? 'animate-spin' : ''}`} />
              </div>
              <div>
                <p className="text-2xl font-bold">{s.value}</p>
                <p className="text-xs text-muted-foreground">{s.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card
        className={`border-2 border-dashed transition-colors ${isDragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <CardContent className="flex flex-col items-center justify-center py-14 text-center">
          <CloudUpload className={`h-12 w-12 mb-4 transition-colors ${isDragging ? 'text-primary' : 'text-muted-foreground/40'}`} />
          <p className="text-lg font-medium mb-1">Drop resumes here or click to browse</p>
          <p className="text-sm text-muted-foreground mb-4">
            Supports PDF, PNG, JPG, TIFF, BMP, DOC, DOCX, ZIP (max {MAX_MB}MB each)
          </p>
          <div className="flex gap-3">
            <Button onClick={() => inputRef.current?.click()}>
              <Upload className="mr-2 h-4 w-4" />
              Browse Files
            </Button>
          </div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPTED}
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
        </CardContent>
      </Card>

      <div className="rounded-lg border bg-muted/30 p-4 flex gap-3">
        <Info className="h-4 w-4 text-primary mt-0.5 shrink-0" />
        <div className="text-sm text-muted-foreground space-y-1">
          <p className="font-medium text-foreground">AI Pipeline</p>
          <p>Each uploaded file goes through: OCR (PaddleOCR → EasyOCR → Tesseract) → Entity Extraction → Safety Certification Audit → Candidate Profile Creation.</p>
        </div>
      </div>

      <AnimatePresence>
        {items.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Upload Queue</h2>
              <Button variant="ghost" size="sm" onClick={() => setItems([])}>Clear All</Button>
            </div>
            {items.map((item) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
              >
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                        <FileText className="h-4 w-4 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{item.file.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {(item.file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                        {item.status === 'uploading' && (
                          <Progress value={item.progress} className="mt-1.5 h-1.5" />
                        )}
                        {item.status === 'error' && (
                          <p className="text-xs text-destructive mt-1">{item.error}</p>
                        )}
                        {item.status === 'success' && item.result && (
                          <div className="flex items-center gap-2 mt-1 flex-wrap">
                            {(item.result.ocr_confidence as number) && (
                              <span className="text-xs text-muted-foreground">
                                OCR: {item.result.ocr_confidence as number}%
                              </span>
                            )}
                            {(item.result.ocr_engine_used as string) && (
                              <Badge variant="secondary" className="text-[10px]">
                                <Zap className="h-2.5 w-2.5 mr-1" />
                                {item.result.ocr_engine_used as string}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="shrink-0">
                        {item.status === 'pending' && <Badge variant="secondary">Queued</Badge>}
                        {item.status === 'uploading' && (
                          <Badge variant="outline" className="text-blue-500 border-blue-500/30">
                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />Processing
                          </Badge>
                        )}
                        {item.status === 'success' && (
                          <Badge variant="outline" className="text-emerald-500 border-emerald-500/30">
                            <CheckCircle className="mr-1 h-3 w-3" />Done
                          </Badge>
                        )}
                        {item.status === 'error' && (
                          <Badge variant="destructive">Failed</Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
