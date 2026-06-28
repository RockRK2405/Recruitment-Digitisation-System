-- WorkforceAI Recruitment Intelligence Platform
-- PostgreSQL Schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS vector;

-- Users & Authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'recruiter' CHECK (role IN ('admin', 'recruiter', 'viewer')),
    is_active BOOLEAN DEFAULT true,
    avatar_url TEXT,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Candidates
CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    location VARCHAR(200),
    address TEXT,
    status VARCHAR(30) DEFAULT 'new' CHECK (status IN ('new', 'screening', 'shortlisted', 'interviewed', 'offered', 'hired', 'rejected')),
    source VARCHAR(100),
    primary_domain VARCHAR(100),
    experience_years REAL DEFAULT 0,
    low_literacy_flag BOOLEAN DEFAULT false,
    profile_completeness INTEGER DEFAULT 0 CHECK (profile_completeness >= 0 AND profile_completeness <= 100),
    ai_summary TEXT,
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Uploaded Documents
CREATE TABLE uploaded_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE SET NULL,
    filename VARCHAR(500) NOT NULL,
    filepath TEXT NOT NULL,
    mime_type VARCHAR(100),
    ocr_text TEXT,
    ocr_confidence REAL DEFAULT 0,
    status VARCHAR(30) DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'ocr_completed', 'parsed', 'completed', 'failed')),
    doc_type VARCHAR(50) DEFAULT 'unknown' CHECK (doc_type IN ('resume', 'certificate', 'experience_letter', 'id_card', 'training_record', 'unknown', 'document')),
    doc_type_confidence REAL DEFAULT 0,
    ocr_engine_used VARCHAR(50),
    total_pages INTEGER DEFAULT 1,
    batch_id UUID,
    vision_analysis JSONB,
    bounding_boxes_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document Upload Batches
CREATE TABLE document_upload_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE SET NULL,
    total_documents INTEGER DEFAULT 0,
    status VARCHAR(30) DEFAULT 'uploaded',
    run_id VARCHAR(100),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Resumes (Parsed Data)
CREATE TABLE resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID UNIQUE REFERENCES candidates(id) ON DELETE CASCADE,
    uploaded_doc_id UUID REFERENCES uploaded_documents(id) ON DELETE SET NULL,
    raw_text TEXT,
    experience_years REAL,
    skills_list TEXT[] DEFAULT '{}',
    primary_domain VARCHAR(100),
    equipment_handled TEXT[] DEFAULT '{}',
    languages TEXT[] DEFAULT '{}',
    education TEXT,
    availability VARCHAR(100),
    notice_period VARCHAR(50),
    expected_salary VARCHAR(100),
    raw_parsed_json JSONB,
    industrial_details_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Certifications
CREATE TABLE certifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    name VARCHAR(300) NOT NULL,
    issuer VARCHAR(200),
    issue_date DATE,
    expiry_date DATE,
    registration_number VARCHAR(100),
    grade_or_class VARCHAR(50),
    safety_domain VARCHAR(100),
    is_safety_critical BOOLEAN DEFAULT false,
    verification_status VARCHAR(30) DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'failed')),
    verification_notes TEXT,
    source_document_id UUID REFERENCES uploaded_documents(id) ON DELETE SET NULL,
    confidence REAL DEFAULT 0,
    raw_parsed_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Job Descriptions
CREATE TABLE job_descriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(300) NOT NULL,
    description TEXT,
    required_skills TEXT[] DEFAULT '{}',
    required_certifications TEXT[] DEFAULT '{}',
    location VARCHAR(200),
    experience_years_required INTEGER,
    education_required VARCHAR(200),
    industry VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'closed', 'draft')),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Match Results
CREATE TABLE match_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    job_id UUID REFERENCES job_descriptions(id) ON DELETE CASCADE,
    vector_score REAL DEFAULT 0,
    skill_score REAL DEFAULT 0,
    agent_score REAL DEFAULT 0,
    overall_score REAL DEFAULT 0,
    match_explanation TEXT,
    agent_comments TEXT,
    missing_skills TEXT[] DEFAULT '{}',
    matched_skills TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(candidate_id, job_id)
);

-- Recruiter Decisions
CREATE TABLE recruiter_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    job_id UUID REFERENCES job_descriptions(id) ON DELETE CASCADE,
    decision VARCHAR(30) NOT NULL CHECK (decision IN ('accepted', 'rejected', 'hold', 'shortlisted')),
    recruiter_username VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Recruiter Feedback
