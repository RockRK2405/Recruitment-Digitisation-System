import express from 'express'
import cors from 'cors'
import helmet from 'helmet'
import compression from 'compression'
import morgan from 'morgan'
import { Pool } from 'pg'
import { config } from './config/index.js'
import { authenticate } from './middleware/auth.js'
import { errorHandler, notFoundHandler } from './middleware/error-handler.js'
import { createAuthRouter } from './routes/auth.js'
import { createCandidatesRouter } from './routes/candidates.js'
import { createJobsRouter } from './routes/jobs.js'
import { createMatchingRouter } from './routes/matching.js'
import { createResumesRouter } from './routes/resumes.js'
import { createDashboardRouter } from './routes/dashboard.js'
import { createAnalyticsRouter } from './routes/analytics.js'
import { createAgentRouter } from './routes/agent.js'
import { createDocumentsRouter } from './routes/documents.js'
import { createAiProxyRouter } from './routes/ai-proxy.js'

async function main() {
  const pool = new Pool({
    host: config.database.host,
    port: config.database.port,
    database: config.database.name,
    user: config.database.user,
    password: config.database.password,
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 5000,
  })

  pool.on('error', (err) => {
    console.error('Database pool error:', err)
  })

  try {
    await pool.query('SELECT 1')
    console.log('Database connected successfully')
  } catch (err) {
    console.warn('Database connection failed, server will start but DB features will be limited:', err)
  }

  const app = express()

  app.use(helmet())
  app.use(cors({ origin: config.cors.origin, credentials: true }))
  app.use(compression())
  app.use(morgan('dev'))
  app.use(express.json({ limit: '50mb' }))
  app.use(express.urlencoded({ extended: true, limit: '50mb' }))

  app.get('/health', (_req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() })
  })

  app.use('/api/auth', createAuthRouter(pool))
  app.use('/api/candidates', createCandidatesRouter(pool))
  app.use('/api/jobs', createJobsRouter(pool))
  app.use('/api/matching', createMatchingRouter(pool))
  app.use('/api/resumes', createResumesRouter(pool))
  app.use('/api/dashboard', createDashboardRouter(pool))
  app.use('/api/analytics', createAnalyticsRouter(pool))
  app.use('/api/agent', createAgentRouter(pool))
  app.use('/api/documents', createDocumentsRouter(pool))
  app.use('/api/vision', createAiProxyRouter())

  app.use(notFoundHandler)
  app.use(errorHandler)

  app.listen(config.port, () => {
    console.log(`API Gateway running on port ${config.port}`)
    console.log(`Environment: ${config.nodeEnv}`)
    console.log(`AI Service: ${config.aiService.url}`)
  })
}

main().catch(console.error)
