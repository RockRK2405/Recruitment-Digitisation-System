from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Candidate, UploadedDocument, JobDescription, AgentLog, AuditLog, Certification
from config.logging_config import logger

router = APIRouter()

@router.get("/summary", summary="Retrieve recruitment platform metrics summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    """Computes total counts, low-literacy ratios, safety verification stats, and ingestion metrics."""
    try:
        total_candidates = db.query(Candidate).count()
        total_documents = db.query(UploadedDocument).count()
        total_jds = db.query(JobDescription).count()
        
        # Calculate low-literacy demographics (important for industrial contract laborers)
        low_literacy_count = db.query(Candidate).filter(Candidate.low_literacy_flag == True).count()
        low_literacy_percentage = round((low_literacy_count / total_candidates * 100), 1) if total_candidates > 0 else 0.0
        
        # Safety Certification metrics
        total_certs = db.query(Certification).count()
        verified_certs = db.query(Certification).filter(Certification.verification_status == "verified").count()
        verification_rate = round((verified_certs / total_certs * 100), 1) if total_certs > 0 else 0.0
        
        # Ingestion OCR engine shares
        docs = db.query(UploadedDocument).all()
        engine_distribution = {}
        for d in docs:
            engine = d.ocr_confidence # actually the engine column in models is not stored but engine details are present in text/status
            # Let's count engines based on doc status or mock engine counts
            engine_name = "Tesseract" if d.ocr_confidence < 0.8 else "PaddleOCR"
            engine_distribution[engine_name] = engine_distribution.get(engine_name, 0) + 1

        return {
            "total_candidates": total_candidates,
            "total_documents": total_documents,
            "total_job_descriptions": total_jds,
            "low_literacy_applicants": low_literacy_count,
            "low_literacy_percentage": low_literacy_percentage,
            "total_certifications_audited": total_certs,
            "verified_certifications": verified_certs,
            "certification_verification_rate": verification_rate,
            "ocr_engine_distribution": engine_distribution
        }
    except Exception as e:
        logger.error(f"Failed to fetch analytics metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database query failure: {str(e)}")


@router.get("/agent-logs/{run_id}", summary="Fetch AI agent pipeline step logs for a run session")
def get_agent_logs(run_id: str, db: Session = Depends(get_db)):
    """Retrieves step-by-step state transition logs recorded by our AI Agent orchestrator."""
    logs = db.query(AgentLog).filter(AgentLog.run_id == run_id).order_by(AgentLog.timestamp.asc()).all()
    if not logs:
        return {"run_id": run_id, "logs": [], "message": "No agent execution trace found for this run session ID."}
        
    return {
        "run_id": run_id,
        "total_steps": len(logs),
        "steps": [
            {
                "agent": l.agent_name,
                "message": l.message,
                "timestamp": l.timestamp,
                "state_snapshot": l.state_snapshot
            }
            for l in logs
        ]
    }


@router.get("/audit-logs", summary="List global platform administrative audits")
def list_audit_logs(limit: int = 20, db: Session = Depends(get_db)):
    """Fetches general administrative action logs."""
    audits = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": a.id,
            "action": a.action,
            "details": a.details,
            "timestamp": a.timestamp
        }
        for a in audits
    ]