CREATE TABLE recruiter_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    job_id UUID REFERENCES job_descriptions(id) ON DELETE CASCADE,
    match_quality_rating INTEGER CHECK (match_quality_rating >= 1 AND match_quality_rating <= 5),
    comment TEXT,
    original_score REAL,
    recruiter_username VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Candidate Tags
CREATE TABLE candidate_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    tag VARCHAR(100) NOT NULL,
    tagged_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent Logs
CREATE TABLE agent_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(100),
    agent_name VARCHAR(100),
    state_snapshot JSONB,
    message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action VARCHAR(200) NOT NULL,
    details JSONB,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Extraction Confidences
CREATE TABLE extraction_confidences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    document_id UUID REFERENCES uploaded_documents(id) ON DELETE CASCADE,
    field_name VARCHAR(100),
    field_value TEXT,
    confidence_score REAL DEFAULT 0,
    source_page INTEGER,
    bounding_box_json JSONB,
    extraction_method VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector Embeddings Cache
CREATE TABLE embeddings_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    content_type VARCHAR(50),
    embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_candidates_name ON candidates USING gin (name gin_trgm_ops);
CREATE INDEX idx_candidates_email ON candidates(email);
CREATE INDEX idx_candidates_status ON candidates(status);
CREATE INDEX idx_candidates_domain ON candidates(primary_domain);
CREATE INDEX idx_candidates_created ON candidates(created_at DESC);

CREATE INDEX idx_resumes_candidate ON resumes(candidate_id);
CREATE INDEX idx_resumes_skills ON resumes USING gin (skills_list);
CREATE INDEX idx_resumes_domain ON resumes(primary_domain);

CREATE INDEX idx_certifications_candidate ON certifications(candidate_id);
CREATE INDEX idx_certifications_name ON certifications(name);
CREATE INDEX idx_certifications_verification ON certifications(verification_status);

CREATE INDEX idx_jobs_status ON job_descriptions(status);
CREATE INDEX idx_jobs_title ON job_descriptions USING gin (title gin_trgm_ops);
CREATE INDEX idx_jobs_created ON job_descriptions(created_at DESC);

CREATE INDEX idx_match_results_score ON match_results(overall_score DESC);
CREATE INDEX idx_match_results_candidate ON match_results(candidate_id);
CREATE INDEX idx_match_results_job ON match_results(job_id);

CREATE INDEX idx_uploaded_documents_status ON uploaded_documents(status);
CREATE INDEX idx_uploaded_documents_candidate ON uploaded_documents(candidate_id);

CREATE INDEX idx_agent_logs_run ON agent_logs(run_id);
CREATE INDEX idx_agent_logs_timestamp ON agent_logs(timestamp DESC);

CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);

-- Trigger functions
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_candidates_updated_at BEFORE UPDATE ON candidates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON job_descriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_resumes_updated_at BEFORE UPDATE ON resumes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Seed default users (password for all: password123)
-- Default password for all users: admin123
INSERT INTO users (username, password_hash, display_name, email, role) VALUES
    ('admin', '$2b$10$.ElQf3B8tAwFfZkbM2bV1uRf1Q/v5fMhsmYX9uEMarCdq75On/hm6', 'Admin User', 'admin@workforce.ai', 'admin'),
    ('recruiter', '$2b$10$.ElQf3B8tAwFfZkbM2bV1uRf1Q/v5fMhsmYX9uEMarCdq75On/hm6', 'Recruiter User', 'recruiter@workforce.ai', 'recruiter'),
    ('viewer', '$2b$10$.ElQf3B8tAwFfZkbM2bV1uRf1Q/v5fMhsmYX9uEMarCdq75On/hm6', 'Viewer User', 'viewer@workforce.ai', 'viewer')
ON CONFLICT (username) DO NOTHING;

-- Additional performance indexes (added Phase 3)
CREATE INDEX IF NOT EXISTS idx_match_results_job_score ON match_results(job_id, overall_score DESC);
CREATE INDEX IF NOT EXISTS idx_resumes_raw_text_gin ON resumes USING gin (to_tsvector('english', COALESCE(raw_text, '')));
CREATE INDEX IF NOT EXISTS idx_candidates_status_created ON candidates(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_uploaded_documents_candidate_status ON uploaded_documents(candidate_id, status);
