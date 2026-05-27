from database.connection import SessionLocal
from database.models import Candidate, Resume, Certification
from services.resume_parser.parser import ResumeParser
from services.embeddings.vector_store import VectorStoreService
from services.agents.state import AgentState
from config.logging_config import logger

class ScreeningAgent:
    """Screening Agent Node: Orchestrates LLM extraction, database storage, and semantic indexing."""
    
    @staticmethod
    def execute(state: AgentState) -> AgentState:
        state.current_node = "parsing"
        state.log_transition("Screening Agent", "Initializing AI-powered profile parsing and entity extraction...")
        
        if not state.ocr_raw_text or state.status == "failed":
            state.status = "failed"
            state.log_transition("Screening Agent", "Skipping screening node due to failed prior state.")
            return state

        try:
            # 1. Trigger structured parsing
            parsed_profile = ResumeParser.parse_resume(state.ocr_raw_text)
            state.parsed_profile = parsed_profile.model_dump()
            
            state.log_transition(
                "Screening Agent", 
                f"Candidate identity parsed: '{parsed_profile.name}' (Exp: {parsed_profile.experience_years} Yrs, Domain: {parsed_profile.industry_domain})"
            )

            # 2. Open DB Session and store parsed candidate entities
            db = SessionLocal()
            try:
                # Resolve potential low-literacy onboarding status
                # If email is missing or candidate has 10th standard pass or lower, flag for low literacy help
                is_low_literacy = False
                if not parsed_profile.email or any(w in (parsed_profile.education or "").lower() for w in ["10th", "8th", "secondary", "fail"]):
                    is_low_literacy = True
                    state.log_transition("Screening Agent", "Profile marked with 'Low Literacy Assistance' flag due to limited digital trace.")

                # Check for existing candidate profile by email to avoid unique constraint crashes
                cand = None
                if parsed_profile.email:
                    cand = db.query(Candidate).filter(Candidate.email == parsed_profile.email).first()
                    
                if cand:
                    state.log_transition("Screening Agent", f"Found existing candidate profile record (ID: {cand.id}). Re-indexing updated details...")
                    # Update fields dynamically
                    cand.name = parsed_profile.name or cand.name
                    cand.phone = parsed_profile.phone or cand.phone
                    cand.location = parsed_profile.location or cand.location
                    cand.low_literacy_flag = is_low_literacy
                    
                    # Wipe previous resume and certifications to avoid duplicate rows
                    db.query(Resume).filter(Resume.candidate_id == cand.id).delete()
                    db.query(Certification).filter(Certification.candidate_id == cand.id).delete()
                else:
                    # Insert new Candidate Row
                    cand = Candidate(
                        name=parsed_profile.name or "Unnamed Applicant",
                        email=parsed_profile.email,
                        phone=parsed_profile.phone,
                        location=parsed_profile.location,
                        low_literacy_flag=is_low_literacy,
                        status="screening"
                    )
                    db.add(cand)
                    db.commit()
                    db.refresh(cand)
                
                # Insert Resume structured details
                res = Resume(
                    candidate_id=cand.id,
                    uploaded_doc_id=state.verification_results.get("uploaded_doc_id"),
                    raw_text=state.ocr_raw_text,
                    experience_years=parsed_profile.experience_years,
                    skills_list=", ".join(parsed_profile.skills),
                    primary_domain=parsed_profile.industry_domain,
                    equipment_handled=", ".join(parsed_profile.equipment_handled),
                    languages=", ".join(parsed_profile.languages),
                    education=parsed_profile.education,
                    availability=parsed_profile.availability,
                    raw_parsed_json=parsed_profile.model_dump_json()
                )
                db.add(res)
                
                # Insert individual Certifications
                for cert_data in parsed_profile.certifications:
                    cert = Certification(
                        candidate_id=cand.id,
                        name=cert_data.name,
                        issuer=cert_data.issuer,
                        issue_date=cert_data.issue_date,
                        expiry_date=cert_data.expiry_date,
                        verification_status="pending"
                    )
                    db.add(cert)
                
                db.commit()
                
                # Record references in state
                state.candidate_id = cand.id
                state.resume_id = res.id
                state.log_transition("Screening Agent", f"Candidate profile committed to database (Candidate ID: {cand.id})")
                
                # 3. Trigger Semantic Vector Indexing
                state.log_transition("Screening Agent", "Indexing candidate profile in vector search database...")
                
                # Compile a rich indexing text payload
                index_payload = (
                    f"Name: {parsed_profile.name}\n"
                    f"Domain: {parsed_profile.industry_domain}\n"
                    f"Skills: {', '.join(parsed_profile.skills)}\n"
                    f"Equipment: {', '.join(parsed_profile.equipment_handled)}\n"
                    f"Certifications: {', '.join(parsed_profile.safety_certifications)}\n"
                    f"Location: {parsed_profile.location}\n"
                    f"Experience: {parsed_profile.experience_years} years"
                )
                
                # Push to indexer
                VectorStoreService.index_resume(
                    resume_id=cand.id,
                    text=index_payload,
                    metadata={
                        "name": parsed_profile.name or "",
                        "skills": ", ".join(parsed_profile.skills),
                        "domain": parsed_profile.industry_domain or "",
                        "experience_years": parsed_profile.experience_years
                    }
                )
                
                state.log_transition("Screening Agent", "Vector indexing complete. Profile is now searchable.")
                
            except Exception as e:
                db.rollback()
                logger.error(f"Database write transaction failed: {str(e)}")
                state.errors.append(f"DB Transaction error: {str(e)}")
                state.status = "failed"
                state.log_transition("Screening Agent", f"CRITICAL database commit error: {str(e)}")
            finally:
                db.close()
                
        except Exception as e:
            state.status = "failed"
            state.errors.append(str(e))
            state.log_transition("Screening Agent", f"CRITICAL screening node failure: {str(e)}")
            
        return state
