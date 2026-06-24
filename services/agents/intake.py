"""
Enhanced Intake Agent for Multi-Modal Document Intelligence.

Handles multi-file OCR processing, embedded image extraction from PDFs,
and per-file result tracking.
"""

import os
import json
from database.connection import SessionLocal
from database.models import AgentLog, UploadedDocument
from services.ocr.engine import OCREngine
from services.ocr.clean import DocumentCleaner
from services.agents.state import AgentState
from config.logging_config import logger


class IntakeAgent:
    """Intake Agent Node: Handles file verification, triggers OCR pipelines, and normalizes output."""
    
    @staticmethod
    def execute(state: AgentState) -> AgentState:
        state.current_node = "intake"
        
        # Determine all files to process
        all_files = state.file_paths if state.file_paths else ([state.file_path] if state.file_path else [])
        
        state.log_transition(
            "Intake Agent",
            f"Initializing document digitization for {len(all_files)} file(s)."
        )
        
        if not all_files:
            state.status = "failed"
            state.errors.append("No files provided for processing.")
            state.log_transition("Intake Agent", "CRITICAL: No files to process.")
            return state

        # Validate all files exist
        valid_files = []
        for fp in all_files:
            if os.path.exists(fp):
                valid_files.append(fp)
            else:
                state.log_transition("Intake Agent", f"WARNING: File not found: {fp}")
        
        if not valid_files:
            state.status = "failed"
            state.errors.append("No valid files found on disk.")
            state.log_transition("Intake Agent", "CRITICAL: All file paths are invalid.")
            return state

        # Process each file
        per_file_results = {}
        primary_text = ""
        primary_confidence = 0.0
        primary_engine = ""
        doc_ids = []
        
        for file_path in valid_files:
            filename = os.path.basename(file_path)
            state.log_transition("Intake Agent", f"Processing file: {filename}")
            
            try:
                # Run OCR engine
                ocr_result = OCREngine.extract_text(file_path)
                
                # Clean text
                raw_text = ocr_result.get("text", "")
                cleaned_text = DocumentCleaner.clean(raw_text)
                
                # Store per-file result
                per_file_results[file_path] = {
                    "text": cleaned_text,
                    "confidence": ocr_result.get("confidence", 0.0),
                    "engine": ocr_result.get("engine_used", ""),
                    "is_digital": ocr_result.get("is_digital", False),
                    "total_pages": ocr_result.get("total_pages", 1),
                    "bounding_boxes": ocr_result.get("bounding_boxes", []),
                    "page_results": ocr_result.get("page_results", []),
                }
                
                # Use first file as primary (backward compatibility)
                if not primary_text:
                    primary_text = cleaned_text
                    primary_confidence = ocr_result.get("confidence", 0.0)
                    primary_engine = ocr_result.get("engine_used", "")
                
                state.log_transition(
                    "Intake Agent",
                    f"OCR complete for '{filename}': engine='{ocr_result.get('engine_used')}', "
                    f"confidence={ocr_result.get('confidence', 0)*100:.1f}%, "
                    f"pages={ocr_result.get('total_pages', 1)}, "
                    f"chars={len(cleaned_text)}"
                )
                
                # Save document record to DB
                db = SessionLocal()
                try:
                    # Determine MIME type
                    ext = os.path.splitext(file_path)[1].lower()
                    mime_map = {
                        '.pdf': 'application/pdf', '.png': 'image/png',
                        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                        '.tiff': 'image/tiff', '.tif': 'image/tiff',
                        '.bmp': 'image/bmp', '.heic': 'image/heic',
                    }
                    
                    doc = UploadedDocument(
                        filename=filename,
                        filepath=file_path,
                        mime_type=mime_map.get(ext, 'application/octet-stream'),
                        ocr_text=cleaned_text,
                        ocr_confidence=ocr_result.get("confidence", 0.0),
                        ocr_engine_used=ocr_result.get("engine_used", ""),
                        total_pages=ocr_result.get("total_pages", 1),
                        bounding_boxes_json=json.dumps(ocr_result.get("bounding_boxes", [])),
                        batch_id=state.batch_id,
                        status="completed"
                    )
                    db.add(doc)
                    db.commit()
                    db.refresh(doc)
                    doc_ids.append(doc.id)
                    
                    # Store first doc ID for backward compatibility
                    if len(doc_ids) == 1:
                        state.verification_results["uploaded_doc_id"] = doc.id
                    
                    state.log_transition(
                        "Intake Agent",
                        f"Document '{filename}' saved to database (Doc ID: {doc.id})"
                    )
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to save document record for {filename}: {str(e)}")
                finally:
                    db.close()
                    
            except Exception as e:
                state.log_transition(
                    "Intake Agent",
                    f"WARNING: OCR failed for '{filename}': {str(e)}"
                )
                per_file_results[file_path] = {
                    "text": "",
                    "confidence": 0.0,
                    "engine": "error",
                    "error": str(e)
                }
        
        # Update state
        state.per_file_ocr_results = per_file_results
        state.ocr_raw_text = primary_text
        state.ocr_confidence = primary_confidence
        state.ocr_engine = primary_engine
        state.verification_results["doc_ids"] = doc_ids
        
        # Combine all texts for downstream processing
        all_texts = [r["text"] for r in per_file_results.values() if r.get("text")]
        if len(all_texts) > 1:
            state.ocr_raw_text = "\n\n---\n\n".join(all_texts)
        
        state.log_transition(
            "Intake Agent",
            f"Intake complete. {len(per_file_results)} files processed, "
            f"{len(doc_ids)} document records created."
        )
        
        return state
