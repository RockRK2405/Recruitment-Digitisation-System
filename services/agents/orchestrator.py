import json
from database.connection import SessionLocal
from database.models import AgentLog, AuditLog
from services.agents.state import AgentState
from services.agents.intake import IntakeAgent
from services.agents.screening import ScreeningAgent
from services.agents.verification import VerificationAgent
from services.agents.notification import NotificationAgent
from config.logging_config import logger

class AgentOrchestrator:
    """Orchestrates AI Agent sequence execution, managing state handoffs and committing transaction logs."""
    
    @classmethod
    def _persist_logs(cls, db_session, state: AgentState):
        """Helper to commit state log transitions and snapshots into relational database tables."""
        try:
            # 1. Commit all accumulated transition steps to agent_logs
            for log_entry in state.agent_logs:
                # To prevent duplicating logs, we can check if it's already there
                # For simplicity, we just insert all entries for this specific run
                agent_log = AgentLog(
                    run_id=state.run_id,
                    agent_name=log_entry["agent"],
                    message=log_entry["message"],
                    state_snapshot=json.dumps({
                        "node": state.current_node,
                        "status": state.status,
                        "candidate_id": state.candidate_id,
                        "verification": state.verification_results,
                        "errors": state.errors
                    })
                )
                db_session.add(agent_log)
                
            # Clear in-memory logs that are already committed to avoid double logging
            state.agent_logs = []
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.error(f"Failed to persist agent logs: {str(e)}")

    @classmethod
    def process_resume(cls, file_path: str) -> AgentState:
        """
        Runs the full recruitment ingestion workflow on an uploaded resume.
        Executes Intake -> Screening -> Verification -> Notification sequentially.
        """
        logger.info(f"--- Launching AI Recruiting Agent Team for file: {file_path} ---")
        
        # 1. Initialize State
        state = AgentState(file_path=file_path)
        state.log_transition("Orchestrator", f"Team assembled. Initiating run session: {state.run_id}")
        
        db = SessionLocal()
        
        # Log Audit event
        try:
            audit = AuditLog(
                action="agent_workflow_started",
                details=f"File: {file_path} | Run ID: {state.run_id}"
            )
            db.add(audit)
            db.commit()
        except Exception as e:
            logger.error(f"Audit log failed: {str(e)}")

        # 2. Sequential Node Handoff
        pipeline = [
            IntakeAgent,
            ScreeningAgent,
            VerificationAgent,
            NotificationAgent
        ]
        
        for agent_node in pipeline:
            if state.status == "failed":
                break
                
            # Execute node
            state = agent_node.execute(state)
            
            # Persist state transition history in database
            cls._persist_logs(db, state)

        # 3. Log Final Audit Results
        try:
            audit = AuditLog(
                action="agent_workflow_completed" if state.status == "completed" else "agent_workflow_failed",
                details=f"Run ID: {state.run_id} | Status: {state.status} | Candidate ID: {state.candidate_id}"
            )
            db.add(audit)
            db.commit()
        except Exception as e:
            logger.error(f"Final audit log failed: {str(e)}")
            
        db.close()
        logger.info(f"--- Workflow execution terminated with status: '{state.status}' ---")
        return state
