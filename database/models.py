import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from database.connection import Base

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
    
    # Relationships
    resumes = relationship("Resume", back_populates="document", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=True)
    email = Column(String(150), nullable=True, unique=True)
    phone = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)
    status = Column(String(50), default="onboarded")  # onboarded, screening, active, inactive
    low_literacy_flag = Column(Boolean, default=False)
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
    raw_parsed_json = Column(Text, nullable=True)  # Raw JSON output from Gemini model
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="resume")
    document = relationship("UploadedDocument", back_populates="resumes")


class Certification(Base):
    __tablename__ = "certifications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    name = Column(String(255), nullable=False)  # e.g., DGMS mining gas certification
    issuer = Column(String(255), nullable=True)
    issue_date = Column(String(100), nullable=True)
    expiry_date = Column(String(100), nullable=True)
    verification_status = Column(String(50), default="pending")  # pending, verified, rejected
    raw_parsed_data = Column(Text, nullable=True)  # Extra JSON variables
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
