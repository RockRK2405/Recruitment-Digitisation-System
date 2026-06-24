import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from config.settings import settings
from config.logging_config import logger
from database.connection import get_db
from database.models import Candidate, UploadedDocument, DocumentUploadBatch
from services.agents.orchestrator import AgentOrchestrator
from services.document_intelligence.classifier import DocumentClassifier

router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR

@router.post("/upload-batch", summary="Upload and process multiple candidate documents in a single batch")
async def upload_batch(files: List[UploadFile] = File(...)):
    """
    Accepts multiple documents (resumes, certificates, experience letters, etc.).
    Triggers the multi-stage AI Agent workflow to process the entire batch.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    file_paths = []
    logger.info(f"Received batch upload of {len(files)} files")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    for file in files:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in [".pdf", ".png", ".jpg", ".jpeg", ".heic", ".tiff"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{file_ext}' for file {file.filename}. Supported: PDF, PNG, JPG, JPEG, HEIC, TIFF."
            )
        
        file_path = os.path.join(UPLOAD_DIR, f"batch_{os.urandom(8).hex()}_{file.filename}")
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_paths.append(file_path)
            logger.info(f"Saved batch file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to write file {file.filename} to disk: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save file on server: {str(e)}")

    try:
        # Hand off to orchestrator
        state = AgentOrchestrator.process_documents(file_paths)
        
        if state.status == "failed":
            raise HTTPException(
                status_code=422,
                detail={"message": "AI document intelligence agents failed to process batch.", "errors": state.errors}
            )

        # Build classification details for response
        classifications = []
        for path, cls_info in state.document_classifications.items():
            classifications.append({
                "filename": os.path.basename(path),
                "doc_type": cls_info.get("doc_type"),
                "confidence": cls_info.get("confidence"),
                "classification_method": cls_info.get("classification_method")
            })

        return {
            "batch_id": state.batch_id,
            "run_id": state.run_id,
            "status": state.status,
            "candidate_id": state.candidate_id,
            "classifications": classifications,
            "verification_status": state.verification_results.get("identity_status", "pending"),
            "anomalies_detected": state.verification_results.get("anomalies_detected", []),
            "agent_audit_logs": [f"[{log['agent']}] - {log['message']}" for log in state.agent_logs]
        }
    except Exception as e:
        logger.error(f"Agent Orchestrator batch execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI Agent batch pipeline failed: {str(e)}")


@router.post("/classify", summary="Classify a single uploaded document")
async def classify_document(file: UploadFile = File(...)):
    """
    Uploads a document, extracts text using a simple fast fallback or full OCR,
    and returns its document type classification.
    """
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".pdf", ".png", ".jpg", ".jpeg", ".heic", ".tiff"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{file_ext}'. Supported: PDF, PNG, JPG, JPEG, HEIC, TIFF."
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"classify_{os.urandom(8).hex()}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to write file to disk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save file on server: {str(e)}")

    try:
        # Perform light OCR or read text to classify
        from services.ocr.engine import OcrEngine
        ocr_result = OcrEngine.extract_text(file_path)
        text = ocr_result.get("text", "")
        
        classification = DocumentClassifier.classify(text)
        
        # Cleanup temp file
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return {
            "filename": file.filename,
            "doc_type": classification.get("doc_type"),
            "doc_type_display": classification.get("doc_type_display"),
            "confidence": classification.get("confidence"),
            "all_scores": classification.get("all_scores"),
            "classification_method": classification.get("classification_method")
        }
    except Exception as e:
        # Cleanup on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Classification failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.get("/candidate/{candidate_id}", summary="List all uploaded documents for a candidate")
def get_candidate_documents(candidate_id: int, db: Session = Depends(get_db)):
    """
    Retrieves all documents associated with a candidate, including their classification,
    OCR text, confidence, and engine metadata.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    batches = db.query(DocumentUploadBatch).filter(DocumentUploadBatch.candidate_id == candidate_id).all()
    batch_ids = [b.id for b in batches]
    
    documents = db.query(UploadedDocument).filter(
        (UploadedDocument.batch_id.in_(batch_ids)) | 
        (UploadedDocument.id == (candidate.resume.uploaded_doc_id if candidate.resume else None))
    ).all() if (batch_ids or (candidate.resume and candidate.resume.uploaded_doc_id)) else []
    
    # Also fetch direct references if we missed them
    if candidate.resume and candidate.resume.uploaded_doc_id:
        direct_doc = db.query(UploadedDocument).filter(UploadedDocument.id == candidate.resume.uploaded_doc_id).first()
        if direct_doc and direct_doc not in documents:
            documents.append(direct_doc)
            
    results = []
    seen = set()
    for doc in documents:
        if doc.id in seen:
            continue
        seen.add(doc.id)
        results.append({
            "id": doc.id,
            "filename": doc.filename,
            "doc_type": doc.doc_type,
            "doc_type_confidence": doc.doc_type_confidence,
            "ocr_confidence": doc.ocr_confidence,
            "status": doc.status,
            "created_at": doc.created_at,
            "total_pages": doc.total_pages,
            "ocr_engine_used": doc.ocr_engine_used
        })
        
    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate.name,
        "total_documents": len(results),
        "documents": results
    }
