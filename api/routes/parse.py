"""
Stateless resume parsing endpoint.

Purpose: Run OCR + LLM-assisted parsing on an uploaded file and return
structured JSON. Does NOT touch the database — the caller (api-gateway)
is responsible for persistence using its own raw pg queries.

This sidesteps the broken SQLAlchemy ORM layer (model/schema drift)
and keeps the Python service focused on what it does well: OCR + LLM.
"""

import os
import shutil
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from config.logging_config import logger
from services.ocr.engine import OCREngine
from services.ocr.clean import DocumentCleaner
from services.resume_parser.parser import ResumeParser

router = APIRouter()


@router.post("/parse", summary="OCR + parse a resume file, return structured JSON (no DB writes)")
async def parse_resume(file: UploadFile = File(...)):
    """
    Stateless pipeline:
      1. Save uploaded file to a temp path.
      2. Run OCR engine (PaddleOCR → EasyOCR → Tesseract cascade).
      3. Run resume parser (LLM with regex heuristic fallback).
      4. Return parsed profile + raw text + OCR confidence.
    """
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".heic", ".tiff", ".tif", ".bmp", ".webp", ".doc", ".docx"}
    if file_ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{file_ext}'.")

    tmp_dir = tempfile.mkdtemp(prefix="parse_")
    tmp_path = os.path.join(tmp_dir, file.filename or f"upload{file_ext}")

    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        logger.info(f"[parse] file saved → {tmp_path}")

        # 1. OCR
        try:
            ocr_result = OCREngine.extract_text(tmp_path)
        except Exception as e:
            logger.warning(f"[parse] OCR engine raised: {e}")
            ocr_result = {"text": "", "confidence": 0.0, "engine_used": "error", "total_pages": 1}

        raw_text = ocr_result.get("text", "") or ""
        cleaned_text = DocumentCleaner.clean(raw_text) if raw_text else ""
        ocr_confidence = float(ocr_result.get("confidence", 0.0) or 0.0)
        ocr_engine = ocr_result.get("engine_used", "")

        if not cleaned_text.strip():
            logger.warning(f"[parse] OCR returned no text for {file.filename}")
            return {
                "ok": False,
                "reason": "ocr_empty",
                "ocr_confidence": 0.0,
                "ocr_engine_used": ocr_engine,
                "raw_text": "",
                "parsed": _empty_profile(),
            }

        # 2. Parse (LLM with heuristic fallback inside parser)
        try:
            parsed = ResumeParser.parse_resume(cleaned_text)
        except Exception as e:
            logger.error(f"[parse] resume parser exception: {e}")
            return {
                "ok": False,
                "reason": f"parser_error: {e}",
                "ocr_confidence": ocr_confidence,
                "ocr_engine_used": ocr_engine,
                "raw_text": cleaned_text,
                "parsed": _empty_profile(),
            }

        # 3. Build a stable JSON payload for the gateway
        return {
            "ok": True,
            "ocr_confidence": ocr_confidence,
            "ocr_engine_used": ocr_engine,
            "total_pages": int(ocr_result.get("total_pages", 1) or 1),
            "raw_text": cleaned_text,
            "parsed": {
                "name": parsed.name or "",
                "email": (parsed.email or "").strip() or None,
                "phone": parsed.phone or "",
                "location": parsed.location or "",
                "address": parsed.address or "",
                "experience_years": float(parsed.experience_years or 0),
                "primary_domain": parsed.industry_domain or "",
                "skills": list(parsed.skills or []),
                "equipment_handled": list(parsed.equipment_handled or []),
                "languages": list(parsed.languages or []),
                "education": parsed.education or "",
                "availability": parsed.availability or "",
                "certifications": [
                    {
                        "name": c.name,
                        "issuer": c.issuer or "",
                        "issue_date": str(c.issue_date) if c.issue_date else None,
                        "expiry_date": str(c.expiry_date) if c.expiry_date else None,
                        "registration_number": c.registration_number or "",
                        "is_safety_critical": bool(c.is_safety_critical),
                        "confidence": float(c.confidence or 0),
                    }
                    for c in (parsed.certifications or [])
                ],
            },
        }
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def _empty_profile() -> dict:
    return {
        "name": "", "email": None, "phone": "", "location": "", "address": "",
        "experience_years": 0.0, "primary_domain": "", "skills": [],
        "equipment_handled": [], "languages": [], "education": "",
        "availability": "", "certifications": [],
    }
