#  Kshamata: AI-Powered Industrial Workforce Recruitment Platform

Kshamata ("Capability/Skill" in Hindi) is a production-grade, compliance-first, AI-driven workforce digitization and resume intelligence platform specifically engineered for low-literacy, high-noise industrial sectors:
*   **Mining & Quarrying** (Coal, Minerals, Open-cast, Underground)
*   **Thermal & Power Plants** (Boiler operations, Turbine technicians)
*   **Steel & Metallurgy Plants** (Foundry, Fabricators, Welders)
*   **Manufacturing, Logistics, and Heavy Construction**

---

##  Executive Summary & Problem Context

In heavy industrial sectors, blue-collar and grey-collar contract laborers (e.g. heavy excavator operators, crane riggers, high-pressure welders, certified electricians) are crucial for operational safety and throughput. However:
1.  **Low Digital Literacy:** Most workers do not possess digital profiles; they submit crumpled, wet, or handwritten physical resumes/hardcopies, often in regional languages (Hindi, Spanish, etc.).
2.  **Strict Safety & Compliance Constraints:** Hiring a worker without mandatory regulatory licenses (e.g., a **DGMS mining gas certificate**, **Grade-A Boiler attendant card**, or **ASME welder stamp**) exposes operations to catastrophic failure, regulatory fines, and shutdown.
3.  **Noisy Mobile Photos:** Document scans uploaded by field contractors are typically low-quality, angled mobile camera photos with grease stains and wrinkles.

**Kshamata** digitizes these noisy inputs, extracts structural qualifications using Google Gemini LLMs, audits safety certificates against regulatory requirements, and ranks workers using a compliance-aware similarity matcher.

---

##  Architecture & Self-Healing Fallbacks

Kshamata is built for **resiliency** and is engineered with an enterprise-grade **Self-Healing Architecture** that guarantees full system execution even in restricted, offline, or non-dockerized local environments:

```
+--------------------------------------------------------------------------------+
|                             KSHAMATA PLATFORM SYSTEM                           |
+--------------------------------------------------------------------------------+
|                                                                                |
|   1. INGESTION  ===>  2. IMAGE OCR PREPROCESSING ===> 3. AI AGENT FLOW ENGINE  |
|   [Scanned PDF]       [Grayscale Conversion]          [Intake & Cleaning]      |
|   [Mobile Photo]      [Binarization & De-skew]        [Structured Extraction]  |
|                       [Dual-OCR Fallbacks]            [Credential Compliance]  |
|                                                       [WhatsApp Notification]  |
|                                                                                |
|                                       ||                                       |
|                                       \/                                       |
|                                                                                |
|   4. INDEX & VECTOR STORE   <======================== 5. HYBRID MATCH ENGINE   |
|   [SentenceTransformers]                              [Conversational Query]   |
|   [ChromaDB Vector Store]                             [Skill-Aware Overlap]    |
|   [SQLite fallback vector]                            [Safety Cert Audits]     |
|                                                       [50% Penalty Flags]      |
|                                                                                |
+--------------------------------------------------------------------------------+
```

### 1. Dual-Engine OCR Pipeline
*   **Digital Extract first:** Born-digital PDFs bypass expensive image rendering and instantly pull raw text streams using `pdfplumber`.
*   **PaddleOCR Primary:** Scanned pages run through PaddleOCR to handle non-English text blocks and tabular certificate grids.
*   **Tesseract OCR Fallback:** If PaddleOCR is unavailable (e.g., missing system binaries or compile errors), it catches the exception and executes Tesseract (`pytesseract`).
*   **Simulated Backup Parser:** If all OCR binaries fail, it injects a highly accurate blue-collar candidate template to ensure developers can run end-to-end trials immediately.

### 2. Relational Database Self-Healing redirect
*   **Primary Database:** Connects to PostgreSQL inside Docker.
*   **Self-Healing Fallback:** If a PostgreSQL server is not running on the local host (e.g. `Connection refused` error), the application catches the error and creates an embedded SQLite database file locally (`./data/local_fallback.db`).

### 3. Semantic Vector Store Fallback
*   **Primary Store:** Indexes candidate profiles in ChromaDB utilizing multilingual `intfloat/multilingual-e5-base` SentenceTransformers.
*   **Offline Fallback:** If models cannot download or ChromaDB libraries fail, the system initializes a pure-Python hash-based TF-IDF vectorizer and calculates manual NumPy cosine-similarities, ensuring semantic candidate searches run completely offline.

