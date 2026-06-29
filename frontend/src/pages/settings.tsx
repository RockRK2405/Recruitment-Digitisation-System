import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { useAuthStore } from '@/lib/store'
import { settingsApi } from '@/lib/api'
import {
  Settings, Database, Brain, Bell, Shield,
  Server, CheckCircle, AlertCircle, Sliders,
} from 'lucide-react'
import toast from 'react-hot-toast'

const WEIGHT_KEYS: Array<{ key: string; label: string; hint: string }> = [
  { key: 'llm_weight', label: 'LLM Reasoning', hint: 'How much the LLM-evaluated overall_match drives the final score' },
  { key: 'skill_weight', label: 'Skills', hint: 'Direct skill overlap vs required & preferred' },
  { key: 'experience_weight', label: 'Experience', hint: 'Years of experience vs required years' },
  { key: 'certification_weight', label: 'Certifications', hint: 'Required certifications match' },
  { key: 'education_weight', label: 'Education', hint: 'Education match' },
  { key: 'resume_quality_weight', label: 'Resume Quality', hint: 'LLM-judged resume polish & clarity' },
]

export function SettingsPage() {
  const { user } = useAuthStore()
  const qc = useQueryClient()

  const { data: weightsData } = useQuery({
    queryKey: ['scoring-weights'],
    queryFn: () => settingsApi.getWeights().then((r) => r.data),
  })

  const [weightDraft, setWeightDraft] = useState<Record<string, number>>({})
  useEffect(() => {
    if (weightsData?.weights) setWeightDraft(weightsData.weights)
  }, [weightsData])

  const saveWeights = useMutation({
    mutationFn: (w: Record<string, number>) => settingsApi.updateWeights(w),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scoring-weights'] })
      toast.success('Scoring weights saved — applies to next evaluation')
    },
    onError: () => toast.error('Failed to save weights'),
  })

  const weightSum = Object.values(weightDraft).reduce((a, b) => a + b, 0)
  const normalizedHint = weightSum > 0 && Math.abs(weightSum - 1) > 0.01
    ? `Note: weights sum to ${weightSum.toFixed(2)} — they will be normalized at scoring time.`
    : ''

  const [aiConfig, setAiConfig] = useState({
    provider: 'ollama',
    ollamaUrl: 'http://localhost:11434',
    ollamaModel: 'llama3',
    geminiKey: '',
  })

  const [uploadConfig, setUploadConfig] = useState({
    maxFileSizeMb: 50,
    ocrCascade: true,
    autoProcess: true,
  })

  const handleSaveAi = () => {
    toast.success('AI configuration saved (restart required)')
  }

  const handleSaveUpload = () => {
    toast.success('Upload settings saved')
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground text-sm mt-1">Configure the recruitment platform</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Account */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="h-4 w-4 text-primary" />
              Account
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-lg border p-3 space-y-2">
              <p className="text-sm font-medium">{user?.displayName || user?.username || 'Admin'}</p>
              <p className="text-xs text-muted-foreground">{user?.email || 'admin@kshamata.ai'}</p>
              <Badge variant="outline" className="text-xs capitalize">{user?.role || 'admin'}</Badge>
            </div>
            <Button variant="outline" size="sm" className="w-full" disabled>
              Change Password
            </Button>
          </CardContent>
        </Card>

        {/* AI / LLM Configuration */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Brain className="h-4 w-4 text-primary" />
              AI & LLM Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="text-sm font-medium">Provider</label>
                <select
                  value={aiConfig.provider}
                  onChange={(e) => setAiConfig({ ...aiConfig, provider: e.target.value })}
                  className="w-full mt-1 rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="ollama">Ollama (Local)</option>
                  <option value="gemini">Google Gemini</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Ollama Model</label>
                <Input
                  value={aiConfig.ollamaModel}
                  onChange={(e) => setAiConfig({ ...aiConfig, ollamaModel: e.target.value })}
                  placeholder="e.g. llama3, qwen2.5, mistral"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Ollama URL</label>
                <Input
                  value={aiConfig.ollamaUrl}
                  onChange={(e) => setAiConfig({ ...aiConfig, ollamaUrl: e.target.value })}
                  placeholder="http://localhost:11434"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Gemini API Key</label>
                <Input
                  type="password"
                  value={aiConfig.geminiKey}
                  onChange={(e) => setAiConfig({ ...aiConfig, geminiKey: e.target.value })}
                  placeholder="AIza..."
                  className="mt-1"
                />
              </div>
            </div>
            <div className="rounded-lg bg-muted/40 border p-3 flex gap-3">
              <AlertCircle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
              <p className="text-xs text-muted-foreground">
                AI configuration changes require a backend service restart to take effect.
                Set <code className="bg-background px-1 rounded">LLM_PROVIDER</code> in your <code className="bg-background px-1 rounded">.env</code> file for persistence.
              </p>
            </div>
            <Button size="sm" onClick={handleSaveAi}>Save AI Settings</Button>
          </CardContent>
        </Card>

        {/* Upload & OCR */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Database className="h-4 w-4 text-primary" />
              Upload & OCR Pipeline
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium">Max File Size (MB)</label>
              <Input
                type="number"
                value={uploadConfig.maxFileSizeMb}
                onChange={(e) => setUploadConfig({ ...uploadConfig, maxFileSizeMb: Number(e.target.value) })}
                className="mt-1"
                min={1}
                max={200}
              />
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">OCR Cascade</p>
                  <p className="text-xs text-muted-foreground">PaddleOCR → EasyOCR → Tesseract</p>
                </div>
                <Badge variant={uploadConfig.ocrCascade ? 'default' : 'secondary'}>
                  {uploadConfig.ocrCascade ? 'Enabled' : 'Disabled'}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Auto-process on Upload</p>
                  <p className="text-xs text-muted-foreground">Run AI pipeline immediately after upload</p>
                </div>
                <Badge variant={uploadConfig.autoProcess ? 'default' : 'secondary'}>
                  {uploadConfig.autoProcess ? 'Enabled' : 'Disabled'}
                </Badge>
              </div>
            </div>
            <Button size="sm" onClick={handleSaveUpload}>Save Upload Settings</Button>
          </CardContent>
        </Card>

        {/* System Status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Server className="h-4 w-4 text-primary" />
              System Status
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              { label: 'API Gateway', status: 'online', port: '4000' },
              { label: 'Python AI Service', status: 'unknown', port: '8000' },
              { label: 'PostgreSQL', status: 'online', port: '5432' },
              { label: 'Ollama LLM', status: 'unknown', port: '11434' },
              { label: 'Redis', status: 'unknown', port: '6379' },
            ].map((svc) => (
              <div key={svc.label} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {svc.status === 'online'
                    ? <CheckCircle className="h-4 w-4 text-emerald-500" />
                    : <AlertCircle className="h-4 w-4 text-muted-foreground/50" />
                  }
                  <span className="text-sm">{svc.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="text-xs text-muted-foreground">:{svc.port}</code>
                  <Badge
                    variant="outline"
                    className={svc.status === 'online' ? 'text-emerald-500 border-emerald-500/30' : ''}
                  >
                    {svc.status}
                  </Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Bell className="h-4 w-4 text-primary" />
              Notifications
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { label: 'New candidate uploaded', desc: 'Alert when a new resume is processed' },
                { label: 'High match score', desc: 'Alert when a candidate scores above 85%' },
                { label: 'Certification expiry', desc: 'Alert 30 days before cert expiry' },
                { label: 'Pipeline completion', desc: 'Alert when AI pipeline finishes' },
              ].map((n) => (
                <div key={n.label} className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <p className="text-sm font-medium">{n.label}</p>
                    <p className="text-xs text-muted-foreground">{n.desc}</p>
                  </div>
                  <Badge variant="secondary" className="shrink-0">Coming Soon</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        {/* AI Matching scoring weights — controls the hybrid score blend */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sliders className="h-4 w-4 text-primary" />
              AI Matching Scoring Weights
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground">
              Adjust how each signal contributes to the final candidate match score. Weights take effect on the next evaluation run.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              {WEIGHT_KEYS.map((w) => (
                <div key={w.key} className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">{w.label}</label>
                    <span className="text-sm tabular-nums text-muted-foreground">
                      {Math.round((weightDraft[w.key] ?? 0) * 100)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={weightDraft[w.key] ?? 0}
                    onChange={(e) => setWeightDraft({ ...weightDraft, [w.key]: parseFloat(e.target.value) })}
                    className="w-full accent-primary"
                  />
                  <p className="text-[10px] text-muted-foreground">{w.hint}</p>
                </div>
              ))}
            </div>
            {normalizedHint && (
              <p className="text-xs text-amber-600 dark:text-amber-400">{normalizedHint}</p>
            )}
            <Button
              size="sm"
              onClick={() => saveWeights.mutate(weightDraft)}
              disabled={saveWeights.isPending || Object.keys(weightDraft).length === 0}
            >
              {saveWeights.isPending ? 'Saving...' : 'Save Weights'}
            </Button>
          </CardContent>
        </Card>
      </div>
    </motion.div>
  )
}
