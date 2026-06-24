import streamlit as st
import pandas as pd
import requests
import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ui.components.styling import inject_premium_styles
from database.connection import SessionLocal
from database.models import Candidate, Resume
from services.embeddings.vector_store import VectorStoreService
from services.auth import require_role
from config.logging_config import logger

st.set_page_config(page_title="Conversational Semantic Search ", page_icon="🔍", layout="wide")
inject_premium_styles()

# Enforce role gate
user = require_role(st, "viewer")

st.markdown('<div class="gradient-title"> Conversational Semantic Search</div>', unsafe_allow_html=True)
st.markdown('<div class="gradient-subtitle">Search the digitized workforce database using natural conversation queries</div>', unsafe_allow_html=True)

# Search Bar Widget
search_query = st.text_input(
    "Enter your worker hiring search requirements (e.g. 'Find welders with thermal plant experience and safety certification')",
    placeholder="Search for mining riggers, heavy excavator operators, ITI electricians..."
)

if search_query:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader(f"⚡ Search Results for: '{search_query}'")
    
    # Method A: Try REST API
    processed = False
    candidates = []
    
    try:
        payload = {"query": search_query, "limit": 10}
        res = requests.post("http://localhost:8000/api/match/semantic", json=payload, timeout=5.0)
        if res.status_code == 200:
            candidates = res.json()["candidates"]
            processed = True
            logger.info("Search executed successfully via REST API.")
    except Exception as e:
        logger.warning(f"REST API search failed: {str(e)}. Attempting direct database fallback...")
        
    # Method B: Direct Heuristic Python Execution (Robust Fallback!)
    if not processed:
        try:
            matches = VectorStoreService.search_candidates(search_query, limit=10)
            
            db = SessionLocal()
            try:
                for m in matches:
                    cid = int(m["id"])
                    cand = db.query(Candidate).filter(Candidate.id == cid).first()
                    if cand:
                        res_obj = cand.resume
                        candidates.append({
                            "candidate_id": cand.id,
                            "name": cand.name,
                            "location": cand.location,
                            "phone": cand.phone,
                            "status": cand.status,
                            "low_literacy_flag": cand.low_literacy_flag,
                            "vector_similarity_score": round(float(m["score"]) * 100, 1),
                            "primary_domain": res_obj.primary_domain if res_obj else None,
                            "experience_years": res_obj.experience_years if res_obj else 0.0,
                            "skills": [s.strip() for s in (res_obj.skills_list or "").split(",") if s.strip()] if res_obj else []
                        })
                processed = True
            finally:
                db.close()
        except Exception as ex:
            st.error(f"Heuristic Search Engine failure: {str(ex)}")

    # Display Matching Candidates
    if processed:
        if not candidates:
            st.info("No candidates match this search. Try modifying key words (e.g. welder, excavator, mining).")
        else:
            st.write(f"Found {len(candidates)} matching candidate profiles:")
            
            for index, cand in enumerate(candidates):
                score = cand["vector_similarity_score"]
                
                # Determine score color theme
                score_color = "#00e676" if score >= 80 else "#ffd700" if score >= 50 else "#ff1744"
                
                st.markdown(
                    f"""
                    <div style="background: rgba(22, 26, 32, 0.85); border: 1px solid rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 12px; margin-bottom: 0.8rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-size: 1.25rem; font-weight: 600; color: #ffffff;">👤 {cand['name']}</span>
                                <span style="margin-left: 1rem;" class="badge {'badge-low-literacy' if cand['low_literacy_flag'] else 'badge-verified'}">
                                    {'Low Literacy Assist Needed' if cand['low_literacy_flag'] else 'Standard Profile'}
                                </span>
                            </div>
                            <div style="font-size: 1.2rem; font-weight: bold; color: {score_color};">
                                Match: {score}%
                            </div>
                        </div>
                        
                        <div style="margin-top: 0.8rem; display: grid; grid-template-columns: 1fr 1fr 1fr; font-size: 0.9rem; color: #cbd5e1;">
                            <div> <b>Location:</b> {cand['location'] or 'N/A'}</div>
                            <div> <b>Domain:</b> {cand['primary_domain'] or 'N/A'}</div>
                            <div> <b>Experience:</b> {cand['experience_years']} Years</div>
                        </div>
                        
                        <div style="margin-top: 0.6rem; font-size: 0.85rem; color: #8f9bb3;">
                            <b> Skills list:</b> {", ".join(cand['skills'])}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Dynamic detailed compliance review option
                with st.expander(f"🔍 Compliance details for {cand['name']}"):
                    st.write(f"**Contact Number:** `{cand['phone'] or 'N/A'}`")
                    st.write(f"**Application State:** `{cand['status'].title()}`")
                    st.write("Ensure safety qualifications are audited in the **Job Matching** portal prior to scheduling shifts.")

    st.markdown('</div>', unsafe_allow_html=True)
