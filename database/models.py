"""
Extended Database Models for Multi-Modal Document Intelligence System.

Adds models for:
- Document upload batches (multi-file sessions)
- Per-document classification and extraction tracking
- Candidate skills, experience, education (knowledge graph nodes)
- Knowledge graph edges (typed relationships)
- Field-level extraction confidence tracking
"""

import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from database.connection import Base


# ─────────────────────────────────────────────
# EXISTING MODELS (preserved)
# ─────────────────────────────────────────────

class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(512), nullable=False)
    mime_type = Column(String(100), nullable=True)
    ocr_text = Column(Text, nullable=True)
    ocr_confidence = Column(Float, default=0.0)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Multi-modal extensions
    doc_type = Column(String(50), nullable=True)  # resume, certificate, experience_letter, id_card, training_record
    doc_type_confidence = Column(Float, default=0.0)
    ocr_engine_used = Column(String(50), nullable=True)
    total_pages = Column(Integer, default=1)
    batch_id = Column(Integer, ForeignKey("document_upload_batches.id"), nullable=True)
    vision_analysis = Column(Text, nullable=True)  # JSON from VLM analysis
    bounding_boxes_json = Column(Text, nullable=True)  # JSON array of bounding boxes
    
    # Relationships
    resumes = relationship("Resume", back_populates="document", cascade="all, delete-orphan")
    batch = relationship("DocumentUploadBatch", back_populates="documents")
    extraction_confidences = relationship("ExtractionConfidence", back_populates="document", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=True)
    email = Column(String(150), nullable=True, unique=True)
    phone = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    status = Column(String(50), default="onboarded")  # onboarded, screening, active, inactive
    low_literacy_flag = Column(Boolean, default=False)
    profile_completeness = Column(Float, default=0.0)  # 0.0 to 1.0
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    resume = relationship("Resume", uselist=False, back_populates="candidate", cascade="all, delete-orphan")
    certifications = relationship("Certification", back_populates="candidate", cascade="all, delete-orphan")
    matches = relationship("MatchResult", back_populates="candidate", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    uploaded_doc_id = Column(Integer, ForeignKey("uploaded_documents.id"), nullable=True)
    raw_text = Column(Text, nullable=True)
    experience_years = Column(Float, default=0.0)
    skills_list = Column(Text, nullable=True)  # Comma-separated or clean list text
    primary_domain = Column(String(100), nullable=True)  # Mining, Steel Plant, etc.
    equipment_handled = Column(Text, nullable=True)  # Comma-separated list of machines
    languages = Column(String(255), nullable=True)  # Comma-separated languages
    education = Column(Text, nullable=True)
    availability = Column(String(100), nullable=True)
    notice_period = Column(String(100), nullable=True)  # e.g. "Immediate", "15 days", "1 month"
    expected_salary = Column(String(100), nullable=True)  # e.g. "25000", "30000-40000"
    raw_parsed_json = Column(Text, nullable=True)  # Raw JSON output from LLM
    industrial_details_json = Column(Text, nullable=True)  # JSON of IndustrialDetails
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="resume")
    document = relationship("UploadedDocument", back_populates="resumes")


class Certification(Base):
    __tablename__ = "certifications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    name = Column(String(255), nullable=False)
    issuer = Column(String(255), nullable=True)
    issue_date = Column(String(100), nullable=True)
    expiry_date = Column(String(100), nullable=True)
    registration_number = Column(String(100), nullable=True)
    grade_or_class = Column(String(50), nullable=True)
    safety_domain = Column(String(50), nullable=True)  # mining/electrical/welding/crane/boiler/fire/general
    is_safety_critical = Column(Boolean, default=False)
    verification_status = Column(String(50), default="pending")  # pending, verified, rejected, flagged
    verification_notes = Column(Text, nullable=True)
    source_document_id = Column(Integer, ForeignKey("uploaded_documents.id"), nullable=True)
    confidence = Column(Float, default=0.0)
    raw_parsed_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="certifications")


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    required_skills = Column(Text, nullable=True)  # Comma-separated
    required_certifications = Column(Text, nullable=True)  # Comma-separated
    location = Column(String(255), nullable=True)
    experience_years_required = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    matches = relationship("MatchResult", back_populates="job_description", cascade="all, delete-orphan")


class MatchResult(Base):
    __tablename__ = "match_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=False)
    vector_score = Column(Float, default=0.0)
    skill_score = Column(Float, default=0.0)
    agent_score = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)
    match_explanation = Column(Text, nullable=True)
    agent_comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="matches")
    job_description = relationship("JobDescription", back_populates="matches")


class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(100), nullable=False)
    agent_name = Column(String(100), nullable=False)
    state_snapshot = Column(Text, nullable=True)  # JSON snap
    message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


# ─────────────────────────────────────────────
# NEW MODELS: Multi-Modal Document Intelligence
# ─────────────────────────────────────────────

class DocumentUploadBatch(Base):
    """Groups multiple document uploads belonging to a single candidate session."""
    __tablename__ = "document_upload_batches"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=True)
    total_documents = Column(Integer, default=0)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    run_id = Column(String(100), nullable=True)  # Agent run session ID
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    documents = relationship("UploadedDocument", back_populates="batch")




class ExtractionConfidence(Base):
    """Per-field extraction confidence with source provenance."""
    __tablename__ = "extraction_confidences"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=True)
    document_id = Column(Integer, ForeignKey("uploaded_documents.id"), nullable=True)
    field_name = Column(String(100), nullable=False)
    field_value = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.0)
    source_page = Column(Integer, nullable=True)
    bounding_box_json = Column(Text, nullable=True)  # JSON [[x1,y1],[x2,y2],...]
    extraction_method = Column(String(50), nullable=True)  # ocr, vision, llm, heuristic
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    document = relationship("UploadedDocument", back_populates="extraction_confidences")


# ─────────────────────────────────────────────
# RBAC & RECRUITER REVIEW MODELS
# ─────────────────────────────────────────────

class User(Base):
    """User accounts with role-based access control."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(150), nullable=True)
    role = Column(String(50), nullable=False, default="viewer")  # admin, recruiter, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class RecruiterDecision(Base):
    """Stores recruiter accept/reject/hold decisions on candidate-job matches."""
    __tablename__ = "recruiter_decisions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=False)
    decision = Column(String(50), nullable=False)  # accepted, rejected, hold, shortlisted
    recruiter_username = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate")
    job_description = relationship("JobDescription")


class RecruiterFeedback(Base):
    """Stores match quality feedback for scoring weight adjustment."""
    __tablename__ = "recruiter_feedback"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=False)
    match_quality_rating = Column(Integer, nullable=False)  # 1-5 stars
    comment = Column(Text, nullable=True)
    original_score = Column(Float, nullable=True)  # The score the system gave
    recruiter_username = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate")
    job_description = relationship("JobDescription")


class CandidateTag(Base):
    """Free-form tags assigned by recruiters to candidates."""
    __tablename__ = "candidate_tags"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    tag = Column(String(100), nullable=False)  # e.g. "interview scheduled", "reference check"
    tagged_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate")
