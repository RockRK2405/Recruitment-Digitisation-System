import streamlit as st
import os
import requests
import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ui.components.styling import inject_premium_styles
from services.agents.orchestrator import AgentOrchestrator
from config.settings import settings
from config.logging_config import logger

st.set_page_config(page_title="Resume Ingestion Portal", page_icon="", layout="wide")
inject_premium_styles()

st.markdown('<div class="gradient-title"> Resume Ingestion Portal</div>', unsafe_allow_html=True)
st.markdown('<div class="gradient-subtitle">Upload scanned PDFs or low-quality mobile photos of physical worker resumes</div>', unsafe_allow_html=True)

# File Uploader Widget
uploaded_file = st.file_uploader(
    "Choose a scanned resume document (PDF, PNG, JPG, JPEG)",
    type=["pdf", "png", "jpg", "jpeg"]
)

if uploaded_file is not None:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader(f" Processing: {uploaded_file.name}")
    
    # Trigger processing on button click
    if st.button(" Run AI Recruiting Agents Ingestion"):
        with st.spinner("AI Recruiting Agent Team digesting upload (OCR + LLM Extraction + Credential Audit)..."):
            
            # Save file locally first
            uploads_dir = settings.UPLOAD_DIR
            os.makedirs(uploads_dir, exist_ok=True)
            temp_path = os.path.join(uploads_dir, f"ui_{uploaded_file.name}")
            
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Method A: Try REST API
            processed = False
            response_data = {}
            
            try:
                # Prepare payload
                files = {"file": (uploaded_file.name, open(temp_path, "rb"), uploaded_file.type)}
                res = requests.post("http://localhost:8000/api/resumes/upload", files=files, timeout=30.0)
                if res.status_code == 200:
                    response_data = res.json()
                    processed = True
                    logger.info("Uploaded successfully via REST API.")
            except Exception as e:
                logger.warning(f"REST API call skipped or failed: {str(e)}. Running direct local fallback...")
                
            # Method B: Direct Heuristic Python Execution (Robust Fallback!)
            if not processed:
                try:
                    state = AgentOrchestrator.process_resume(temp_path)
                    if state.status == "completed":
                        response_data = {
                            "run_id": state.run_id,
                            "status": state.status,
                            "ocr_engine_used": state.ocr_engine,
                            "ocr_confidence": round(state.ocr_confidence * 100, 1),
                            "candidate_id": state.candidate_id,
                            "parsed_profile": state.parsed_profile,
                            "verification_status": state.verification_results.get("identity_status"),
                            "anomalies_detected": state.verification_results.get("anomalies_detected", []),
                            "sms_whatsapp_alert": state.notifications_prepared.get("message_body"),
                            "agent_audit_logs": [log["message"] for log in state.agent_logs]
                        }
                        processed = True
                        logger.info("Uploaded and processed successfully via Direct Local Engine.")
                    else:
                        st.error(f"Ingestion failed. Errors reported: {state.errors}")
                except Exception as ex:
                    st.error(f"Failed direct in-process engine: {str(ex)}")

            # Display Ingestion Results on success
            if processed:
                st.balloons()
                st.success(" AI recruitment team completed ingestion successfully!")
                
                # Setup 3 sub-columns: Profile details, Credentials checks, WhatsApp alert preview
                col_det, col_cert, col_sms = st.columns([4, 3, 3])
                
                profile = response_data["parsed_profile"] or {}
                
                with col_det:
                    st.markdown("### 📋 Structurally Extracted Profile")
                    st.markdown(
                        f"""
                        <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); padding: 1rem; border-radius: 8px;">
                            <p><b>Name:</b> {profile.get('name')}</p>
                            <p><b>Phone:</b> {profile.get('phone')}</p>
                            <p><b>Email:</b> {profile.get('email') or 'N/A'}</p>
                            <p><b>Current Location:</b> {profile.get('location')}</p>
                            <p><b>Experience Years:</b> {profile.get('experience_years')} Years</p>
                            <p><b>Primary Domain:</b> {profile.get('industry_domain')}</p>
                            <p><b>Equipment Operated:</b> {", ".join(profile.get('equipment_handled', []))}</p>
                            <p><b>Technical Skills:</b> {", ".join(profile.get('skills', []))}</p>
                            <p><b>Highest Education:</b> {profile.get('education')}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                with col_cert:
                    st.markdown("### 🔒 Compliance & Auditing")
                    v_status = response_data["verification_status"]
                    
                    if v_status == "verified":
                        st.markdown('<span class="badge badge-verified"> VERIFIED PROFILE</span>', unsafe_allow_html=True)
                    elif v_status == "flagged_with_anomalies":
                        st.markdown('<span class="badge badge-warning"> FLAGGED WITH ANOMALIES</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="badge badge-failed"> UNVERIFIED</span>', unsafe_allow_html=True)
                        
                    st.write("")
                    st.write(f"**OCR Digitization Engine:** `{response_data['ocr_engine_used']}`")
                    st.write(f"**OCR Text Confidence:** `{response_data['ocr_confidence']}%`")
                    
                    # Certs list
                    st.write("**Extracted Certifications:**")
                    certs = profile.get("certifications", [])
                    if certs:
                        for c in certs:
                            st.markdown(f"- 🎓 {c.get('name')} (`{c.get('issuer') or 'Govt'}`)")
                    else:
                        st.write("*No safety certifications detected.*")
                        
                    # Anomalies flagged
                    anoms = response_data.get("anomalies_detected", [])
                    if anoms:
                        st.write(" **Flagged Anomalies:**")
                        for an in anoms:
                            st.markdown(f"<span style='color: #ffea00;'>• {an}</span>", unsafe_allow_html=True)
                            
                with col_sms:
                    st.markdown("###  Localization WhatsApp Onboarding Alert")
                    st.info("The Notification Agent automatically drafted this onboarding template in the worker's native tongue:")
                    
                    sms_body = response_data.get("sms_whatsapp_alert")
                    if sms_body:
                        st.markdown(
                            f"""
                            <div style="background: #075e54; color: #ffffff; padding: 1.2rem; border-radius: 12px; border-bottom-left-radius: 0; box-shadow: 0 4px 10px rgba(0,0,0,0.15);">
                                <small style="color: #25d366; font-weight:bold;">📲 WhatsApp Message Prep</small>
                                <p style="margin-top: 0.5rem; font-size: 0.95rem; line-height: 1.5;">{sms_body}</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        st.write("*No localization message prepared.*")

                # 4. Target Recommendations Section
                st.markdown("---")
                st.markdown("###  Targeted Job Openings Recommendations")
                
                # Fetch recommendations
                recs = []
                recs_processed = False
                candidate_id = response_data.get("candidate_id")
                
                if candidate_id:
                    # Method A: Try REST API
                    try:
                        res = requests.get(f"http://localhost:8000/api/match/recommendations/{candidate_id}", timeout=2.0)
                        if res.status_code == 200:
                            recs = res.json()["recommendations"]
                            recs_processed = True
                    except Exception:
                        pass
                        
                    # Method B: Direct DB Fallback
                    if not recs_processed:
                        try:
                            from database.connection import SessionLocal
                            from services.matching.engine import MatchingEngine
                            
                            db = SessionLocal()
                            try:
                                recs = MatchingEngine.recommend_jobs_for_candidate(db, candidate_id)
                                recs_processed = True
                            finally:
                                db.close()
                        except Exception as ex:
                            st.error(f"Failed to fetch local recommendations: {str(ex)}")
                            
                if recs_processed and recs:
                    st.write(f"Ranks of seeded vacancies calculated for **{profile.get('name')}**:")
                    
                    for r_idx, r in enumerate(recs):
                        r_score = r["overall_score"]
                        r_color = r.get("hiring_status_color", "#ff1744")
                        r_status = r.get("hiring_status", "Failed")
                        
                        badge_class = "badge-failed"
                        if r_status == "Passed":
                            badge_class = "badge-verified"
                        elif r_status == "May Hire":
                            badge_class = "badge-warning"
                            
                        penalty = ""
                        if r.get("has_compliance_penalty"):
                            penalty = '<span class="badge badge-failed"> missing safety regulatory certificates</span>'
                            
                        st.markdown(
                            f"""<div style="background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.03); padding: 1.2rem; border-radius: 8px; margin-bottom: 0.6rem; display: flex; justify-content: space-between; align-items: center;">
<div>
<span style="font-size: 1.1rem; font-weight: 600; color: #ffffff;">💼 {r['job_title']}</span>
<span style="margin-left: 0.8rem;" class="badge {badge_class}">{r_status.upper()}</span>
{penalty}
<div style="font-size: 0.85rem; color: #8f9bb3; margin-top: 0.3rem;">Missing Certs: {", ".join(r['missing_certs']) if r['missing_certs'] else 'None'}</div>
</div>
<div style="font-size: 1.3rem; font-weight: bold; color: {r_color}; text-align:right;">
{r_score}% Match
</div>
</div>""",
                            unsafe_allow_html=True
                        )
                else:
                    st.write("*No job description matches calculated.*")

    st.markdown('</div>', unsafe_allow_html=True)
