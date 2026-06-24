"""
Enhanced Screening Agent for Multi-Modal Document Intelligence.

Accepts multi-document extraction results, merges profiles from multiple documents,
indexes all document types into vector store, and handles document-type-specific parsing.
"""

import json
from database.connection import SessionLocal
from database.models import Candidate, Resume, UploadedDocument, Certification
from services.agents.state import AgentState
from services.resume_parser.parser import ResumeParser
from services.resume_parser.schema import CertificateExtractionResult, ExperienceLetterResult
from services.embeddings.vector_store import VectorStoreService
from services.document_intelligence.confidence_engine import ConfidenceEngine
from config.logging_config import logger


class ScreeningAgent:
    """Screening Agent Node: LLM entity extraction, multi-document merging, and database storage."""
    
    @staticmethod
    def execute(state: AgentState) -> AgentState:
        state.current_node = "screening"
        state.log_transition("Screening Agent", "Starting multi-document screening and extraction pipeline...")
        
        if state.status == "failed":
            state.log_transition("Screening Agent", "Skipping screening due to prior failures.")
            return state
        
        db = SessionLocal()
        
        try:
            # 1. Route documents to appropriate parsers based on classification
            resume_texts = []
            certificate_results = []
            experience_letter_results = []
            
            classifications = state.document_classifications or {}
            per_file_results = state.per_file_ocr_results or {}
            
            # If no classifications, treat everything as resume (backward compat)
            if not classifications and state.ocr_raw_text:
                resume_texts.append(state.ocr_raw_text)
            else:
                for file_path, ocr_data in per_file_results.items():
                    text = ocr_data.get("text", "")
                    if not text.strip():
                        continue
                    
                    doc_type = classifications.get(file_path, {}).get("doc_type", "resume")
                    filename = ocr_data.get("filename", file_path)
                    
                    if doc_type == "resume" or doc_type == "unknown":
                        resume_texts.append(text)
                    elif doc_type == "certificate":
                        cert_result = ResumeParser.parse_certificate(text, source_filename=filename)
                        certificate_results.append(cert_result)
                        state.log_transition(
                            "Screening Agent",
                            f"Parsed certificate: {cert_result.certificate_name or 'Unknown'} "
                            f"(confidence: {cert_result.confidence:.1%})"
                        )
                    elif doc_type == "experience_letter":
                        letter_result = ResumeParser.parse_experience_letter(text, source_filename=filename)
                        experience_letter_results.append(letter_result)
                        state.log_transition(
                            "Screening Agent",
                            f"Parsed experience letter: {letter_result.employer_name or 'Unknown employer'}"
                        )
                    elif doc_type == "training_record":
                        # Training records are parsed like certificates
                        cert_result = ResumeParser.parse_certificate(text, source_filename=filename)
                        cert_result.is_safety_critical = True
                        certificate_results.append(cert_result)

            # 2. Parse resume text(s)
            combined_resume_text = "\n\n".join(resume_texts)
            resume_data = None
            
            if combined_resume_text.strip():
                state.log_transition("Screening Agent", "Running LLM-assisted resume entity extraction...")
                resume_data = ResumeParser.parse_resume(combined_resume_text)
                state.log_transition(
                    "Screening Agent",
                    f"Resume parsed: {resume_data.name} | {resume_data.experience_years} yrs exp | "
                    f"Domain: {resume_data.industry_domain} | "
                    f"Skills: {len(resume_data.skills)} | Certs: {len(resume_data.certifications)}"
                )
            
            # 3. Merge multi-document profiles
            if certificate_results or experience_letter_results:
                state.log_transition(
                    "Screening Agent",
                    f"Merging data from {len(certificate_results)} certificates and "
                    f"{len(experience_letter_results)} experience letters..."
                )
                resume_data = ResumeParser.merge_multi_document_profiles(
                    resume_data=resume_data,
                    certificates=certificate_results,
                    experience_letters=experience_letter_results
                )
            
            if not resume_data:
                state.status = "failed"
                state.errors.append("No parseable data extracted from any document.")
                state.log_transition("Screening Agent", "CRITICAL: No extractable data found.")
                db.close()
                return state

            # Store parsed profile in state
            state.parsed_profile = json.loads(ResumeParser.serialize_parsed_data(resume_data))
            
            # 4. Create/Update database records
            # Sanitize email field: ensure empty strings are treated as None to avoid unique constraint violations
            candidate_email = resume_data.email.strip() if (resume_data.email and resume_data.email.strip()) else None
            
            candidate = None
            if candidate_email:
                candidate = db.query(Candidate).filter(Candidate.email == candidate_email).first()
            
            if not candidate:
                candidate = Candidate(
                    name=resume_data.name,
                    email=candidate_email,
                    phone=resume_data.phone,
                    location=resume_data.location,
                    address=resume_data.address,
                    status="onboarded",
                    low_literacy_flag=(
                        resume_data.education is not None and 
                        any(kw in (resume_data.education or "").lower() for kw in ["standard", "pass", "8th", "10th", "iti"])
                    ),
                    profile_completeness=0.0
                )
                db.add(candidate)
                db.commit()
                db.refresh(candidate)
                state.log_transition(
                    "Screening Agent",
                    f"New candidate created: {candidate.name} (ID: {candidate.id})"
                )
            else:
                # Update existing candidate with new info
                if resume_data.name and not candidate.name:
                    candidate.name = resume_data.name
                if resume_data.phone and not candidate.phone:
                    candidate.phone = resume_data.phone
                if resume_data.address and not candidate.address:
                    candidate.address = resume_data.address
                db.commit()
                state.log_transition(
                    "Screening Agent",
                    f"Existing candidate updated: {candidate.name} (ID: {candidate.id})"
                )
            
            state.candidate_id = candidate.id
            
            # 5. Create Resume record
            industrial_json = None
            if resume_data.industrial_details:
                industrial_json = resume_data.industrial_details.model_dump_json()
            
            doc_id = state.verification_results.get("uploaded_doc_id")
            
            resume = Resume(
                candidate_id=candidate.id,
                uploaded_doc_id=doc_id,
                raw_text=combined_resume_text[:10000],  # Truncate for DB storage
                experience_years=resume_data.experience_years,
                skills_list=", ".join(resume_data.skills),
                primary_domain=resume_data.industry_domain,
                equipment_handled=", ".join(resume_data.equipment_handled),
                languages=", ".join(resume_data.languages),
                education=resume_data.education,
                availability=resume_data.availability,
                raw_parsed_json=ResumeParser.serialize_parsed_data(resume_data),
                industrial_details_json=industrial_json
            )
            db.add(resume)
            db.commit()
            db.refresh(resume)
            state.resume_id = resume.id
            
            # 6. Save certifications
            for cert in resume_data.certifications:
                db_cert = Certification(
                    candidate_id=candidate.id,
                    name=cert.name,
                    issuer=cert.issuer,
                    issue_date=cert.issue_date,
                    expiry_date=cert.expiry_date,
                    registration_number=cert.registration_number,
                    grade_or_class=cert.grade_or_class,
                    safety_domain=cert.safety_domain,
                    is_safety_critical=cert.is_safety_critical,
                    verification_status="pending",
                    confidence=cert.confidence,
                    source_document_id=doc_id,
                    raw_parsed_data=cert.model_dump_json()
                )
                db.add(db_cert)
            db.commit()
            
            # 7. Calculate and update profile completeness
            profile_fields = [
                resume_data.name, resume_data.phone, resume_data.email,
                resume_data.location, resume_data.education,
                bool(resume_data.skills), bool(resume_data.certifications),
                resume_data.experience_years > 0, resume_data.industry_domain,
            ]
            completeness = sum(1 for f in profile_fields if f) / len(profile_fields)
            candidate.profile_completeness = round(completeness, 2)
            
            # 7b. Confidence-based routing: auto-accept vs needs-review
            from config.settings import settings
            confidence_threshold = settings.FIELD_CONFIDENCE_THRESHOLD
            
            if state.ocr_confidence < confidence_threshold or completeness < 0.5:
                candidate.status = "needs_review"
                routing_reason = []
                if state.ocr_confidence < confidence_threshold:
                    routing_reason.append(f"OCR confidence {state.ocr_confidence:.1%} < threshold {confidence_threshold:.1%}")
                if completeness < 0.5:
                    routing_reason.append(f"Profile completeness {completeness:.0%} < 50%")
                state.log_transition(
                    "Screening Agent",
                    f"⚠️ ROUTING: Candidate marked for HUMAN REVIEW. Reasons: {'; '.join(routing_reason)}"
                )
            else:
                candidate.status = "auto_accepted"
                state.log_transition(
                    "Screening Agent",
                    f"✅ ROUTING: Candidate AUTO-ACCEPTED. OCR confidence: {state.ocr_confidence:.1%}, "
                    f"Profile completeness: {completeness:.0%}"
                )
            
            db.commit()
            
            # 8. Track extraction confidence
            try:
                ConfidenceEngine.track_extraction_batch(
                    db=db,
                    candidate_id=candidate.id,
                    document_id=doc_id,
                    fields={
                        "name": resume_data.name,
                        "phone": resume_data.phone,
                        "email": resume_data.email,
                        "location": resume_data.location,
                        "experience_years": resume_data.experience_years,
                        "industry_domain": resume_data.industry_domain,
                        "education": resume_data.education,
                    },
                    confidence=state.ocr_confidence,
                    extraction_method="llm"
                )
            except Exception as e:
                logger.warning(f"Confidence tracking failed: {str(e)}")
            
            # 9. Index all document texts into vector store
            try:
                all_texts = [r.get("text", "") for r in state.per_file_ocr_results.values() if r.get("text")]
                combined_for_vector = "\n".join(all_texts) if all_texts else combined_resume_text
                
                VectorStoreService.add_to_collection(
                    doc_id=str(doc_id or resume.id),
                    text=combined_for_vector,
                    metadata={
                        "candidate_id": candidate.id,
                        "candidate_name": resume_data.name,
                        "primary_domain": resume_data.industry_domain,
                        "total_documents": len(state.per_file_ocr_results) or 1,
                    }
                )
                state.log_transition("Screening Agent", "All document texts indexed into vector store.")
            except Exception as e:
                logger.warning(f"Vector store indexing failed: {str(e)}")
                state.log_transition("Screening Agent", f"WARNING: Vector indexing failed: {str(e)}")
            
            state.log_transition(
                "Screening Agent",
                f"Screening complete. Candidate: {candidate.name} (ID: {candidate.id}) | "
                f"Profile completeness: {completeness*100:.0f}% | "
                f"Certs: {len(resume_data.certifications)} | "
                f"Skills: {len(resume_data.skills)}"
            )
            
        except Exception as e:
            state.status = "failed"
            state.errors.append(f"Screening error: {str(e)}")
            state.log_transition("Screening Agent", f"CRITICAL FAILURE: {str(e)}")
        finally:
            db.close()
        
        return state
