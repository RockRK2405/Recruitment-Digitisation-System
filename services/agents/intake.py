import os
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
        state.log_transition("Intake Agent", f"Initializing document digitization for file: {os.path.basename(state.file_path)}")
        
        if not os.path.exists(state.file_path):
            state.status = "failed"
            err = f"Target document not found at path: {state.file_path}"
            state.errors.append(err)
            state.log_transition("Intake Agent", f"CRITICAL: {err}")
            return state

        try:
            # 1. Trigger dual-OCR parsing engine
            state.log_transition("Intake Agent", "Executing OCR and text stream extraction...")
            ocr_result = OCREngine.extract_text(state.file_path)
            
            # 2. Extract and clean text
            raw_text = ocr_result["text"]
            cleaned_text = DocumentCleaner.clean(raw_text)
            
            # 3. Store result in state
            state.ocr_raw_text = cleaned_text
            state.ocr_confidence = ocr_result["confidence"]
            state.ocr_engine = ocr_result["engine_used"]
            
            state.log_transition(
                "Intake Agent", 
                f"OCR execution completed using engine '{state.ocr_engine}' with {state.ocr_confidence*100:.1f}% confidence."
            )
            
            # 4. Save uploaded document record to Database
            db = SessionLocal()
            try:
                doc = UploadedDocument(
                    filename=os.path.basename(state.file_path),
                    filepath=state.file_path,
                    mime_type="application/pdf" if state.file_path.endswith(".pdf") else "image/png",
                    ocr_text=cleaned_text,
                    ocr_confidence=state.ocr_confidence,
                    status="completed"
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                
                # Keep tracked document reference in state
                state.verification_results["uploaded_doc_id"] = doc.id
                state.log_transition("Intake Agent", f"Digitized document reference logged in SQL database (Doc ID: {doc.id})")
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to save document record: {str(e)}")
                state.log_transition("Intake Agent", f"Warning: Failed to save document database record: {str(e)}")
            finally:
                db.close()
                
        except Exception as e:
            state.status = "failed"
            state.errors.append(str(e))
            state.log_transition("Intake Agent", f"CRITICAL failure during intake node: {str(e)}")
            
        return state
