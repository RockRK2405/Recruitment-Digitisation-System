import streamlit as st
import requests
import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ui.components.styling import inject_premium_styles
from database.connection import SessionLocal, is_sqlite_fallback
from database.models import Candidate, UploadedDocument, JobDescription, Certification
from config.logging_config import logger

# Set premium Streamlit page configurations
st.set_page_config(
    page_title="Recruitment Digitisation System",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject CSS styling overrides
inject_premium_styles()

def fetch_summary_data() -> dict:
    """Fetches summary metrics from FastAPI API with dynamic direct DB fallback."""
    # Method A: Try REST API
    try:
        res = requests.get("http://localhost:8000/api/analytics/summary", timeout=1.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        # Fallback to Method B: Direct Database Lookup (Ensures UI works offline/standalone!)
        pass
        
    # Database Direct fallback
    db = SessionLocal()
    try:
        candidates_count = db.query(Candidate).count()
        docs_count = db.query(UploadedDocument).count()
        jobs_count = db.query(JobDescription).count()
        
        low_lit = db.query(Candidate).filter(Candidate.low_literacy_flag == True).count()
        low_lit_pct = round((low_lit / candidates_count * 100), 1) if candidates_count > 0 else 0.0
        
        total_certs = db.query(Certification).count()
        verified_certs = db.query(Certification).filter(Certification.verification_status == "verified").count()
        cert_rate = round((verified_certs / total_certs * 100), 1) if total_certs > 0 else 0.0
        
        return {
            "total_candidates": candidates_count,
            "total_documents": docs_count,
            "total_job_descriptions": jobs_count,
            "low_literacy_applicants": low_lit,
            "low_literacy_percentage": low_lit_pct,
            "total_certifications_audited": total_certs,
            "verified_certifications": verified_certs,
            "certification_verification_rate": cert_rate,
            "ocr_engine_distribution": {"Tesseract": docs_count}
        }
    except Exception as e:
        logger.error(f"UI summary fallback query failed: {str(e)}")
        return {
            "total_candidates": 0, "total_documents": 0, "total_job_descriptions": 0,
            "low_literacy_applicants": 0, "low_literacy_percentage": 0.0,
            "total_certifications_audited": 0, "verified_certifications": 0,
            "certification_verification_rate": 0.0, "ocr_engine_distribution": {}
        }
    finally:
        db.close()

# Page Header
st.markdown('<div class="gradient-title">Recruitment Digitisation System</div>', unsafe_allow_html=True)
st.markdown('<div class="gradient-subtitle">AI-Powered Industrial Workforce Recruitment & Resume Intelligence Platform</div>', unsafe_allow_html=True)

# Fetch stats
stats = fetch_summary_data()

# KPI Metric Cards Grid
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(
        f"""
        <div class="glass-card">
            <div style="font-size: 0.9rem; color: #8f9bb3; font-weight: 500;">DIGITIZED CANDIDATES</div>
            <div class="metric-val">{stats["total_candidates"]} Workers</div>
            <div style="font-size: 0.8rem; color: #00e676; margin-top: 0.5rem;">⚡ Profiles Active</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        f"""
        <div class="glass-card">
            <div style="font-size: 0.9rem; color: #8f9bb3; font-weight: 500;">PHYSICAL UPLOADS</div>
            <div class="metric-val">{stats["total_documents"]} Files</div>
            <div style="font-size: 0.8rem; color: #ffd700; margin-top: 0.5rem;"> Mobile Photo OCR</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"""
        <div class="glass-card">
            <div style="font-size: 0.9rem; color: #8f9bb3; font-weight: 500;">LOW-LITERACY HELP</div>
            <div class="metric-val">{stats["low_literacy_percentage"]}%</div>
            <div style="font-size: 0.8rem; color: #00b0ff; margin-top: 0.5rem;"> Assistance Flagged ({stats["low_literacy_applicants"]})</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col4:
    st.markdown(
        f"""
        <div class="glass-card">
            <div style="font-size: 0.9rem; color: #8f9bb3; font-weight: 500;">LICENSE COMPLIANCE</div>
            <div class="metric-val">{stats["certification_verification_rate"]}%</div>
            <div style="font-size: 0.8rem; color: #00e676; margin-top: 0.5rem;"> DGMS/OSHA Audited</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Core Platform Showcase
st.markdown("###  Platform Architecture & Capabilities")

col_left, col_right = st.columns([3, 2])

with col_left:
    st.markdown(
        """
        <div class="glass-card" style="min-height: 380px;">
            <h4 style="color: #ffd700; margin-top:0;"> Platform Workflow Overview</h4>
            <p style="color: #cbd5e1; line-height:1.6;">
                Most industrial workers operating heavy mining shovels, steam boilers, or fabrication furnaces submit only 
                <b>crumpled physical paper resumes</b> and are not digitally literate. <b></b> digitizes, 
                interprets, and audits safety licenses for blue-collar placements:
            </p>
            <ul style="color: #cbd5e1; line-height: 1.8; padding-left: 1.2rem;">
                <li><b>Noisy Document Preprocessing:</b> OpenCV filters out grease stains, de-skews angled mobile photos, and adaptive-thresholds handwritten/printed paper layers.</li>
                <li><b>Dual OCR Core:</b> Primary PaddleOCR processes complex multilingual tables and fallback Tesseract scans text in Hindi/English characters.</li>
                <li><b>Pydantic LLM Extraction:</b> Resolves messy transcripts into strict JSON objects containing heavy machinery items, locations, and spoken languages.</li>
                <li><b>State-Machine AI Agent Crew:</b> Ingests documents, parses entities, validates certification authenticities, and generates localized WhatsApp SMS.</li>
                <li><b>Compliance-Aware Matching:</b> A hybrid SQL-vector scoring matrix weights candidate profiles against Job Descriptions, penalizing profiles that lack mandatory regulatory licenses.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )

with col_right:
    st.markdown(
        """
        <div class="glass-card" style="min-height: 380px;">
            <h4 style="color: #ffd700; margin-top:0;"> Active Environment Stats</h4>
            <table style="width: 100%; border-collapse: collapse; color: #cbd5e1; line-height:2.2;">
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td><b>Vector Index:</b></td>
                    <td style="color: #ffd700;">ChromaDB Persistent (Cosine)</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td><b>Embedding Model:</b></td>
                    <td style="color: #00b0ff;">intfloat/multilingual-e5-base</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td><b>LLM Engine:</b></td>
                    <td style="color: #00e676;">Gemini 2.5 Flash</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td><b>Database Mode:</b></td>
                    <td>{}</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td><b>Multilingual Support:</b></td>
                    <td>English, Hindi (हिन्दी), Spanish (Español)</td>
                </tr>
                <tr>
                    <td><b>Safety Guidelines:</b></td>
                    <td style="color: #00e676;">DGMS & OSHA Compliance Audited</td>
                </tr>
            </table>
        </div>
        """.format("Local SQLite Fallback File" if is_sqlite_fallback else "PostgreSQL Server"),
        unsafe_allow_html=True
    )

# Quick Sidebar Guide
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/993/993928.png", width=80)
    st.markdown("<h3 style='color: #ffd700; margin-top: 0;'>Navigation Guide</h3>", unsafe_allow_html=True)
    st.info(
        "👈 Use the multi-page menu on the sidebar to navigate:\n\n"
        "1. **Dashboard:** Detailed recruiter analytics.\n"
        "2. **Resume Ingestion:** Upload and digitize resumes.\n"
        "3. **Semantic Search:** Look up workers using conversational queries.\n"
        "4. **Job Matching:** Check candidates ranked against job specs.\n"
        "5. **Agent Monitor:** Trace AI team step-by-step logs in real-time."
    )
