import streamlit as st
import requests
import json
import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from config.logging_config import logger
from ui.components.styling import inject_premium_styles

def get_candidate_context():
    """Queries all candidate records and returns a compressed text representation for LLM context."""
    from database.connection import SessionLocal
    from database.models import Candidate
    
    db = SessionLocal()
    try:
        candidates = db.query(Candidate).all()
        if not candidates:
            return "No candidates have been ingested into the system yet."
            
        context = "Here are the candidate summaries currently registered in the database:\n"
        for i, c in enumerate(candidates, 1):
            resume = c.resume
            skills = resume.skills_list if resume else ""
            domain = resume.primary_domain if resume else ""
            exp = resume.experience_years if resume else 0.0
            certs = ", ".join([cert.name for cert in c.certifications]) if c.certifications else "None"
            
            # Short, single-line candidate overview to save prompt tokens
            context += f"- Candidate #{i}: {c.name or 'Unknown'} | Domain: {domain or 'Industrial'} | Exp: {exp} yrs | Skills: {skills or 'N/A'} | Certs: {certs}\n"
        return context
    except Exception as e:
        logger.error(f"Error retrieving candidate context for chatbot: {str(e)}")
        return f"Error retrieving candidate records: {str(e)}"
    finally:
        db.close()

def get_detailed_candidate_context(prompt: str) -> str:
    """If a candidate's name is mentioned in the prompt, returns their full profile detail."""
    from database.connection import SessionLocal
    from database.models import Candidate
    
    prompt_lower = prompt.lower()
    db = SessionLocal()
    try:
        candidates = db.query(Candidate).all()
        details = ""
        for c in candidates:
            if c.name and c.name.lower() in prompt_lower:
                resume = c.resume
                skills = resume.skills_list if resume else ""
                domain = resume.primary_domain if resume else ""
                exp = resume.experience_years if resume else 0.0
                equip = resume.equipment_handled if resume else ""
                languages = resume.languages if resume else ""
                edu = resume.education if resume else ""
                certs = ", ".join([cert.name for cert in c.certifications]) if c.certifications else "None"
                
                details += f"\n--- DETAILED PROFILE FOR {c.name.upper()} ---\n"
                details += f"Full Name: {c.name}\n"
                details += f"Email: {c.email or 'N/A'}\n"
                details += f"Phone: {c.phone or 'N/A'}\n"
                details += f"Location: {c.location or 'N/A'}\n"
                details += f"Address: {c.address or 'N/A'}\n"
                details += f"Industry Domain: {domain or 'Industrial'}\n"
                details += f"Experience: {exp} years\n"
                details += f"Education: {edu or 'N/A'}\n"
                details += f"Languages: {languages or 'N/A'}\n"
                details += f"Skills: {skills or 'N/A'}\n"
                details += f"Heavy Equipment Operated: {equip or 'N/A'}\n"
                details += f"Safety Certifications: {certs}\n"
                details += f"Onboarding Flag: {'Low Literacy Onboarding Assistance Required' if c.low_literacy_flag else 'None'}\n"
                details += f"Application Status: {c.status}\n"
                details += "--------------------------------------\n"
        return details
    except Exception as e:
        logger.error(f"Error retrieving detailed candidate context: {str(e)}")
        return ""
    finally:
        db.close()

def get_job_descriptions_context():
    """Queries all job description records and returns a compressed text representation for LLM context."""
    from database.connection import SessionLocal
    from database.models import JobDescription
    
    db = SessionLocal()
    try:
        jobs = db.query(JobDescription).all()
        if not jobs:
            return "No job descriptions are currently registered."
            
        context = "Here are the active job description vacancies in the database:\n"
        for j in jobs:
            # Compact job overview
            context += f"- Job: {j.title} | Location: {j.location or 'N/A'} | Exp req: {j.experience_years_required} yrs | Skills req: {j.required_skills or 'N/A'}\n"
        return context
    except Exception as e:
        logger.error(f"Error retrieving job description context for chatbot: {str(e)}")
        return f"Error retrieving job descriptions: {str(e)}"
    finally:
        db.close()

def get_detailed_job_context(prompt: str) -> str:
    """If a job title is mentioned in the prompt, returns its full job description detail."""
    from database.connection import SessionLocal
    from database.models import JobDescription
    
    prompt_lower = prompt.lower()
    db = SessionLocal()
    try:
        jobs = db.query(JobDescription).all()
        details = ""
        for j in jobs:
            if j.title:
                matched = False
                if j.title.lower() in prompt_lower:
                    matched = True
                else:
                    # Match words of job title in prompt
                    for word in j.title.lower().split():
                        if len(word) > 3 and word in prompt_lower:
                            matched = True
                            break
                if matched:
                    details += f"\n--- DETAILED JOB SPECIFICATION FOR {j.title.upper()} ---\n"
                    details += f"Title: {j.title}\n"
                    details += f"Location: {j.location or 'N/A'}\n"
                    details += f"Experience Required: {j.experience_years_required} years\n"
                    details += f"Required Skills: {j.required_skills or 'N/A'}\n"
                    details += f"Required Certifications: {j.required_certifications or 'N/A'}\n"
                    details += f"Description: {j.description or 'N/A'}\n"
                    details += "--------------------------------------\n"
        return details
    except Exception as e:
        logger.error(f"Error retrieving detailed job context: {str(e)}")
        return ""
    finally:
        db.close()

