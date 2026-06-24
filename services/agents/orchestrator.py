"""
Enhanced Agent Orchestrator for Multi-Modal Document Intelligence.

Extended pipeline: Intake → Classification → Vision Analysis → 
Screening → Verification → KG Build → Notification

Supports both single-file (backward compatible) and multi-file batch processing.
"""

import json
from database.connection import SessionLocal
from database.models import AgentLog, AuditLog, DocumentUploadBatch
from services.agents.state import AgentState
from services.agents.intake import IntakeAgent
from services.agents.classification_agent import ClassificationAgent
from services.agents.vision_agent import VisionAnalysisAgent
from services.agents.screening import ScreeningAgent
from services.agents.verification import VerificationAgent
from config.logging_config import logger


class AgentOrchestrator:
    """Orchestrates AI Agent sequence execution, managing state handoffs and transaction logs."""
    
    @classmethod
    def _persist_logs(cls, db_session, state: AgentState):
        """Helper to commit state log transitions and snapshots into database tables."""
        try:
            for log_entry in state.agent_logs:
                agent_log = AgentLog(
                    run_id=state.run_id,
                    agent_name=log_entry["agent"],
                    message=log_entry["message"],
                    state_snapshot=json.dumps({
                        "node": state.current_node,
                        "status": state.status,
                        "candidate_id": state.candidate_id,
                        "verification": state.verification_results,
                        "errors": state.errors,
                        "classifications_count": len(state.document_classifications),
                        "vision_results_count": len(state.vision_analysis_results),
                    })
                )
                db_session.add(agent_log)
            
            state.agent_logs = []
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.error(f"Failed to persist agent logs: {str(e)}")

    @classmethod
    def process_resume(cls, file_path: str) -> AgentState:
        """
        Backward-compatible single-file processing.
        Runs the full multi-modal pipeline on a single document.
        """
        return cls.process_documents([file_path])

    @classmethod
    def process_documents(cls, file_paths: list) -> AgentState:
        """
        Runs the full multi-modal document intelligence pipeline on one or more files.
        
        Extended Pipeline:
        1. Intake Agent: OCR extraction for all files
        2. Classification Agent: Document type identification
        3. Vision Analysis Agent: VLM-powered image understanding
        4. Screening Agent: LLM entity extraction + database storage
        5. Verification Agent: Certification and credential auditing
        6. KG Builder Agent: Knowledge graph construction
        7. Notification Agent: Localized onboarding notifications
        """
        logger.info(f"--- Launching AI Document Intelligence Team for {len(file_paths)} file(s) ---")
        
        # 1. Initialize State
        state = AgentState(
            file_path=file_paths[0] if file_paths else "",
            file_paths=file_paths
        )
        state.log_transition("Orchestrator", f"Team assembled. Run session: {state.run_id} | Files: {len(file_paths)}")
        
        db = SessionLocal()
        
        # Create batch record
        try:
            batch = DocumentUploadBatch(
                total_documents=len(file_paths),
                status="processing",
                run_id=state.run_id
            )
            db.add(batch)
            db.commit()
            db.refresh(batch)
            state.batch_id = batch.id
            
            audit = AuditLog(
                action="agent_workflow_started",
                details=f"Batch ID: {batch.id} | Files: {len(file_paths)} | Run ID: {state.run_id}"
            )
            db.add(audit)
            db.commit()
        except Exception as e:
            logger.error(f"Batch/audit log failed: {str(e)}")

        # 2. Extended Pipeline Execution
        pipeline = [
            IntakeAgent,            # OCR extraction
            ClassificationAgent,    # Document type identification
            VisionAnalysisAgent,    # VLM image analysis
            ScreeningAgent,         # LLM extraction + DB storage
            VerificationAgent,      # Credential auditing
        ]
        
        for agent_node in pipeline:
            if state.status == "failed":
                break
                
            # Execute node
            state = agent_node.execute(state)
            
            # Persist state transition history
            cls._persist_logs(db, state)

        # 3. Update batch status
        try:
            batch = db.query(DocumentUploadBatch).filter(
                DocumentUploadBatch.id == state.batch_id
            ).first()
            if batch:
                batch.status = "completed" if state.status == "completed" else "failed"
                batch.candidate_id = state.candidate_id
                import datetime
                batch.completed_at = datetime.datetime.utcnow()
            
            audit = AuditLog(
                action="agent_workflow_completed" if state.status == "completed" else "agent_workflow_failed",
                details=(
                    f"Run ID: {state.run_id} | Status: {state.status} | "
                    f"Candidate ID: {state.candidate_id} | "
                    f"Documents: {len(file_paths)}"
                )
            )
            db.add(audit)
            db.commit()
        except Exception as e:
            logger.error(f"Final audit log failed: {str(e)}")
            
        db.close()
        logger.info(f"--- Workflow terminated: '{state.status}' ---")
        return state
