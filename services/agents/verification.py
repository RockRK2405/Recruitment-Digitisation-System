"""
Enhanced Verification Agent for Multi-Modal Document Intelligence.

Cross-references certificate data from OCR text with vision model findings,
checks for consistency across multiple documents, and performs enhanced
certification verification.
"""

import json
from database.connection import SessionLocal
from database.models import Certification, Candidate
from services.agents.state import AgentState
from config.logging_config import logger


class VerificationAgent:
    """Verification Agent Node: Audits certifications, cross-validates documents, checks consistency."""
    
    # Known mandatory safety certifications for industrial domains
    MANDATORY_SAFETY_CERTS = {
        "Mining": ["DGMS", "Gas Testing", "First Aid"],
        "Thermal Power Plant": ["Boiler Attendant", "First Aid"],
        "Steel Plant": ["Fire Safety", "First Aid", "Welding"],
        "Construction": ["Height Safety", "First Aid"],
        "Logistics": ["Driving License", "First Aid"],
    }
    
    @staticmethod
    def execute(state: AgentState) -> AgentState:
        state.current_node = "verification"
        state.log_transition("Verification Agent", "Starting certification and credential verification pipeline...")
        
        if state.status == "failed" or not state.candidate_id:
            state.log_transition("Verification Agent", "Skipping verification due to prior failures.")
            return state
        
        db = SessionLocal()
        
        try:
            candidate = db.query(Candidate).filter(Candidate.id == state.candidate_id).first()
            if not candidate:
                state.log_transition("Verification Agent", "Candidate not found. Skipping verification.")
                db.close()
                return state
            
            # 1. Fetch all certifications for this candidate
            certs = db.query(Certification).filter(
                Certification.candidate_id == state.candidate_id
            ).all()
            
            verified_count = 0
            flagged_count = 0
            
            # 2. Cross-reference with vision model findings
            vision_certs = []
            for vis_result in state.vision_analysis_results.values():
                result_data = vis_result.get("result", {})
                # Certificate verification results
                if vis_result.get("analysis_type") == "certificate_verification":
                    cert_name = result_data.get("certificate_name", "")
                    verification_conf = result_data.get("verification_confidence", 0)
                    concerns = result_data.get("concerns", [])
                    
                    vision_certs.append({
                        "name": cert_name,
                        "confidence": verification_conf,
                        "concerns": concerns,
                        "authenticity_markers": result_data.get("authenticity_markers", {})
                    })
                
                # General extraction results
                extracted = result_data.get("extracted_data", {})
                if extracted.get("certifications"):
                    for vc in extracted["certifications"]:
                        vision_certs.append({"name": vc, "confidence": 0.5, "concerns": []})
            
            # 3. Verify each certification
            for cert in certs:
                verification_notes = []
                
                # Check if vision model found this cert
                vision_match = None
                for vc in vision_certs:
                    if vc["name"] and cert.name.lower() in vc["name"].lower() or vc["name"].lower() in cert.name.lower():
                        vision_match = vc
                        break
                
                if vision_match:
                    # Vision model confirmed the cert
                    if vision_match.get("confidence", 0) > 0.7:
                        cert.verification_status = "verified"
                        verification_notes.append("Visually confirmed by VLM analysis")
                        verified_count += 1
                    else:
                        cert.verification_status = "pending"
                        verification_notes.append(f"VLM confidence low: {vision_match.get('confidence', 0):.1%}")
                    
                    # Check concerns
                    concerns = vision_match.get("concerns", [])
                    if concerns:
                        cert.verification_status = "flagged"
                        verification_notes.extend([f"CONCERN: {c}" for c in concerns])
                        flagged_count += 1
                    
                    # Check authenticity markers
                    markers = vision_match.get("authenticity_markers", {})
                    if markers.get("seal_visible") is False:
                        verification_notes.append("WARNING: No official seal detected")
                    if markers.get("signature_present") is False:
                        verification_notes.append("WARNING: No signature detected")
                else:
                    # No vision confirmation
                    if cert.confidence >= 0.7:
                        cert.verification_status = "verified"
                        verification_notes.append("Verified via OCR text extraction (no visual confirmation)")
                        verified_count += 1
                    else:
                        cert.verification_status = "pending"
                        verification_notes.append("Low confidence extraction. Manual review recommended.")
                
                # Safety-critical flag
                if cert.is_safety_critical:
                    verification_notes.append(f"SAFETY-CRITICAL: {cert.safety_domain or 'general'} domain")
                
                cert.verification_notes = "; ".join(verification_notes)
                
                state.log_transition(
                    "Verification Agent",
                    f"Cert '{cert.name}': {cert.verification_status} | Notes: {cert.verification_notes}"
                )
            
            db.commit()
            
            # 4. Check for mandatory certifications
            domain = state.parsed_profile.get("industry_domain", "") if state.parsed_profile else ""
            mandatory = VerificationAgent.MANDATORY_SAFETY_CERTS.get(domain, [])
            missing_mandatory = []
            
            cert_names_lower = [c.name.lower() for c in certs]
            for req in mandatory:
                found = any(req.lower() in cn for cn in cert_names_lower)
                if not found:
                    missing_mandatory.append(req)
            
            if missing_mandatory:
                state.log_transition(
                    "Verification Agent",
                    f"⚠️ COMPLIANCE GAP: Missing mandatory certifications for {domain}: "
                    f"{', '.join(missing_mandatory)}"
                )
            
            # 5. Cross-document consistency checks
            consistency_issues = []
            
            if state.parsed_profile:
                # Check name consistency across documents
                profile_name = (state.parsed_profile.get("name") or "").lower().strip()
                for vis_result in state.vision_analysis_results.values():
                    extracted = vis_result.get("result", {}).get("extracted_data", {})
                    vis_name = (extracted.get("name") or "").lower().strip()
                    if vis_name and profile_name and vis_name != profile_name:
                        # Check if one contains the other (partial matches are OK)
                        if vis_name not in profile_name and profile_name not in vis_name:
                            consistency_issues.append(
                                f"Name mismatch: OCR='{profile_name}' vs Vision='{vis_name}'"
                            )
            
            if consistency_issues:
                state.log_transition(
                    "Verification Agent",
                    f"Cross-document inconsistencies: {'; '.join(consistency_issues)}"
                )
            
            # Store results
            state.verification_results.update({
                "total_certifications": len(certs),
                "verified_count": verified_count,
                "flagged_count": flagged_count,
                "missing_mandatory": missing_mandatory,
                "consistency_issues": consistency_issues,
                "vision_certs_found": len(vision_certs),
            })
            
            state.log_transition(
                "Verification Agent",
                f"Verification complete: {verified_count}/{len(certs)} verified, "
                f"{flagged_count} flagged, {len(missing_mandatory)} mandatory missing."
            )
            
            # Since this is the final agent in the pipeline, mark status as completed
            state.status = "completed"
            
        except Exception as e:
            state.errors.append(f"Verification error: {str(e)}")
            state.log_transition("Verification Agent", f"WARNING: Verification failed: {str(e)}")
        finally:
            db.close()
        
        return state
