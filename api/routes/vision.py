import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.orm import Session
from config.settings import settings
from config.logging_config import logger
from database.connection import get_db
from database.models import Candidate, UploadedDocument, DocumentUploadBatch
from services.document_intelligence.vision_model import VisionModel

router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR

@router.post("/analyze", summary="Analyze an uploaded document image with a custom question")
async def analyze_image(
    file: UploadFile = File(...),
    question: str = Form(...)
):
    """
    Uploads an image, sends it to the vision model (Ollama LLaVA or Gemini),
    and returns the model's answer to a custom question.
    """
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".png", ".jpg", ".jpeg", ".heic", ".webp", ".bmp", ".tiff"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format '{file_ext}'. Supported: PNG, JPG, JPEG, WEBP, BMP, TIFF, HEIC."
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"vision_qa_{os.urandom(8).hex()}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to write file to disk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save file on server: {str(e)}")

    try:
        result = VisionModel.analyze_image(file_path, question)
        
        # Cleanup temp file
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return result
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Vision analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")


@router.post("/extract", summary="Extract structured data directly from a document image using VLM")
async def extract_image_data(file: UploadFile = File(...)):
    """
    Uploads a document image and runs a vision model to parse structured fields
    (e.g., name, dates, certificate registry number) without standard OCR pipelines.
    """
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".png", ".jpg", ".jpeg", ".heic", ".webp", ".bmp", ".tiff"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format '{file_ext}'. Supported: PNG, JPG, JPEG, WEBP, BMP, TIFF, HEIC."
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"vision_ext_{os.urandom(8).hex()}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to write file to disk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save file on server: {str(e)}")

    try:
        result = VisionModel.extract_from_image(file_path)
        
        # Cleanup temp file
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return result
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Vision extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Vision extraction failed: {str(e)}")


@router.get("/candidate-summary/{candidate_id}", summary="Synthesize a profile summary across all candidate document images")
def get_candidate_summary(candidate_id: int, db: Session = Depends(get_db)):
    """
    Finds all image-based documents uploaded for a candidate and uses the VLM
    to synthesize a comprehensive candidate profile summary.
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
    
    if candidate.resume and candidate.resume.uploaded_doc_id:
        direct_doc = db.query(UploadedDocument).filter(UploadedDocument.id == candidate.resume.uploaded_doc_id).first()
        if direct_doc and direct_doc not in documents:
            documents.append(direct_doc)
            
    image_paths = []
    for doc in documents:
        if not doc.filepath or not os.path.exists(doc.filepath):
            continue
        file_ext = os.path.splitext(doc.filename)[1].lower()
        if file_ext in [".png", ".jpg", ".jpeg", ".heic", ".webp", ".bmp", ".tiff", ".tif"]:
            image_paths.append(doc.filepath)

    if not image_paths:
        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate.name,
            "summary": "No image-based documents found for this candidate to summarize.",
            "status": "no_images"
        }

    try:
        synthesis = VisionModel.summarize_documents(image_paths)
        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate.name,
            "document_count": len(image_paths),
            "summary": synthesis
        }
    except Exception as e:
        logger.error(f"Vision synthesis summary failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate synthesis summary: {str(e)}")
