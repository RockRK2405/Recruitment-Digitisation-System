# WorkforceAI - Recruitment Intelligence Platform

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                     │
│              TypeScript · Tailwind · ShadCN UI              │
│              React Query · Framer Motion · RTL              │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP/REST + WebSocket
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Node.js API Gateway (Express)               │
│              TypeScript · PostgreSQL · Redis                 │
│         JWT Auth · Rate Limiting · Request Validation        │
├─────────────────────┬───────────────────────────────────────┤
│                     │                                       │
│          PostgreSQL │                           Redis       │
│          (Primary)  │                     (Cache/Queue)     │
│                     │                                       │
└─────────────────────┴───────────────────────────────────────┘
                      │ Internal HTTP
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Python AI Microservice (FastAPI)                │
│   OCR Engine · Resume Parser · Embedding Service            │
│   LLM Orchestrator · Ranking Engine · Knowledge Graph       │
│   Celery Workers · ChromaDB Vector Store                    │
└─────────────────────────────────────────────────────────────┘
```

## Why This Architecture Is Superior

### 1. **Hybrid Architecture (Node.js + Python)**
- **Node.js API Gateway**: Best for I/O-bound operations, real-time features, auth middleware, BFF pattern, request validation, rate limiting
- **Python AI Service**: Best for AI/ML workloads, OCR (PaddleOCR, EasyOCR), LLM orchestration, vector embeddings, NLP processing
- Each language does what it does best

### 2. **API Gateway Pattern**
- Single entry point for all clients
- Centralized auth, rate limiting, request validation
- Service discovery for AI microservice
- Request/response transformation
- WebSocket support for real-time features

### 3. **PostgreSQL + pgvector**
- ACID compliance for candidate data
- Vector similarity search built-in (pgvector)
- Full-text search with pg_trgm
- Proper indexing strategy for 5000+ resumes
- JSONB for flexible extracted data

### 4. **Redis + Queue System**
- Session caching (JWT blacklist, rate limiting)
- Background job processing (OCR, parsing, embedding)
- Real-time updates via Pub/Sub
- Cache frequently accessed data

### 5. **React + TypeScript Frontend**
- Type safety across the entire stack
- Component reusability with ShadCN UI
- Optimized rendering with React Query
- Smooth animations with Framer Motion
- Enterprise-grade design system

## Design System

### Color Palette
- **Primary**: Deep Blue (#1e40af) - Trust, professionalism
- **Secondary**: Steel Grey (#6c757d) - Industrial, stable
- **Accent**: Emerald Green (#059669) - Growth, success
- **Dark Mode**: Full dark theme with proper contrast ratios

### Typography
- **Font**: Inter (sans-serif), JetBrains Mono (monospace)
- **Scale**: 12px/14px/16px/18px/20px/24px/30px
- **Weights**: 400/500/600/700/800

### Component Hierarchy
```
Layout
├── Sidebar (collapsible, icon + label)
├── Header (search, notifications, profile)
└── Main Content
    ├── Cards (metrics, summaries)
    ├── Tables (data display)
    ├── Charts (Recharts)
    ├── Forms (React Hook Form + Zod)
    └── Dialogs (modals, drawers)

