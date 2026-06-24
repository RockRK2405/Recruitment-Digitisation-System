import { Router, Request, Response } from 'express'
import { authenticate } from '../middleware/auth.js'
import axios from 'axios'
import { config } from '../config/index.js'

const router = Router()
const aiClient = axios.create({
  baseURL: config.aiService.url,
  timeout: config.aiService.timeout,
})

export function createAiProxyRouter() {
  router.post('/vision/analyze', authenticate, async (req: Request, res: Response) => {
    try {
      const response = await aiClient.post('/api/vision/analyze', req.body)
      res.json(response.data)
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { status: number; data: unknown } }
        res.status(axiosError.response?.status || 502).json(axiosError.response?.data || { message: 'AI service unavailable' })
      } else {
        res.status(502).json({ message: 'AI service unavailable' })
      }
    }
  })

  router.post('/vision/extract', authenticate, async (req: Request, res: Response) => {
    try {
      const response = await aiClient.post('/api/vision/extract', req.body)
      res.json(response.data)
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { status: number; data: unknown } }
        res.status(axiosError.response?.status || 502).json(axiosError.response?.data || { message: 'AI service unavailable' })
      } else {
        res.status(502).json({ message: 'AI service unavailable' })
      }
    }
  })

  router.get('/vision/candidate-summary/:candidateId', authenticate, async (req: Request, res: Response) => {
    try {
      const response = await aiClient.get(`/api/vision/candidate-summary/${req.params.candidateId}`)
      res.json(response.data)
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { status: number; data: unknown } }
        res.status(axiosError.response?.status || 502).json(axiosError.response?.data || { message: 'AI service unavailable' })
      } else {
        res.status(502).json({ message: 'AI service unavailable' })
      }
    }
  })

  return router
}
