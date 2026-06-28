# WorkforceAI — Intelligent Recruitment Platform for Heavy Industry

> **Enterprise-grade AI recruitment assistant** for mining, steel, power, and heavy construction sectors — built to digitise paper resumes, rank candidates against job descriptions, and power an LLM-backed HR assistant.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Features](#features)
5. [Quick Start](#quick-start)
6. [Environment Variables](#environment-variables)
7. [API Reference](#api-reference)
8. [Frontend Pages](#frontend-pages)
9. [AI Pipeline](#ai-pipeline)
10. [LLM Provider Configuration](#llm-provider-configuration)
11. [OCR Pipeline](#ocr-pipeline)
12. [Database Schema](#database-schema)
13. [Deployment](#deployment)
14. [Developer Guide](#developer-guide)

---

## Overview

**WorkforceAI** solves a real problem in heavy industry HR: thousands of blue-collar workers submit crumpled, handwritten, or low-quality scanned resumes that no standard ATS can read. The platform:

- **Ingests** any resume format — PDF, scanned PDF, PNG/JPEG/TIFF/BMP, DOC/DOCX, handwritten, multi-language
- **Digitises** them with a 3-tier OCR cascade (PaddleOCR → EasyOCR → Tesseract) with OpenCV preprocessing
- **Parses** structured profiles using an LLM (Ollama locally, Google Gemini as cloud fallback)
- **Stores** everything in PostgreSQL with pgvector for semantic search
- **Ranks** candidates against job descriptions using vector similarity + skills overlap + safety certification checks
- **Assists** HR with a conversational AI agent backed by RAG over stored resumes and JDs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WorkforceAI Platform                         │
├───────────────┬──────────────────────┬──────────────────────────────┤
│   Frontend    │    API Gateway       │     Python AI Service        │
│  React 18     │   Node.js/Express    │     FastAPI (port 8000)      │
│  Vite + TS    │   (port 4000)        │                              │
│  ShadCN UI    │                      │  ┌─────────────────────────┐ │
│               │  ┌────────────────┐  │  │  7-Stage Agent Pipeline │ │
│  /dashboard   │  │  JWT Auth      │  │  │  1. Intake & Classify   │ │
│  /candidates  │  │  Rate Limiting │  │  │  2. OCR Preprocess      │ │
│  /jobs        │  │  File Upload   │  │  │  3. Vision Analysis     │ │
│  /resumes     │  │  DB Pool (pg)  │  │  │  4. LLM Parsing        │ │
│  /matching    │  │  AI Proxy      │  │  │  5. Verification        │ │
│  /analytics   │  └────────────────┘  │  │  6. Embeddings + Store  │ │
│  /agent       │                      │  │  7. Match and Score     │ │
│  /settings    │                      │  └─────────────────────────┘ │
└───────────────┴──────────────────────┴──────────────────────────────┘
                              │                        │
                    ┌─────────┴──────┐    ┌───────────┴──────────┐
                    │  PostgreSQL    │    │  ChromaDB            │
                    │  + pgvector   │    │  Vector Store        │
                    │  (port 5432)  │    │  (TF-IDF fallback)   │
                    └───────────────┘    └──────────────────────┘
                              │
                    ┌─────────┴──────┐
                    │   Ollama LLM   │
                    │  (port 11434)  │
                    │  qwen / llama  │
                    └───────────────┘
```

### Self-Healing Design

| Component | Primary | Fallback |
|-----------|---------|----------|
| LLM | Ollama (local) | Google Gemini |
| OCR | PaddleOCR | EasyOCR then Tesseract |
| Vector Search | ChromaDB | TF-IDF keyword search |
| Semantic Search | Python vector API | PostgreSQL ILIKE |

---

## Tech Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| React 18 + TypeScript | UI framework |
| Vite 5 | Build tool with lazy code-splitting |
| TailwindCSS + ShadCN UI | Component library |
| React Router v6 | Client-side routing |
| TanStack Query v5 | Server state management |
| Zustand | Client state (auth, theme, sidebar) |
| Framer Motion | Animations |
| Recharts | Analytics charts |
| React Hook Form + Zod | Form validation |

### API Gateway (Node.js)
| Technology | Purpose |
|------------|---------|
| Express.js | HTTP server |
| PostgreSQL (pg) | Primary database |
| JWT (jsonwebtoken) | Authentication |
| Helmet | Security headers |
| express-rate-limit | Rate limiting |
| Multer | File upload handling |
| Axios | AI service proxy |

### Python AI Service (FastAPI)
| Technology | Purpose |
|------------|---------|
| FastAPI + Uvicorn | Async HTTP server |
| SQLAlchemy | ORM |
| PaddleOCR | Primary OCR engine |
| EasyOCR | Secondary OCR engine |
| Tesseract (pytesseract) | Tertiary OCR fallback |
| OpenCV | Image preprocessing |
| SentenceTransformers | Embeddings (multilingual-e5-base) |
| ChromaDB | Vector store |
| Ollama | Local LLM inference |
| Google Generative AI | Cloud LLM fallback |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| PostgreSQL 16 + pgvector | Primary DB with vector support |
| Redis 7 | Caching layer |
| Docker + Compose | Container orchestration |
| Nginx | Frontend reverse proxy |
| Ollama | Local LLM runtime |

---

## Features

### Resume Ingestion
- Upload via drag-and-drop or file picker
- Supported formats: PDF, Scanned PDF, PNG, JPEG, TIFF, BMP, WEBP, DOC, DOCX, HEIC
- Bulk upload (multiple files simultaneously)
- Real-time per-file status: queued, processing, success, or failed
- OCR engine and confidence score displayed after processing

### Intelligent OCR Pipeline
- OpenCV preprocessing: grayscale, deskew, denoise, adaptive threshold, contrast enhancement
- 3-tier engine cascade: PaddleOCR then EasyOCR then Tesseract
- Per-page confidence scoring stored in the database
- Multilingual support (English and Hindi)

### Resume Parsing
Structured JSON extraction of:
- Personal: name, email, phone, address, location
- Professional: experience years, primary domain, current role, industry
- Skills: comma-separated skill list, equipment operated
- Education: degree, institution, year
- Certifications: name, issuer, registration number, expiry date
- Job preferences: availability, notice period, expected salary
- Safety certs: DGMS, OSHA, Boiler, Crane, ASME (flagged as critical for compliance)

### Candidate Scoring and Matching
- Vector similarity (SentenceTransformers embeddings vs JD embeddings)
- Skills overlap scoring
- Safety certification compliance bonus/penalty
- LLM explanation of why a candidate scored what they scored
- Auto-trigger: creating a new job automatically scores all active candidates
- Rankings view per job, per candidate job recommendations

### AI HR Assistant (Agent)
- Conversational chat with context memory
- RAG over stored candidate profiles and job descriptions
- Answers questions like "Who has 5+ years welding experience?" or "Compare candidate A and B"
- Backed by Ollama (local) with Gemini fallback
- Agent processing logs visible in UI

### Analytics
- Skills distribution bar chart
- Hiring funnel visualisation
- Candidate source breakdown
- Domain distribution across all candidates

### Export
- Export full candidate list to CSV with status filter
- `GET /api/candidates/export/csv?status=shortlisted`

### Security
- JWT authentication with refresh tokens
- bcrypt password hashing (cost factor 10)
- Helmet security headers
- Rate limiting: 200 req/min global, 10/min on login, 30/min on uploads
- File type validation (MIME type + extension)
- 50MB file size limit
- SQL parameterised queries throughout — no injection vectors

---

## Quick Start

### Prerequisites
- Docker and Docker Compose
- 8GB RAM minimum (16GB recommended with Ollama)
- NVIDIA GPU optional — Ollama runs on CPU

### 1. Clone and configure

```bash
git clone https://github.com/RockRK2405/Recruitment-Digitisation-System.git
cd Recruitment-Digitisation-System
cp .env.example .env
# Edit .env with your values
```

### 2. Start without Ollama (cloud LLM via Gemini)

```bash
# Set GEMINI_API_KEY in .env first
docker compose up -d
```

### 3. Start with Ollama (fully local, no cloud calls)

```bash
docker compose --profile ai up -d
docker exec -it recruitment-digitisation-system-ollama-1 ollama pull qwen2.5:7b
```

### 4. Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API Gateway | http://localhost:4000 |
| Python AI API Docs | http://localhost:8000/docs |
| Ollama | http://localhost:11434 |

**Default credentials:**

| Username | Password | Role |
|----------|----------|------|
| `admin` | `password123` | Admin |
| `recruiter` | `password123` | Recruiter |
| `viewer` | `password123` | Viewer |

> Change all passwords immediately in production.

---

## Environment Variables

```env
# Database
POSTGRES_PASSWORD=postgres_secure_pwd_2026
JWT_SECRET=change-this-to-a-long-random-string-in-production

# LLM — 'ollama' uses local inference, 'gemini' uses Google cloud
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b
GEMINI_API_KEY=

# CORS
CORS_ORIGIN=http://localhost:3000
```

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/refresh` | Refresh token |

### Candidates
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/candidates` | List with search, status, domain, page filters |
| GET | `/api/candidates/:id` | Full candidate profile |
| PATCH | `/api/candidates/:id/status` | Update pipeline status |
| GET | `/api/candidates/:id/timeline` | Agent processing timeline |
| GET | `/api/candidates/export/csv` | Export to CSV (optional status filter) |

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | List job descriptions |
| POST | `/api/jobs` | Create JD (auto-triggers match scoring) |
| PUT | `/api/jobs/:id` | Update JD |
| DELETE | `/api/jobs/:id` | Delete JD |

### Resume Upload
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/resumes/upload` | Upload single resume |
| POST | `/api/resumes/bulk-upload` | Upload multiple resumes |
| GET | `/api/resumes/profile/:candidateId` | Parsed candidate profile |
| GET | `/api/resumes/document/:docId` | Raw OCR text and metadata |

### Matching
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/matching/rank/:jobId` | Ranked candidates for a job |
| GET | `/api/matching/score?candidateId&jobId` | Single match score |
| GET | `/api/matching/recommendations/:candidateId` | Job recommendations for a candidate |
| POST | `/api/matching/semantic` | Natural language candidate search |
| GET | `/api/matching/explain/:candidateId/:jobId` | Score explanation breakdown |
| POST | `/api/match/trigger` | Batch score all candidates vs a job |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/metrics` | Dashboard KPIs |
| GET | `/api/analytics/skills` | Skills distribution |
| GET | `/api/analytics/funnel` | Hiring funnel |
| GET | `/api/analytics/sources` | Resume source breakdown |

### AI Agent
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/agent/chat` | Chat with HR assistant |
| GET | `/api/agent/logs` | Recent agent processing logs |

---

## Frontend Pages

| Route | Page | Description |
|-------|------|-------------|
| `/dashboard` | Dashboard | KPIs, recent activity, pipeline summary |
| `/candidates` | Candidates | Searchable filterable candidate list |
| `/candidates/:id` | Profile | Full candidate profile with certifications and scores |
| `/jobs` | Jobs | Job descriptions with create JD dialog |
| `/resumes` | Resume Upload | Drag-and-drop upload with real-time status |
| `/matching` | AI Matching | Job-based ranking and semantic search |
| `/analytics` | Analytics | Charts for skills, funnel, and sources |
| `/agent` | AI Agent | Conversational HR assistant |
| `/settings` | Settings | LLM configuration, theme, system status |

All pages are lazy-loaded — only the current page JS chunk downloads on navigation.

---

## AI Pipeline

```
Resume File
    │
    ▼
1. Intake Agent       Validate file, classify type (resume/cert/ID), save to disk
    │
    ▼
2. OCR Pipeline       OpenCV preprocess → PaddleOCR → EasyOCR → Tesseract
   + Vision Agent     Visual document classification, certificate authenticity check
    │
    ▼
3. LLM Parser         Ollama/Gemini → structured JSON profile
                      Regex heuristic fallback when LLM is offline
    │
    ▼
4. Verification       Safety cert audit (DGMS, OSHA, Boiler, Crane, ASME)
   Agent              Anomaly detection, identity flag
    │
    ▼
5. DB Storage         Candidate + Resume + Certifications → PostgreSQL
    │
    ▼
6. Embeddings         multilingual-e5-base → ChromaDB vector store
    │
    ▼
7. Match Scoring      Vector similarity + skills overlap + cert compliance scoring
```

---

## LLM Provider Configuration

The platform uses a unified provider abstraction at `services/llm/provider.py`. All resume parsing, chatbot, and scoring calls route through it.

| Setting | Value | Effect |
|---------|-------|--------|
| `LLM_PROVIDER=ollama` | Default | Uses local Ollama, auto-falls back to Gemini |
| `LLM_PROVIDER=gemini` | Cloud | Skips Ollama, uses Gemini directly |
| `GEMINI_API_KEY=AIza...` | Required for fallback | Enables cloud fallback |
| `OLLAMA_MODEL=qwen2.5:7b` | Any pulled model | Selects local inference model |

---

## OCR Pipeline

```
Input Image or PDF
      │
      ▼
OpenCV Preprocessing
  ├── Grayscale conversion
  ├── Deskew (Hough transform rotation correction)
  ├── Denoise (fastNlMeansDenoising)
  ├── Adaptive threshold (Otsu / Gaussian)
  └── CLAHE contrast enhancement
      │
      ▼
Engine Cascade
  1. PaddleOCR — PP-OCRv4, English + Hindi
     └── if confidence below threshold or failure:
  2. EasyOCR — LSTM-based, multilingual
     └── if failure:
  3. Tesseract 4.x — LSTM mode, eng+hin
      │
      ▼
Confidence Scoring
  Weighted average per page stored in uploaded_documents.ocr_confidence
  Surfaced in the UI after each upload
```

---

## Database Schema

Core tables:

| Table | Key Columns |
|-------|-------------|
| `candidates` | id, name, email, phone, location, status, low_literacy_flag, created_at |
| `resumes` | candidate_id, skills_list (TEXT), primary_domain, experience_years, raw_text, equipment_handled, languages, notice_period, expected_salary |
| `certifications` | candidate_id, name, issuer, registration_number, expiry_date, verification_status |
| `job_descriptions` | title, description, required_skills (ARRAY), required_certifications (ARRAY), status |
| `match_results` | candidate_id, job_id, overall_score, vector_score, skill_score, agent_score, match_explanation |
| `uploaded_documents` | candidate_id, filename, mime_type, ocr_confidence, ocr_text, status |
| `users` | username, password_hash, role (admin/recruiter/viewer) |

Full schema with indexes: [`database/schema.sql`](database/schema.sql)

---

## Deployment

### Production

```bash
export JWT_SECRET="$(openssl rand -hex 32)"
export GEMINI_API_KEY=your_key_here
docker compose up -d --build
```

### Services

| Service | Port | Notes |
|---------|------|-------|
| frontend | 3000 | Nginx serving React build |
| api-gateway | 4000 | Node.js Express |
| python-api | 8000 | FastAPI with OCR |
| postgres | 5432 | pgvector enabled |
| redis | 6379 | Optional caching |
| ollama | 11434 | Only with `--profile ai` |

### Without Ollama (recommended for cloud)

```bash
LLM_PROVIDER=gemini GEMINI_API_KEY=your_key docker compose up -d
```

---

## Developer Guide

### Project Structure

```
├── frontend/              React 18 + Vite frontend
│   ├── src/pages/         9 lazy-loaded page components
│   ├── src/components/    Shared UI (layout, shared, ui)
│   └── nginx.conf         Production nginx with SPA fallback
│
├── api-gateway/           Node.js Express gateway (port 4000)
│   └── src/routes/        auth, candidates, jobs, matching, resumes, analytics, agent
│
├── api/                   Python FastAPI AI service (port 8000)
│   └── routes/            resumes, match, jobs, agent, analytics, vision, review
│
├── services/              Python service modules
│   ├── llm/               Unified LLM provider abstraction
│   ├── agents/            7-stage orchestrator pipeline
│   ├── ocr/               OCR engine cascade + OpenCV
│   ├── resume_parser/     LLM + regex extraction
│   ├── embeddings/        SentenceTransformers + ChromaDB
│   ├── matching/          Candidate scoring engine
│   └── chatbot/           HR assistant chat
│
├── database/schema.sql    PostgreSQL schema with all indexes
└── docker-compose.yml     Full-stack container orchestration
```

### Running locally

```bash
# Infrastructure only
docker compose up postgres redis -d

# Python AI service
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# API Gateway
cd api-gateway && npm install && npm run dev

# Frontend
cd frontend && npm install && npm run dev
# Opens at http://localhost:3000
```

### Type checking

```bash
cd api-gateway && npx tsc --noEmit
cd frontend && npm run build
```

### Candidate status flow

```
new → screening → shortlisted → interview → offered → hired
                                                    ↘ rejected
```

Update: `PATCH /api/candidates/:id/status` with `{ "status": "shortlisted" }`

---

*Built for heavy industry HR. Designed to run fully offline with local LLMs.*