---

##  Local Quickstart Guide

You can run the entire platform locally with zero infrastructure configuration.

### 1. Install System Dependencies (Recommended)
To run the standard OpenCV and Tesseract fallbacks, install these packages via your package manager:
*   **macOS (Homebrew):**
    ```bash
    brew install tesseract poppler
    ```
*   **Ubuntu/Linux:**
    ```bash
    sudo apt-get update && sudo apt-get install -y tesseract-ocr poppler-utils libgl1-mesa-glx
    ```

### 2. Configure Environment & Python
1.  Clone the repository and move into it.
2.  Install Python dependencies:
    ```bash
    pip3 install -r requirements.txt
    ```
3.  **Active In-Process LLM Provider:**
    *   **Local LLM (Default & 100% Free):** Kshamata is configured out-of-the-box to use **Ollama** running your local **`gemma4:e4b`** model locally inside [services/resume_parser/parser.py](file:///Users/rudrakhale/Desktop/Recruitment%20Digitisation%20System/services/resume_parser/parser.py). It requires no API key, does not call the internet, and runs fully on your machine at **zero cost**!
    *   **Regex Fallback (100% Free):** If your local Ollama server is offline or fails, Kshamata automatically falls back to our local regex heuristics in pure Python, which is also completely offline and free.
    *   **Gemini Option:** If you ever want to use external Gemini APIs, you can swap the provider in `.env` by setting `LLM_PROVIDER=gemini` and providing your `GEMINI_API_KEY=""` (which offers a generous free tier in Google AI Studio).

### 3. Initialize & Seed Database
Build the SQL schemas and seed standard job descriptions (Boiler Attendant, Mining Sirdar, etc.) with a mock worker process trace:
```bash
python3 scripts/seed_data.py
```

### 4. Launch Standalone UI (Standard Run)
Start the Streamlit dashboard:
```bash
streamlit run ui/app.py
```
Visit `http://localhost:8501` to view Kshamata! You can upload resumes, query conversational lookups, match workers, and trace agent logs standalone!

### 5. Launch FastAPI Backend Server (Optional)
If you wish to run the backend microservice alongside the Streamlit UI:
```bash
uvicorn api.main:app --reload --port 8000
```
Visit `http://localhost:8000/docs` to view the beautiful interactive Swagger REST API documentation.

---

##  Production Docker Ingestion

To deploy the entire stack in production (PostgreSQL + FastAPI + Streamlit):

### 1. Build and Run containers
```bash
docker-compose up --build
```

### 2. Port Allocation
*   **Streamlit Recruiter Dashboard:** `http://localhost:8501`
*   **FastAPI REST Microservice:** `http://localhost:8000`
*   **Interactive Swagger Documentation:** `http://localhost:8000/docs`
*   **PostgreSQL Port:** `5432`

---

## 🤖 AI Event-Driven Agents Crew

Every upload is dispatched to an AI crew orchestrated sequentially:
1.  **Intake Agent (`services/agents/intake.py`):** Coordinates OpenCV thresholding, runs dual-OCR fallbacks, and writes digitized document files.
2.  **Screening Agent (`services/agents/screening.py`):** Runs LLM structured Pydantic parser, inserts applicant profiles into the database, and indexes them in ChromaDB.
3.  **Verification Agent (`services/agents/verification.py`):** Audits safety certificates and flags age/experience anomalies.
4.  **Notification Agent (`services/agents/notification.py`):** Prepares custom WhatsApp onboarding messages in the applicant's native tongue (Hindi, etc.).

*You can trace their step-by-step executions, timestamp logs, and Pydantic state snapshots in real-time on the **AI Agent Flow Monitor** tab in Streamlit.*

---

##  Compliance-First Matching Logic

Industrial operations weight safety certifications heavily. Our matching algorithm computes scores (0 to 100) using a strict weighted average:
*   **Semantic Alignment (40%):** Evaluates overall candidate experience vs job scope.
*   **Technical Skills Overlap (30%):** Counts matched mechanical skills (e.g. Arc Welding, Blasting).
*   **Safety Compliance Score (30%):** Audits required regulatory licenses (e.g. DGMS gas check).

> [!CAUTION]
> **COMPLIANCE PENALTY:**
> If a job description lists mandatory safety certifications (e.g. DGMS Mining Sirdar) and the applicant is missing ALL of them, the platform automatically applies a **50% total match score deduction penalty** and flags a critical compliance alert!
