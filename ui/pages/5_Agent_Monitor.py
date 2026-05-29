import streamlit as st
import json
import requests
import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ui.components.styling import inject_premium_styles
from database.connection import SessionLocal
from database.models import AgentLog
from config.logging_config import logger

st.set_page_config(page_title="AI Agent Flow Monitor ", page_icon="", layout="wide")
inject_premium_styles()

st.markdown('<div class="gradient-title"> AI Agent Flow Monitor</div>', unsafe_allow_html=True)
st.markdown('<div class="gradient-subtitle">Track real-time step-by-step executions and state snapshots of the AI recruitment crew</div>', unsafe_allow_html=True)

# Helper to fetch all unique run sessions logged
def get_unique_run_sessions() -> list[str]:
    db = SessionLocal()
    try:
        # Group by run_id, ordering by latest log
        sessions = db.query(AgentLog.run_id).distinct().all()
        return [s[0] for s in sessions]
    except Exception as e:
        logger.error(f"Failed to query run sessions: {str(e)}")
        return []
    finally:
        db.close()

sessions = get_unique_run_sessions()

if not sessions:
    st.info(
        "No AI agent transaction runs logged in the database yet. "
        "Go to the 'Resume Ingestion' page and upload a resume to trigger the agent crew!"
    )
else:
    # Selector for Run Session ID
    selected_session = st.selectbox(
        "Select an active AI Ingestion Run Session ID to inspect:",
        sessions,
        index=0
    )
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(f"### ⚡ Ingestion Execution Trail: {selected_session}")
    
    # Fetch log steps
    logs = []
    processed = False
    
    # Method A: Try REST API
    try:
        res = requests.get(f"http://localhost:8000/api/analytics/agent-logs/{selected_session}", timeout=1.0)
        if res.status_code == 200:
            logs = res.json()["steps"]
            processed = True
    except Exception:
        pass
        
    # Method B: Direct DB Fallback
    if not processed:
        db = SessionLocal()
        try:
            db_logs = db.query(AgentLog).filter(AgentLog.run_id == selected_session).order_by(AgentLog.timestamp.asc()).all()
            logs = [
                {
                    "agent": l.agent_name,
                    "message": l.message,
                    "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "state_snapshot": l.state_snapshot
                }
                for l in db_logs
            ]
            processed = True
        except Exception as ex:
            st.error(f"Failed to query agent logs: {str(ex)}")
        finally:
            db.close()

    # Render Log pipeline
    if processed:
        if not logs:
            st.text("No steps recorded for this session.")
        else:
            st.write(f"Total pipeline steps completed: {len(logs)}")
            
            for index, step in enumerate(logs):
                agent = step["agent"]
                message = step["message"]
                
                # Determine styling colors based on agent node names
                color_theme = "#00b0ff" # Blue standard
                if "Intake" in agent:
                    color_theme = "#ffd700" # Gold
                elif "Screening" in agent:
                    color_theme = "#d500f9" # Purple
                elif "Verification" in agent:
                    color_theme = "#ff1744" if "anomaly" in message.lower() else "#00e676" # Red or Green
                elif "Notification" in agent:
                    color_theme = "#00e676" # Green WhatsApp
                
                st.markdown(
                    f"""
                    <div class="pipeline-step" style="border-left: 5px solid {color_theme}; background: rgba(255,255,255,0.02); padding: 1.2rem; border-radius: 8px; margin-bottom: 0.8rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #8f9bb3; font-weight:bold; text-transform: uppercase;">
                            <span> Agent: {agent}</span>
                            <span> Step #{index+1} - {step['timestamp']}</span>
                        </div>
                        <div style="margin-top: 0.5rem; font-size: 1rem; color: #ffffff; font-weight: 500;">
                            {message}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Expandable State Snapshot display
                with st.expander(f" Step #{index+1} JSON State variables snapshot"):
                    try:
                        snap_json = json.loads(step["state_snapshot"])
                        st.json(snap_json)
                    except Exception:
                        st.text(step["state_snapshot"])

    st.markdown('</div>', unsafe_allow_html=True)
st.sidebar.info("You can view execution histories of the AI team and evaluate details including OCR confidence, database IDs, and validation errors.")
