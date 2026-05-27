import datetime
import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class AgentState(BaseModel):
    """Encapsulates the global state of the intake and screening workflow agent."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str = Field(description="Absolute path to the uploaded resume document")
    
    # Processing outputs
    ocr_raw_text: Optional[str] = None
    ocr_confidence: float = 0.0
    ocr_engine: Optional[str] = None
    
    parsed_profile: Optional[Dict[str, Any]] = None
    candidate_id: Optional[int] = None
    resume_id: Optional[int] = None
    
    # Node execution variables
    verification_results: Dict[str, Any] = Field(default_factory=dict)
    notifications_prepared: Dict[str, Any] = Field(default_factory=dict)
    
    # State tracking
    current_node: str = "init" # init -> intake -> parsing -> verification -> notification -> finish
    status: str = "running" # running, completed, failed
    errors: List[str] = Field(default_factory=list)
    agent_logs: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    def log_transition(self, agent_name: str, message: str):
        """Helper to append logs to the in-memory execution stack."""
        self.agent_logs.append({
            "agent": agent_name,
            "message": message,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
