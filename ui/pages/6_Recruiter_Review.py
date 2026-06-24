import streamlit as st
import pandas as pd
import requests
import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ui.components.styling import inject_premium_styles
from database.connection import SessionLocal
from database.models import JobDescription, Candidate, RecruiterDecision, RecruiterFeedback, CandidateTag
from services.matching.engine import MatchingEngine
from services.auth import require_role
from config.logging_config import logger

st.set_page_config(page_title="Recruiter Review Panel", page_icon="📋", layout="wide")
inject_premium_styles()

# Require Recruiter role (allows Recruiter and Admin)
user = require_role(st, "recruiter")

st.markdown('<div class="gradient-title">Recruiter Review Panel</div>', unsafe_allow_html=True)
st.markdown('<div class="gradient-subtitle">Act on system recommendations, manage candidate pipeline decisions, and adjust matching intelligence via feedback.</div>', unsafe_allow_html=True)

# Helper to fetch active Job Descriptions
def get_jobs_list() -> list[dict]:
    try:
        res = requests.get("http://localhost:8000/api/jobs", timeout=1.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
        
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

# Load JDs
jobs = get_jobs_list()

if not jobs:
    st.info("No job descriptions registered in the database. Go to 'Job Matching' to register job descriptions first.")
else:
    # Select Job
    job_options = {f"{j['title']} ({j['location']})": j for j in jobs}
    selected_job_name = st.selectbox("Select target Job Description to review candidates:", list(job_options.keys()))
    selected_job = job_options[selected_job_name]
    
    # Display selected Job specs
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(f"### 🎯 Job Spec: {selected_job['title']}")
    st.write(selected_job["description"])
    st.markdown('</div>', unsafe_allow_html=True)

    # Sidebar Filter Controls
    with st.sidebar:
        st.markdown("<h3 style='color: #ffd700;'>Pipeline Filters</h3>", unsafe_allow_html=True)
        pipeline_filter = st.selectbox(
            "Filter Candidates by status:",
            ["All Candidates", "Needs Review (System)", "Auto Accepted (System)", "Shortlisted", "Accepted", "Rejected", "Hold"]
        )

    # Score Candidates and Rank
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
        
    # Method B: Direct Heuristic Python Execution
    if not processed:
        db = SessionLocal()
        try:
            rankings = MatchingEngine.rank_candidates_for_job(db, selected_job["id"], limit=20)
            processed = True
        except Exception as ex:
            st.error(f"Heuristic Ranking Engine failure: {str(ex)}")
        finally:
            db.close()

    # Load recruiter decisions and tags for this job/candidates
    db = SessionLocal()
    try:
        decisions_by_cand = {}
        decisions = db.query(RecruiterDecision).filter(RecruiterDecision.job_id == selected_job["id"]).all()
        for d in decisions:
            decisions_by_cand[d.candidate_id] = d

        tags_by_cand = {}
        tags = db.query(CandidateTag).all()
        for t in tags:
            if t.candidate_id not in tags_by_cand:
                tags_by_cand[t.candidate_id] = []
            tags_by_cand[t.candidate_id].append(t)
            
        candidate_status_by_id = {}
        candidates = db.query(Candidate).all()
        for c in candidates:
            candidate_status_by_id[c.id] = c.status
    except Exception as e:
        st.error(f"Failed to fetch decisions or tags: {str(e)}")
        decisions_by_cand = {}
        tags_by_cand = {}
        candidate_status_by_id = {}
    finally:
        db.close()

    # Filter rankings based on selected pipeline filter
    filtered_rankings = []
    for rank in rankings:
        cand_id = rank["candidate_id"]
        decision_rec = decisions_by_cand.get(cand_id)
        decision_str = decision_rec.decision if decision_rec else None
        system_status = candidate_status_by_id.get(cand_id, "onboarded")
        
        matches_filter = False
        if pipeline_filter == "All Candidates":
            matches_filter = True
        elif pipeline_filter == "Needs Review (System)" and system_status == "needs_review":
            matches_filter = True
        elif pipeline_filter == "Auto Accepted (System)" and system_status == "auto_accepted":
            matches_filter = True
        elif pipeline_filter == "Shortlisted" and decision_str == "shortlisted":
            matches_filter = True
        elif pipeline_filter == "Accepted" and decision_str == "accepted":
            matches_filter = True
        elif pipeline_filter == "Rejected" and decision_str == "rejected":
            matches_filter = True
        elif pipeline_filter == "Hold" and decision_str == "hold":
            matches_filter = True
            
        if matches_filter:
            filtered_rankings.append(rank)

    # Display Scored Rankings & Review Dashboard
    st.markdown(f"### 📋 Candidates Review Shortlist ({len(filtered_rankings)} match results)")
    
    if processed:
        if not filtered_rankings:
            st.info("No candidates match the selected filters.")
        else:
            for idx, rank in enumerate(filtered_rankings):
                cand_id = rank["candidate_id"]
                overall = rank["overall_score"]
                score_color = "#00e676" if overall >= 80 else "#ffd700" if overall >= 60 else "#ff1744"
                
                # Fetch database states
                system_status = candidate_status_by_id.get(cand_id, "onboarded")
                decision_rec = decisions_by_cand.get(cand_id)
                decision_str = decision_rec.decision if decision_rec else "Pending Decision"
                decision_notes = decision_rec.notes if decision_rec else ""
                
                # Color code badges
                if decision_str == "accepted":
                    badge_class = "badge-verified"
                elif decision_str in ["shortlisted", "hold"]:
                    badge_class = "badge-warning"
                elif decision_str == "rejected":
                    badge_class = "badge-failed"
                else:
                    badge_class = "badge-low-literacy" # Neutral for pending
                
                # Draw main card
                st.markdown(
                    f"""<div style="background: rgba(22, 26, 32, 0.85); border: 1px solid rgba(255, 255, 255, 0.05); padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.05); padding-bottom: 0.8rem;">
<div>
<span style="font-size: 1.4rem; font-weight: 600; color: #ffffff;">{rank['candidate_name']}</span>
<span style="margin-left: 0.5rem;" class="badge {badge_class}">{decision_str.upper()}</span>
<span style="margin-left: 0.5rem;" class="badge {'badge-failed' if system_status == 'needs_review' else 'badge-verified'}">SYSTEM: {system_status.replace('_', ' ').upper()}</span>
</div>
<div style="font-size: 1.8rem; font-weight: bold; color: {score_color};">
{overall}%
</div>
</div>
<div style="margin-top: 1rem; display: grid; grid-template-columns: 1fr 1fr; font-size: 0.95rem;">
<div>
<span style="color: #00e676;"><b>✓ Matched Skills:</b></span> {", ".join(rank['matched_skills']) if rank['matched_skills'] else 'None'}<br/>
<span style="color: #ff1744;"><b>✗ Missing Skills:</b></span> {", ".join(rank['missing_skills']) if rank['missing_skills'] else 'None'}
</div>
<div>
<span style="color: #00e676;"><b>✓ Valid Licenses:</b></span> {", ".join(rank['matched_certs']) if rank['matched_certs'] else 'None'}<br/>
<span style="color: #ff1744;"><b>✗ Missing Mandatory Licenses:</b></span> {", ".join(rank['missing_certs']) if rank['missing_certs'] else 'None'}
</div>
</div>
</div>""",
                    unsafe_allow_html=True
                )
                
                # Interactive Operations Container
                with st.container():
                    col_act, col_tags, col_feed = st.columns([2, 2, 3])
                    
                    # 1. Pipeline Decisions
                    with col_act:
                        st.markdown("**Pipeline Action Override**")
                        note_val = st.text_input("Decision Notes", value=decision_notes, key=f"notes_{cand_id}_{selected_job['id']}")
                        
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("Accept", key=f"acc_{cand_id}_{selected_job['id']}", use_container_width=True):
                                try:
                                    res = requests.post("http://localhost:8000/api/review/decision", json={
                                        "candidate_id": cand_id,
                                        "job_id": selected_job["id"],
                                        "decision": "accepted",
                                        "notes": note_val,
                                        "recruiter_username": user["username"]
                                    })
                                    st.success("Accepted candidate!")
                                    st.rerun()
                                except Exception:
                                    # Fallback
                                    db = SessionLocal()
                                    existing = db.query(RecruiterDecision).filter(
                                        RecruiterDecision.candidate_id == cand_id,
                                        RecruiterDecision.job_id == selected_job["id"]
                                    ).first()
                                    if existing:
                                        existing.decision = "accepted"
                                        existing.notes = note_val
                                        existing.recruiter_username = user["username"]
                                    else:
                                        db.add(RecruiterDecision(
                                            candidate_id=cand_id, job_id=selected_job["id"],
                                            decision="accepted", notes=note_val, recruiter_username=user["username"]
                                        ))
                                    db.commit()
                                    db.close()
                                    st.success("Accepted candidate (Direct DB)!")
                                    st.rerun()
                                    
                            if st.button("Shortlist", key=f"short_{cand_id}_{selected_job['id']}", use_container_width=True):
                                try:
                                    res = requests.post("http://localhost:8000/api/review/decision", json={
                                        "candidate_id": cand_id,
                                        "job_id": selected_job["id"],
                                        "decision": "shortlisted",
                                        "notes": note_val,
                                        "recruiter_username": user["username"]
                                    })
                                    st.success("Shortlisted candidate!")
                                    st.rerun()
                                except Exception:
                                    db = SessionLocal()
                                    existing = db.query(RecruiterDecision).filter(
                                        RecruiterDecision.candidate_id == cand_id,
                                        RecruiterDecision.job_id == selected_job["id"]
                                    ).first()
                                    if existing:
                                        existing.decision = "shortlisted"
                                        existing.notes = note_val
                                        existing.recruiter_username = user["username"]
                                    else:
                                        db.add(RecruiterDecision(
                                            candidate_id=cand_id, job_id=selected_job["id"],
                                            decision="shortlisted", notes=note_val, recruiter_username=user["username"]
                                        ))
                                    db.commit()
                                    db.close()
                                    st.success("Shortlisted candidate (Direct DB)!")
                                    st.rerun()
                                    
                        with btn_col2:
                            if st.button("Hold", key=f"hold_{cand_id}_{selected_job['id']}", use_container_width=True):
                                try:
                                    res = requests.post("http://localhost:8000/api/review/decision", json={
                                        "candidate_id": cand_id,
                                        "job_id": selected_job["id"],
                                        "decision": "hold",
                                        "notes": note_val,
                                        "recruiter_username": user["username"]
                                    })
                                    st.success("Placed on hold!")
                                    st.rerun()
                                except Exception:
                                    db = SessionLocal()
                                    existing = db.query(RecruiterDecision).filter(
                                        RecruiterDecision.candidate_id == cand_id,
                                        RecruiterDecision.job_id == selected_job["id"]
                                    ).first()
                                    if existing:
                                        existing.decision = "hold"
                                        existing.notes = note_val
                                        existing.recruiter_username = user["username"]
                                    else:
                                        db.add(RecruiterDecision(
                                            candidate_id=cand_id, job_id=selected_job["id"],
                                            decision="hold", notes=note_val, recruiter_username=user["username"]
                                        ))
                                    db.commit()
                                    db.close()
                                    st.success("Candidate on Hold (Direct DB)!")
                                    st.rerun()
                                    
                            if st.button("Reject", key=f"rej_{cand_id}_{selected_job['id']}", use_container_width=True):
                                try:
                                    res = requests.post("http://localhost:8000/api/review/decision", json={
                                        "candidate_id": cand_id,
                                        "job_id": selected_job["id"],
                                        "decision": "rejected",
                                        "notes": note_val,
                                        "recruiter_username": user["username"]
                                    })
                                    st.success("Rejected candidate!")
                                    st.rerun()
                                except Exception:
                                    db = SessionLocal()
                                    existing = db.query(RecruiterDecision).filter(
                                        RecruiterDecision.candidate_id == cand_id,
                                        RecruiterDecision.job_id == selected_job["id"]
                                    ).first()
                                    if existing:
                                        existing.decision = "rejected"
                                        existing.notes = note_val
                                        existing.recruiter_username = user["username"]
                                    else:
                                        db.add(RecruiterDecision(
                                            candidate_id=cand_id, job_id=selected_job["id"],
                                            decision="rejected", notes=note_val, recruiter_username=user["username"]
                                        ))
                                    db.commit()
                                    db.close()
                                    st.success("Rejected candidate (Direct DB)!")
                                    st.rerun()

                    # 2. Candidate Tags Management
                    with col_tags:
                        st.markdown("**Candidate Tags**")
                        cand_tags = tags_by_cand.get(cand_id, [])
                        if cand_tags:
                            tag_badges = "".join([f'<span class="badge badge-low-literacy" style="margin-bottom:0.2rem; display:inline-block;">🏷️ {t.tag}</span>' for t in cand_tags])
                            st.markdown(f'<div style="min-height:2.5rem;">{tag_badges}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div style="min-height:2.5rem; color:#666; font-style:italic;">No custom tags</div>', unsafe_allow_html=True)
                        
                        new_tag = st.text_input("New Tag", key=f"newtag_{cand_id}", placeholder="e.g. interview scheduled")
                        if st.button("Add Tag", key=f"addt_{cand_id}", use_container_width=True):
                            if new_tag.strip():
                                try:
                                    res = requests.post("http://localhost:8000/api/review/tag", json={
                                        "candidate_id": cand_id,
                                        "tag": new_tag.strip(),
                                        "tagged_by": user["username"]
                                    })
                                    st.success("Added tag!")
                                    st.rerun()
                                except Exception:
                                    db = SessionLocal()
                                    db.add(CandidateTag(
                                        candidate_id=cand_id,
                                        tag=new_tag.strip(),
                                        tagged_by=user["username"]
                                    ))
                                    db.commit()
                                    db.close()
                                    st.success("Added tag (Direct DB)!")
                                    st.rerun()
                                    
                    # 3. AI Feedback Loop
                    with col_feed:
                        st.markdown("**Scoring Feedback (AI Adaptation)**")
                        rating = st.slider("Match Quality (1-5 ⭐)", min_value=1, max_value=5, value=4, key=f"rating_{cand_id}_{selected_job['id']}")
                        comment = st.text_input("Comment", placeholder="Why this match is/isn't accurate...", key=f"comment_{cand_id}_{selected_job['id']}")
                        if st.button("Submit Scoring Feedback", key=f"feedt_{cand_id}_{selected_job['id']}", use_container_width=True):
                            try:
                                res = requests.post("http://localhost:8000/api/review/feedback", json={
                                    "candidate_id": cand_id,
                                    "job_id": selected_job["id"],
                                    "match_quality_rating": rating,
                                    "comment": comment.strip() if comment else None,
                                    "original_score": float(overall),
                                    "recruiter_username": user["username"]
                                })
                                st.success("Feedback submitted! System weights will self-tune.")
                                st.rerun()
                            except Exception:
                                db = SessionLocal()
                                db.add(RecruiterFeedback(
                                    candidate_id=cand_id,
                                    job_id=selected_job["id"],
                                    match_quality_rating=rating,
                                    comment=comment.strip() if comment else None,
                                    original_score=float(overall),
                                    recruiter_username=user["username"]
                                ))
                                db.commit()
                                db.close()
                                st.success("Feedback saved (Direct DB)!")
                                st.rerun()
                st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.05); margin-top:1.5rem; margin-bottom:1.5rem;'/>", unsafe_allow_html=True)
