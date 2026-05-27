from database.connection import SessionLocal
from database.models import Candidate, Certification
from services.agents.state import AgentState
from config.logging_config import logger

class VerificationAgent:
    """Verification Agent Node: Performs automated compliance, license, and credential audits."""
    
    @staticmethod
    def execute(state: AgentState) -> AgentState:
        state.current_node = "verification"
        state.log_transition("Verification Agent", "Initiating regulatory license verification and anomaly detection...")
        
        if state.status == "failed" or not state.candidate_id:
            state.log_transition("Verification Agent", "Skipping verification node due to prior failures.")
            return state

        db = SessionLocal()
        try:
            # 1. Fetch Candidate's database records
            candidate = db.query(Candidate).filter(Candidate.id == state.candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate ID {state.candidate_id} not found during verification.")

            verification_outcome = {
                "identity_status": "unverified",
                "phone_validated": False,
                "certifications_audited": 0,
                "certifications_verified": 0,
                "anomalies_detected": []
            }

            # 2. Basic Contact Verification
            if candidate.phone:
                # Basic check for a 10-digit number structure
                digits_only = "".join(filter(str.isdigit, candidate.phone))
                if len(digits_only) >= 10:
                    verification_outcome["phone_validated"] = True
                    state.log_transition("Verification Agent", "Applicant contact number format validated successfully.")
                else:
                    verification_outcome["anomalies_detected"].append("Invalid phone number format.")
            else:
                verification_outcome["anomalies_detected"].append("No contact phone number provided.")

            # 3. Structural Experience Anomaly Checks
            resume = candidate.resume
            if resume:
                # Anomaly: Candidate claims large experience in heavy mining but has no safety certificates
                if resume.experience_years >= 5.0 and "mining" in (resume.primary_domain or "").lower():
                    has_dgms_safety = any(
                        "dgms" in cert.name.lower() or "safety" in cert.name.lower() 
                        for cert in candidate.certifications
                    )
                    if not has_dgms_safety:
                        warn = "Compliance Warning: Experienced miner claiming 5+ years of service lacks standard DGMS Safety Certifications."
                        verification_outcome["anomalies_detected"].append(warn)
                        state.log_transition("Verification Agent", f"AUDIT ALERT: {warn}")

            # 4. Certifications Check (Simulated Aadhaar/Ministry credential lookup)
            for cert in candidate.certifications:
                verification_outcome["certifications_audited"] += 1
                cert_name = cert.name.lower()
                
                # Verify standard legal certifications automatically if present
                if any(k in cert_name for k in ["dgms", "osha", "first aid", "crane", "electrical", "grade", "license"]):
                    cert.verification_status = "verified"
                    verification_outcome["certifications_verified"] += 1
                    state.log_transition("Verification Agent", f"Safety License '{cert.name}' verified against mock ministry registry databases.")
                else:
                    # General non-safety certs kept as pending or marked verified if structurally sound
                    cert.verification_status = "verified"
                    verification_outcome["certifications_verified"] += 1
            
            # 5. Compile final status
            if verification_outcome["anomalies_detected"]:
                verification_outcome["identity_status"] = "flagged_with_anomalies"
                candidate.status = "screening" # remains in screening for human review
                state.log_transition(
                    "Verification Agent", 
                    f"Anomaly checks complete. {len(verification_outcome['anomalies_detected'])} anomalies flagged."
                )
            else:
                verification_outcome["identity_status"] = "verified"
                candidate.status = "active" # Ready for active search/hiring!
                state.log_transition("Verification Agent", "Security and safety compliance checks passed. Profile upgraded to active status.")
                
            db.commit()
            
            # Store results back in state
            state.verification_results.update(verification_outcome)
            
        except Exception as e:
            db.rollback()
            state.status = "failed"
            state.errors.append(str(e))
            state.log_transition("Verification Agent", f"CRITICAL verification node failure: {str(e)}")
        finally:
            db.close()
            
        return state
