import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from config.settings import settings
from config.logging_config import logger
from database.connection import get_db
from database.models import Candidate, UploadedDocument, Resume
from services.agents.orchestrator import AgentOrchestrator

router = APIRouter()

# Directory to save files temporarily
UPLOAD_DIR = settings.UPLOAD_DIR

@router.post("/upload", summary="Digitize, parse, and verify a physical or digital resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Accepts a photo of a resume (JPEG/PNG) or scanned PDF.
    Triggers the multi-stage AI Agent workflow synchronously to:
    1. Clean the image and extract text (OpenCV + PaddleOCR/Tesseract).
    2. Extract candidate information (LLM Parser).
    3. Audit safety certifications & flag anomalies (Verification Agent).
    4. Generate custom WhatsApp onboarding alerts (Notification Agent).
    """
    # 1. Save uploaded file to local disk
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".pdf", ".png", ".jpg", ".jpeg", ".heic"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{file_ext}'. Please upload an image (PNG, JPG, HEIC) or PDF."
        )
        
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"{os.urandom(8).hex()}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Received upload. File saved to local storage: {file_path}")
    except Exception as e:
        logger.error(f"Failed to write file to disk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save file on server: {str(e)}")

    # 2. Hand off to the Event-Driven AI Agent Orchestrator
    try:
        state = AgentOrchestrator.process_resume(file_path)
        
        if state.status == "failed":
            raise HTTPException(
                status_code=422,
                detail={"message": "AI recruitment agents failed to ingest resume.", "errors": state.errors}
            )
            
        return {
            "run_id": state.run_id,
            "status": state.status,
            "ocr_engine_used": state.ocr_engine,
            "ocr_confidence": round(state.ocr_confidence * 100, 1),
            "candidate_id": state.candidate_id,
            "parsed_profile": state.parsed_profile,
            "verification_status": state.verification_results.get("identity_status"),
            "anomalies_detected": state.verification_results.get("anomalies_detected", []),
            "sms_whatsapp_alert": state.notifications_prepared.get("message_body"),
            "agent_audit_logs": [f"[{log['agent']}] - {log['message']}" for log in state.agent_logs]
        }
    except Exception as e:
        logger.error(f"Agent Orchestrator call failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI Agent pipeline failed: {str(e)}")


@router.post("/bulk-upload", summary="Ingest multiple physical/scanned resumes in batch")
async def bulk_upload_resumes(files: List[UploadFile] = File(...)):
    """Ingests multiple documents in a loop, returning aggregated batch status."""
    results = []
    logger.info(f"Initializing bulk upload ingestion of {len(files)} documents...")
    
    for file in files:
        try:
            # 1. Save file
            file_path = os.path.join(UPLOAD_DIR, f"bulk_{os.urandom(4).hex()}_{file.filename}")
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            # 2. Trigger Orchestrator
            state = AgentOrchestrator.process_resume(file_path)
            
            results.append({
                "filename": file.filename,
                "status": state.status,
                "candidate_id": state.candidate_id,
                "candidate_name": state.parsed_profile.get("name") if state.parsed_profile else None,
                "verification": state.verification_results.get("identity_status")
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "failed",
                "error": str(e)
            })
            
    return {
        "batch_size": len(files),
        "processed_count": len(results),
        "results": results
    }


@router.get("/profile/{candidate_id}", summary="Retrieve a candidate's structured profile")
def get_candidate_profile(candidate_id: int, db: Session = Depends(get_db)):
    """Retrieves full candidate profile including certifications, education, and source file metadata."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found in recruitment system.")
        
    resume = candidate.resume
    certs = [{"name": c.name, "issuer": c.issuer, "status": c.verification_status} for c in candidate.certifications]
    
    return {
        "id": candidate.id,
        "name": candidate.name,
        "phone": candidate.phone,
        "email": candidate.email,
        "location": candidate.location,
        "status": candidate.status,
        "low_literacy_flag": candidate.low_literacy_flag,
        "created_at": candidate.created_at,
        "resume": {
            "experience_years": resume.experience_years if resume else 0.0,
            "skills": [s.strip() for s in (resume.skills_list or "").split(",") if s.strip()] if resume else [],
            "primary_domain": resume.primary_domain if resume else None,
            "equipment_handled": [e.strip() for e in (resume.equipment_handled or "").split(",") if e.strip()] if resume else [],
            "languages": [l.strip() for l in (resume.languages or "").split(",") if l.strip()] if resume else [],
            "education": resume.education if resume else None,
            "availability": resume.availability if resume else None
        },
        "certifications": certs
    }


@router.get("/document/{doc_id}", summary="Retrieve raw extracted OCR text of an upload")
def get_ocr_document(doc_id: int, db: Session = Depends(get_db)):
    """Retrieves a digitized source file's original text and confidence details."""
    doc = db.query(UploadedDocument).filter(UploadedDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Ingested document reference not found.")
        
    return {
        "id": doc.id,
        "filename": doc.filename,
        "mime_type": doc.mime_type,
        "ocr_confidence": doc.ocr_confidence,
        "status": doc.status,
        "created_at": doc.created_at,
        "raw_text": doc.ocr_text
    }
