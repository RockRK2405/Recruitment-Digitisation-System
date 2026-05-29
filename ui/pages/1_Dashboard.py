import streamlit as st
import plotly.express as px
import pandas as pd
import requests
import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ui.components.styling import inject_premium_styles
from database.connection import SessionLocal
from database.models import Candidate, UploadedDocument, JobDescription, AuditLog, Certification, Resume

st.set_page_config(page_title="Analytics Dashboard", page_icon="", layout="wide")
inject_premium_styles()

st.markdown('<div class="gradient-title"> Analytics Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="gradient-subtitle">Demographics, verification rates, and system audit trails</div>', unsafe_allow_html=True)

# Fetch stats helper
def fetch_raw_data() -> dict:
    try:
        res = requests.get("http://localhost:8000/api/analytics/summary", timeout=1.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
        
    db = SessionLocal()
    try:
        total_cand = db.query(Candidate).count()
        low_lit = db.query(Candidate).filter(Candidate.low_literacy_flag == True).count()
        total_certs = db.query(Certification).count()
        verified_certs = db.query(Certification).filter(Certification.verification_status == "verified").count()
        
        # Domains distribution count
        domains = {}
        resumes = db.query(Resume).all()
        for r in resumes:
            dom = r.primary_domain or "General"
            domains[dom] = domains.get(dom, 0) + 1
            
        return {
            "total_candidates": total_cand,
            "low_literacy_applicants": low_lit,
            "total_certifications_audited": total_certs,
            "verified_certifications": verified_certs,
            "domains": domains
        }
    except Exception:
        return {"total_candidates": 0, "low_literacy_applicants": 0, "total_certifications_audited": 0, "verified_certifications": 0, "domains": {}}
    finally:
        db.close()

data = fetch_raw_data()

if data["total_candidates"] == 0:
    st.info("No worker profiles indexed yet. Upload resumes to see live data.")
else:
    # 1. Visual Chart Grid
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader(" Literacy & Digital Assistance Needs")
        
        # Prepare Literacy DataFrame
        norm_count = data["total_candidates"] - data["low_literacy_applicants"]
        lit_df = pd.DataFrame({
            "Onboarding Type": ["Low Literacy Help Needed", "Standard Digital Profiles"],
            "Workers": [data["low_literacy_applicants"], norm_count]
        })
        
        fig1 = px.pie(
            lit_df, names="Onboarding Type", values="Workers",
            color_discrete_sequence=["#ffea00", "#00b0ff"],
            hole=0.4
        )
        fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="#ffffff", margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_chart2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader(" Workforce Industry Domain Distribution")
        
        # Prepare Domain DataFrame
        dom_dict = data.get("domains", {"Mining": 1})
        if not dom_dict:
            dom_dict = {"Mining": 1}
        dom_df = pd.DataFrame({
            "Industry Domain": list(dom_dict.keys()),
            "Active Workers": list(dom_dict.values())
        })
        
        fig2 = px.bar(
            dom_df, x="Industry Domain", y="Active Workers",
            color="Industry Domain",
            color_discrete_sequence=["#ff8c00", "#00e676", "#00b0ff", "#d500f9"]
        )
        fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="#ffffff", showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# 2. Detailed Audit logs list
st.markdown("###  Platform Administration Audit Trail")
st.markdown('<div class="glass-card">', unsafe_allow_html=True)

db = SessionLocal()
try:
    audits = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
    if audits:
        audit_data = [
            {
                "ID": a.id,
                "Audit Action Event": a.action.replace("_", " ").title(),
                "Transaction Summary Details": a.details,
                "Executed Timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
            for a in audits
        ]
        st.dataframe(pd.DataFrame(audit_data), use_container_width=True)
    else:
        st.text("No audit transactions logged yet.")
except Exception as e:
    st.error(f"Failed to fetch audit logs: {str(e)}")
finally:
    db.close()

st.markdown('</div>', unsafe_allow_html=True)
