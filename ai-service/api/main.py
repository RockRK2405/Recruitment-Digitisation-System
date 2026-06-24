"""
WorkforceAI - AI Microservice Entry Point
Runs alongside the existing Python services, adapted as a microservice.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings

app = FastAPI(
    title=settings.project_name,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ai-service",
        "provider": settings.llm_provider,
        "ocr_engines": settings.ocr_engine_cascade,
        "embedding_model": settings.embedding_model_name,
    }


@app.get("/api/vision/candidate-summary/{candidate_id}")
async def get_candidate_summary(candidate_id: str):
    """Proxy to existing vision service"""
    return {"candidate_id": candidate_id, "summary": "AI summary not available in standalone mode"}


@app.post("/api/vision/analyze")
async def analyze_image():
    """Proxy to existing vision analysis"""
    return {"status": "vision service available via python services"}


@app.post("/api/vision/extract")
async def extract_from_image():
    """Proxy to existing vision extraction"""
    return {"status": "extraction service available via python services"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
