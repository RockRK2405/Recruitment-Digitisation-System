import streamlit as st
import pandas as pd
import requests
import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ui.components.styling import inject_premium_styles
from database.connection import SessionLocal
from database.models import JobDescription, Candidate
from services.matching.engine import MatchingEngine
from config.logging_config import logger

st.set_page_config(page_title="Compliance & Job Matching ", page_icon="", layout="wide")
inject_premium_styles()

st.markdown('<div class="gradient-title"> Compliance & Job Matching</div>', unsafe_allow_html=True)
st.markdown('<div class="gradient-subtitle">Align candidates against Job Descriptions and audit mandatory safety certification compliance</div>', unsafe_allow_html=True)

# Helper to fetch active Job Descriptions
def get_jobs_list() -> list[dict]:
    try:
        res = requests.get("http://localhost:8000/api/jobs", timeout=1.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
        
    # SQLite Direct DB lookup fallback
    db = SessionLocal()
    try:
        jobs = db.query(JobDescription).all()
        return [
            {
                "id": j.id,
                "title": j.title,
                "description": j.description,
                "required_skills": [s.strip() for s in (j.required_skills or "").split(",") if s.strip()],
                "required_certifications": [c.strip() for c in (j.required_certifications or "").split(",") if c.strip()],
                "location": j.location,
                "experience_years_required": j.experience_years_required
            }
            for j in jobs
        ]
    except Exception:
        return []
    finally:
        db.close()

# 1. Option to Register a New Job Description
with st.sidebar:
    st.markdown("<h3 style='color: #ffd700;'>Create Job Description</h3>", unsafe_allow_html=True)
    with st.form("jd_creation_form"):
        title = st.text_input("Job Title", placeholder="e.g. Heavy Crane Operator")
        desc = st.text_area("Job Description", placeholder="Duties, responsibilities...")
        skills = st.text_input("Required Skills (comma separated)", placeholder="rigging, crane control, signals")
        certs = st.text_input("Mandatory Certifications (comma separated)", placeholder="Crane Safety License, First Aid")
        loc = st.text_input("Job Location", value="Jamshedpur, Jharkhand")
        exp_req = st.number_input("Experience Required (Years)", min_value=0.0, value=2.0, step=0.5)
        
        submitted = st.form_submit_button("📁 Register JD")
        if submitted:
            if not title or not desc:
                st.error("Title and Description are required.")
            else:
                # Add to DB
                db = SessionLocal()
                try:
                    jd = JobDescription(
                        title=title,
                        description=desc,
                        required_skills=skills,
                        required_certifications=certs,
                        location=loc,
                        experience_years_required=exp_req
                    )
                    db.add(jd)
                    db.commit()
                    st.success(f"Job Description '{title}' registered successfully!")
                except Exception as ex:
                    st.error(f"Failed to save JD: {str(ex)}")
                finally:
                    db.close()

# Load JDs
jobs = get_jobs_list()

if not jobs:
    st.info("No job descriptions registered in the database. Use the sidebar to create your first industrial job description.")
else:
    # Select Job
    job_options = {f"{j['title']} ({j['location']})": j for j in jobs}
    selected_job_name = st.selectbox("Select target Industrial Job Description to rank workers:", list(job_options.keys()))
    selected_job = job_options[selected_job_name]
    
    # Display selected Job specs
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(f"###  Job Spec: {selected_job['title']}")
    st.write(selected_job["description"])
    
    col_spec1, col_spec2 = st.columns(2)
    with col_spec1:
        st.write(f"**Required Technical Skills:** `{', '.join(selected_job['required_skills'])}`")
    with col_spec2:
        st.write(f"**Mandatory Safety Certificates:** `{', '.join(selected_job['required_certifications'])}`")
    st.markdown('</div>', unsafe_allow_html=True)

    # 2. Score Candidates and Rank
    st.markdown("###  Scored Workforce Rankings")
    
    rankings = []
    processed = False
    
    # Method A: Try REST API
    try:
        res = requests.get(f"http://localhost:8000/api/match/rank/{selected_job['id']}", timeout=5.0)
        if res.status_code == 200:
            rankings = res.json()["rankings"]
            processed = True
    except Exception as e:
        logger.warning(f"REST API rank lookup failed: {str(e)}. Attempting direct database ranking fallback...")
        
    # Method B: Direct Heuristic Python Execution (Robust Fallback!)
    if not processed:
        db = SessionLocal()
        try:
            rankings = MatchingEngine.rank_candidates_for_job(db, selected_job["id"], limit=20)
            processed = True
        except Exception as ex:
            st.error(f"Heuristic Ranking Engine failure: {str(ex)}")
        finally:
            db.close()

    # Display Scored Rankings
    if processed:
        if not rankings:
            st.info("No candidates onboarded in the database. Go to 'Resume Ingestion' to ingest resumes first.")
        else:
            for idx, rank in enumerate(rankings):
                # Score theme
                overall = rank["overall_score"]
                score_color = "#00e676" if overall >= 80 else "#ffd700" if overall >= 60 else "#ff1744"
                
                # Fetch hiring status labels
                hiring_status = rank.get("hiring_status", "Failed")
                if hiring_status == "Passed":
                    badge_class = "badge-verified"
                elif hiring_status == "May Hire":
                    badge_class = "badge-warning"
                else:
                    badge_class = "badge-failed"
                
                # Check for compliance penalty
                penalty_tag = ""
                if rank.get("has_compliance_penalty"):
                    penalty_tag = '<span class="badge badge-failed"> 50% SAFETY COMPLIANCE PENALTY APPLIED</span>'
                
                st.markdown(
                    f"""<div style="background: rgba(22, 26, 32, 0.85); border: 1px solid rgba(255, 255, 255, 0.05); padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem;">
<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.05); padding-bottom: 0.8rem;">
<div>
<span style="font-size: 1.3rem; font-weight: 600; color: #ffffff;">#{idx+1} {rank['candidate_name']}</span>
<span style="margin-left: 0.5rem;" class="badge {badge_class}">{hiring_status.upper()}</span>
<span style="margin-left: 0.5rem;">{penalty_tag}</span>
</div>
<div style="font-size: 1.6rem; font-weight: bold; color: {score_color};">
{overall}%
</div>
</div>
<div style="margin-top: 1rem; display: grid; grid-template-columns: 1fr 1fr 1fr; font-size: 0.95rem; text-align: center; border-bottom: 1px solid rgba(255, 255, 255, 0.05); padding-bottom: 0.8rem;">
<div><b>Vector Score:</b> <br/><span style="color: #00b0ff; font-weight:bold;">{rank['vector_score']}%</span></div>
<div><b>Technical Skills Score:</b> <br/><span style="color: #ffd700; font-weight:bold;">{rank['skill_score']}%</span></div>
<div><b>Safety Credential Score:</b> <br/><span style="color: #00e676; font-weight:bold;">{rank['cert_score']}%</span></div>
</div>
<div style="margin-top: 1rem; display: grid; grid-template-columns: 1fr 1fr; font-size: 0.9rem;">
<div>
<span style="color: #00e676;"><b>✓ Matched Skills:</b></span> {", ".join(rank['matched_skills']) if rank['matched_skills'] else 'None'}<br/>
<span style="color: #ff1744;"><b>✗ Missing Skills:</b></span> {", ".join(rank['missing_skills']) if rank['missing_skills'] else 'None'}
</div>
<div>
<span style="color: #00e676;"><b>✓ Valid Licenses:</b></span> {", ".join(rank['matched_certs']) if rank['matched_certs'] else 'None'}<br/>
<span style="color: #ff1744;"><b>✗ Missing Mandatory Licenses:</b></span> {", ".join(rank['missing_certs']) if rank['missing_certs'] else 'None'}
</div>
</div>
<div style="margin-top: 1rem; background: rgba(0, 0, 0, 0.2); padding: 0.8rem; border-radius: 8px; border-left: 3px solid #ff8c00; font-size: 0.9rem; color: #cbd5e1; font-style: italic;">
<b> AI Matching Auditor Remark:</b> {rank['explanation']}
</div>
</div>""",
                    unsafe_allow_html=True
                )