def call_chat_llm(messages: list) -> str:
    """Unified Chat LLM call helper supporting Ollama and Gemini fallback."""
    provider = (settings.LLM_PROVIDER or "ollama").lower()
    
    if provider == "ollama":
        try:
            chat_url = settings.OLLAMA_URL.replace("/api/generate", "/api/chat")
            payload = {
                "model": settings.OLLAMA_MODEL,
                "messages": messages,
                "stream": False
            }
            logger.info(f"Calling Ollama Chat API at: {chat_url} for model: {settings.OLLAMA_MODEL}")
            # Increased timeout to 300.0 seconds to prevent read timeouts on slower devices
            response = requests.post(chat_url, json=payload, timeout=300.0)
            if response.status_code == 200:
                result = response.json()
                return result.get("message", {}).get("content", "").strip()
            else:
                logger.error(f"Ollama returned non-200 status code: {response.status_code}, detail: {response.text}")
        except Exception as e:
            logger.warning(f"Ollama Chat call failed: {str(e)}")
            
    # Gemini fallback
    api_key = settings.GEMINI_API_KEY or ""
    if api_key and "YOUR_GEMINI_API" not in api_key:
        try:
            from google import genai
            from google.genai import types
            
            prompt = ""
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    prompt += f"System: {content}\n\n"
                elif role == "user":
                    prompt += f"User: {content}\n"
                elif role == "assistant":
                    prompt += f"Assistant: {content}\n"
            prompt += "Assistant:"
            
            logger.info("Falling back to Gemini model for Chatbot...")
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Gemini fallback chat call failed: {str(e)}")
            
    return "I am having trouble connecting to the local AI model (Ollama) or the backup AI service. Please ensure Ollama is running and has the model loaded."

def chatbot_interface():
    # Inject styling
    inject_premium_styles()
    
    st.markdown('<div class="gradient-title">💬 HR Resume Chatbot</div>', unsafe_allow_html=True)
    st.markdown('<div class="gradient-subtitle">Interact with the local Qwen model to query candidate profiles and match vacancies</div>', unsafe_allow_html=True)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Sidebar parameters and info
    with st.sidebar:
        st.subheader("🤖 Chatbot Engine")
        st.info(f"**Model:** `{settings.OLLAMA_MODEL}`")
        st.info(f"**Provider:** `{settings.LLM_PROVIDER.upper()}`")
        
        st.markdown("---")
        st.markdown("### 👤 Registered Candidates")
        from database.connection import SessionLocal
        from database.models import Candidate
        db = SessionLocal()
        try:
            candidates = db.query(Candidate).all()
            if candidates:
                for c in candidates:
                    st.markdown(f"- **{c.name}** ({c.location or 'N/A'})")
            else:
                st.write("No candidate records found.")
        except Exception as e:
            st.error(f"DB Error: {str(e)}")
        finally:
            db.close()
            
        st.markdown("---")
        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []
            st.rerun()

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("Ask a question (e.g. 'Compare Ramesh with other candidates' or 'Which candidate is best suited for DGMS Coal Mining Sirdar?'):"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get system prompt with candidate and job contexts
        with st.spinner("🧠 Local Qwen LLM is thinking..."):
            candidate_context = get_candidate_context()
            jobs_context = get_job_descriptions_context()
            
            # Dynamic retrieval details
            detailed_candidate = get_detailed_candidate_context(prompt)
            detailed_job = get_detailed_job_context(prompt)
            
            system_prompt = f"""You are Kshamata Assistant, a friendly and professional HR recruiting assistant. 
Your goal is to help recruiters search, evaluate, and compare candidates for various industrial roles.

Below is the live data from the Kshamata database. Use this information to answer user queries accurately.

---
CANDIDATE DATABASE SUMMARY:
{candidate_context}
---
JOB VACANCIES SUMMARY:
{jobs_context}
---
{detailed_candidate}
{detailed_job}

When answering questions:
1. Always base your answers on the provided candidates and job descriptions where relevant.
2. Be helpful, professional, and highlight candidate qualifications (experience, safety certs, equipment).
3. If asked about a candidate who is not in the list, state politely that they are not in our database.
4. Highlight safety compliance if asked: remember that in industrial roles, safety certs (like DGMS, Boiler Attendant, OSHA) are critical.
"""

            # Build messages list
            messages = [{"role": "system", "content": system_prompt}]
            for msg in st.session_state.messages:
                messages.append({"role": msg["role"], "content": msg["content"]})
                
            # Get response from the unified LLM runner
            response = call_chat_llm(messages)

        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            st.markdown(response)

if __name__ == "__main__":
    chatbot_interface()