Shared Components
├── Button (variants: default, outline, ghost, accent)
├── Card (with header, content, footer)
├── Badge (status, tags, labels)
├── Avatar (user, candidate)
├── Progress (scores, completion)
├── Input, Select, Tabs, Dialog, Table
```

## Performance Strategy

### Database
- Proper indexes on all query columns
- Full-text search with pg_trgm GIN indexes
- JSONB for flexible document storage
- Connection pooling (max 20 connections)

### Caching
- Redis for session data, rate limiting
- Query result caching for dashboard metrics
- Browser caching for static assets

### Background Processing
- Celery workers for OCR, parsing, embedding
- Queue-based upload processing
- Concurrent processing with configurable workers

### Frontend
- Lazy loading for route components
- Infinite scroll / pagination for tables
- React Query for smart caching & refetching
- Debounced search inputs
- Code splitting with Vite

## Security

### Authentication
- JWT-based auth with access + refresh tokens
- Token blacklisting on logout
- Password hashing with bcrypt
- Rate limiting on auth endpoints

### Authorization (RBAC)
- **Admin**: Full system access, user management, config
- **Recruiter**: Candidate management, matching, review
- **Viewer**: Read-only dashboard, search, monitors

### API Security
- Helmet.js security headers
- CORS restricted to frontend origin
- Request size limits (50mb for uploads)
- Input validation with Zod schemas
- SQL injection protection via parameterized queries

## Folder Structure

```
├── frontend/                    # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/             # ShadCN UI primitives
│   │   │   ├── layout/         # Sidebar, Header, AppLayout
│   │   │   └── shared/         # ProtectedRoute, etc.
│   │   ├── pages/              # Route page components
│   │   ├── hooks/              # Custom React hooks
│   │   ├── lib/                # Store, API client, utils
│   │   ├── types/              # TypeScript interfaces
│   │   └── styles/             # Global CSS, Tailwind
│   ├── index.html
│   └── vite.config.ts
│
├── api-gateway/                 # Node.js + Express + TypeScript
│   ├── src/
│   │   ├── routes/             # API route handlers
│   │   ├── middleware/         # Auth, validation, error handling
│   │   ├── config/             # Environment config
│   │   ├── types/              # Type definitions
│   │   └── index.ts            # Entry point
│   └── Dockerfile
│
├── ai-service/                  # Python + FastAPI
│   ├── api/                    # FastAPI routes
│   ├── config/                 # Settings
│   ├── services/               # Existing Python services
│   └── requirements.txt
│
├── database/
│   └── schema.sql              # Full PostgreSQL schema
│
├── docker-compose.yml           # Production stack
├── docker-compose.dev.yml       # Local dev services
└── infra/                       # CI/CD, monitoring
```

## Getting Started

### Prerequisites
- Node.js 20+
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16 (or Docker)

### Quick Start

```bash
# 1. Start infrastructure (PostgreSQL + Redis)
docker compose -f docker-compose.dev.yml up -d

# 2. Install frontend dependencies
cd frontend && npm install && cd ..

# 3. Install API gateway dependencies
cd api-gateway && npm install && cd ..

# 4. Install Python AI service dependencies
cd ai-service && pip install -r requirements.txt && cd ..

# 5. Start development servers
# Terminal 1 - API Gateway
cd api-gateway && npm run dev

# Terminal 2 - Frontend
cd frontend && npm run dev

# Terminal 3 - AI Service (if needed)
cd ai-service && python -m api.main
```

### Using Docker (Full Stack)

```bash
# Start everything
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop
docker compose down
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user
- `POST /api/auth/refresh` - Refresh token

### Candidates
- `GET /api/candidates` - List candidates (paginated, filterable)
- `GET /api/candidates/:id` - Get candidate details
- `GET /api/candidates/:id/timeline` - Candidate activity timeline
- `PUT /api/candidates/:id` - Update candidate

### Jobs
- `GET /api/jobs` - List jobs
- `GET /api/jobs/:id` - Get job details
- `POST /api/jobs` - Create job
- `PUT /api/jobs/:id` - Update job
- `DELETE /api/jobs/:id` - Delete job

### Matching
- `GET /api/matching/rank/:jobId` - Ranked candidates for job
- `GET /api/matching/score` - Match score
- `GET /api/matching/recommendations/:candidateId` - Job recommendations
- `POST /api/matching/semantic` - Semantic search
- `GET /api/matching/explain/:candidateId/:jobId` - Explain match

### Resumes
- `POST /api/resumes/upload` - Upload single resume
- `POST /api/resumes/bulk-upload` - Bulk upload
- `GET /api/resumes/profile/:candidateId` - Candidate profile
- `GET /api/resumes/document/:docId` - Document details

### Analytics
- `GET /api/analytics/summary` - Platform summary
- `GET /api/analytics/skills` - Skill distribution
- `GET /api/analytics/funnel` - Hiring funnel
- `GET /api/analytics/sources` - Candidate sources

### AI Agent
- `POST /api/agent/chat` - Chat with AI agent
- `GET /api/agent/logs` - Agent execution logs
- `POST /api/agent/pipeline` - Start AI pipeline

### Dashboard
- `GET /api/dashboard/metrics` - Dashboard metrics
- `GET /api/dashboard/activity` - Recent activity

### Documents
- `POST /api/documents/upload-batch` - Batch document upload
- `POST /api/documents/classify` - Classify document
- `GET /api/documents/candidate/:candidateId` - List candidate documents
