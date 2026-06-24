import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config.settings import settings
from config.logging_config import logger
from database.connection import Base, engine

# Import Routers
from api.routes import resumes, jobs, match, analytics, documents, vision, review

# Initialize FastAPI App with Swagger description
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise-grade AI-powered Industrial Workforce Recruitment & Digitisation platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Standard CORS Middleware for frontend web requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middleware to log request-response cycles
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"API Request: {request.method} {request.url.path} - "
        f"Response Status: {response.status_code} - "
        f"Duration: {duration:.4f}s"
    )
    return response

# Custom Exception Handler for operational errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Exception on {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# Root endpoint returning platform health status
@app.get("/", tags=["Health Monitor"])
def read_root():
    return {
        "status": "online",
        "app_name": settings.PROJECT_NAME,
        "environment": settings.ENV,
        "api_docs": "/docs",
        "system_time": time.asctime()
    }

# Register Routers
app.include_router(resumes.router, prefix="/api/resumes", tags=["Resumes Ingestion & OCR"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Job Descriptions"])
app.include_router(match.router, prefix="/api/match", tags=["Semantic Search & Match Engine"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics & Logs"])
app.include_router(documents.router, prefix="/api/documents", tags=["Multi-Modal Documents Ingestion"])
app.include_router(vision.router, prefix="/api/vision", tags=["Vision-Language Model (VLM)"])
app.include_router(review.router, prefix="/api/review", tags=["Recruiter Review & Feedback"])
