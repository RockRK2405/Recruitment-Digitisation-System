from database.connection import SessionLocal
from database.models import Candidate
from services.agents.state import AgentState
from config.logging_config import logger

class NotificationAgent:
    """Notification Agent Node: Composes and logs localized SMS and WhatsApp templates for workers."""
    
    @staticmethod
    def execute(state: AgentState) -> AgentState:
        state.current_node = "notification"
        state.log_transition("Notification Agent", "Drafting personalized onboarding notifications for worker...")
        
        if state.status == "failed" or not state.candidate_id:
            state.log_transition("Notification Agent", "Skipping notification node due to prior failures.")
            return state

        db = SessionLocal()
        try:
            # 1. Fetch Candidate
            candidate = db.query(Candidate).filter(Candidate.id == state.candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate ID {state.candidate_id} not found during notification.")

            resume = candidate.resume
            languages = [l.strip().lower() for l in (resume.languages or "").split(",") if l.strip()]
            primary_lang = languages[0] if languages else "hindi"
            
            name = candidate.name or "Worker"
            phone = candidate.phone or "N/A"
            domain = resume.primary_domain or "Industrial workforce"
            
            # 2. Localized templates selection
            sms_text = ""
            channel = "WhatsApp / SMS"
            
            if "hindi" in primary_lang or "hin" in primary_lang:
                sms_text = (
                    f"नमस्ते {name}, आपकी प्रोफाइल ('{domain}') हमारी भर्ती प्रणाली में सुरक्षित रूप से दर्ज कर ली गई है। "
                    f"आपके प्रमाणपत्रों का सत्यापन हो गया है। जल्द ही हमारे भर्ती प्रबंधक आपसे संपर्क करेंगे।"
                )
                state.log_transition("Notification Agent", "Detected Hindi as primary tongue. Formulating Devanagari alert template.")
            elif "spanish" in primary_lang or "esp" in primary_lang:
                sms_text = (
                    f"Hola {name}, su perfil de '{domain}' ha sido registrado en nuestra plataforma. "
                    f"Sus certificaciones han sido validadas. Un reclutador se pondrá en contacto pronto."
                )
                state.log_transition("Notification Agent", "Detected Spanish language preference. Formulating Spanish alert template.")
            else:
                # English default
                sms_text = (
                    f"Hello {name}, your candidate profile for '{domain}' has been successfully registered. "
                    f"Your safety credentials are verified. A recruiter will contact you shortly."
                )
                state.log_transition("Notification Agent", "Defaulting to English onboarding notification template.")

            # 3. Simulate transmission dispatch logging
            prepared_payload = {
                "recipient_name": name,
                "recipient_phone": phone,
                "preferred_language": primary_lang,
                "channel": channel,
                "message_body": sms_text,
                "dispatch_simulated_timestamp": "SUCCESS"
            }
            
            state.notifications_prepared = prepared_payload
            state.log_transition(
                "Notification Agent", 
                f"Onboarding message template ready for dispatch to phone: {phone}"
            )
            
            # Transition state to completed
            state.current_node = "finish"
            state.status = "completed"
            state.log_transition("Notification Agent", "Workforce onboarding notification agent finished execution.")
            
        except Exception as e:
            state.status = "failed"
            state.errors.append(str(e))
            state.log_transition("Notification Agent", f"CRITICAL notification node failure: {str(e)}")
        finally:
            db.close()
            
        return state
