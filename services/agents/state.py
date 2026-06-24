"""
Extended Agent State for Multi-Modal Document Intelligence Pipeline.

Supports multiple file uploads, document classifications, vision analysis,
per-document extraction results, and knowledge graph tracking.
"""

import datetime
import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """Encapsulates the global state of the multi-modal document processing workflow."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # File inputs (supports single or multi-document)
    file_path: str = Field(default="", description="Primary file path (backward compatibility)")
    file_paths: List[str] = Field(default_factory=list, description="All file paths in batch")
    
    # OCR outputs (per primary file, backward compatible)
    ocr_raw_text: Optional[str] = None
    ocr_confidence: float = 0.0
    ocr_engine: Optional[str] = None
    
    # Per-file OCR results (multi-document)
    per_file_ocr_results: Dict[str, dict] = Field(default_factory=dict)
    
    # Document classification results
    document_classifications: Dict[str, dict] = Field(default_factory=dict)
    
    # Vision-Language Model analysis results
    vision_analysis_results: Dict[str, Any] = Field(default_factory=dict)
    
    # Extraction results per document
    extraction_results: List[dict] = Field(default_factory=list)
    
    # Parsed profile (merged from all documents)
    parsed_profile: Optional[Dict[str, Any]] = None
    candidate_id: Optional[int] = None
    resume_id: Optional[int] = None
    batch_id: Optional[int] = None
    
    # Node execution variables
    verification_results: Dict[str, Any] = Field(default_factory=dict)
    
    # Confidence tracking
    confidence_report: Dict[str, Any] = Field(default_factory=dict)
    
    # State tracking
    current_node: str = "init"  # init -> intake -> classification -> vision -> parsing -> verification -> finish
    status: str = "running"  # running, completed, failed
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
