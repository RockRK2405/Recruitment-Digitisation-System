import json
from sqlalchemy.orm import Session
from database.models import Candidate, JobDescription, MatchResult, Resume, Certification
from services.embeddings.vector_store import VectorStoreService
from config.logging_config import logger
from config.settings import settings

class MatchingEngine:
    """Computes safety-compliant, skill-aware matching scores between JDs and candidates."""
    
    @staticmethod
    def _parse_comma_list(comma_str: str) -> list[str]:
        """Safely parses comma-separated tags into clean list arrays."""
        if not comma_str:
            return []
        return [item.strip().lower() for item in comma_str.split(",") if item.strip()]

    @classmethod
    def compute_match(cls, db: Session, candidate_id: int, job_id: int) -> dict:
        """
        Computes a detailed compliance-aware match score between a candidate and a job.
        
        Returns:
            dict containing score breakdowns, certificate status, and text explanations.
        """
        # 1. Fetch from Database
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
        
        if not candidate or not job:
            raise ValueError(f"Candidate {candidate_id} or Job {job_id} not found in database.")
            
        resume = candidate.resume
        if not resume:
            return {
                "overall_score": 0.0,
                "vector_score": 0.0,
                "skill_score": 0.0,
                "cert_score": 0.0,
                "explanation": "No structured resume text registered for this applicant."
            }

        # 2. Semantic Similarity Score (Vector matching)
        # Search the index for the job description to retrieve this candidate's raw vector score
        vector_score = 0.0
        try:
            # Generate a semantic search term from job description
            search_query = f"{job.title} {job.description}"
            # Fetch semantic scores
            matches = VectorStoreService.search_candidates(search_query, limit=100)
            for m in matches:
                if str(m["id"]) == str(candidate.id) or str(m["id"]) == str(resume.id):
                    # Keep vector score between 0.0 and 1.0
                    vector_score = float(m["score"])
                    break
        except Exception as e:
            logger.error(f"Failed to fetch vector score: {str(e)}")
            vector_score = 0.5 # Neutral fallback

        # 3. Hard Skill Overlap (Rule-based)
        jd_skills = cls._parse_comma_list(job.required_skills)
        candidate_skills = cls._parse_comma_list(resume.skills_list)
        
        matched_skills = []
        missing_skills = []
        skill_score = 1.0 # Default if job has no skills defined
        
        if jd_skills:
            for s in jd_skills:
                # Direct check or soft inclusion check
                if any(s in cs or cs in s for cs in candidate_skills):
                    matched_skills.append(s)
                else:
                    missing_skills.append(s)
            skill_score = len(matched_skills) / len(jd_skills)

        # 4. Mandatory Safety Certification Check (Compliance matching)
        jd_certs = cls._parse_comma_list(job.required_certifications)
        
        # Collect candidate's certifications
        cand_certs = []
        for c in candidate.certifications:
            cand_certs.append(c.name.lower())
            
        matched_certs = []
        missing_certs = []
        cert_score = 1.0 # Default if job has no certificates required
        
        if jd_certs:
            for cert in jd_certs:
                # Rigorous check for license compliance
                if any(cert in cc or cc in cert for cc in cand_certs):
                    matched_certs.append(cert)
                else:
                    missing_certs.append(cert)
            cert_score = len(matched_certs) / len(jd_certs)

        # 5. Compile Weighted Score (0 to 100 scale)
        # Weights: Vector Similarity: 40%, Skills: 30%, Certifications: 30%
        # NOTE: Compliance Penalty: If candidate is missing ALL required safety certificates, we penalize the overall score by 50%!
        w_vector = vector_score * 100.0 * 0.4
        w_skill = skill_score * 100.0 * 0.3
        w_cert = cert_score * 100.0 * 0.3
        
        overall_score = w_vector + w_skill + w_cert
        
        # Penalty block
        has_penalty = False
        if jd_certs and not matched_certs:
            # Strict penalty for zero safety compliance
            overall_score = overall_score * 0.5
            has_penalty = True

        overall_score = round(max(0.0, min(100.0, overall_score)), 1)
        
        # 6. Generate natural language explanation
        explanation = cls.generate_explanation(
            candidate.name,
            job.title,
            overall_score,
            matched_skills,
            missing_skills,
            matched_certs,
            missing_certs,
            has_penalty
        )

        # Calculate dynamic hiring status
        if overall_score >= 40.0:
            hiring_status = "Passed"
            status_color = "#00e676"  # Forest green
        elif overall_score >= 30.0:
            hiring_status = "May Hire"
            status_color = "#ffd700"  # Warning gold
        else:
            hiring_status = "Failed"
            status_color = "#ff1744"  # Caution red

        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate.name,
            "job_id": job_id,
            "job_title": job.title,
            "overall_score": overall_score,
            "hiring_status": hiring_status,
            "hiring_status_color": status_color,
            "vector_score": round(vector_score * 100.0, 1),
            "skill_score": round(skill_score * 100.0, 1),
            "cert_score": round(cert_score * 100.0, 1),
            "matched_skills": [s.title() for s in matched_skills],
            "missing_skills": [s.title() for s in missing_skills],
            "matched_certs": [c.upper() for c in matched_certs],
            "missing_certs": [c.upper() for c in missing_certs],
            "has_compliance_penalty": has_penalty,
            "explanation": explanation
        }

    @classmethod
    def generate_explanation(
        cls, name: str, job_title: str, score: float, 
        matched_skills: list, missing_skills: list, 
        matched_certs: list, missing_certs: list, has_penalty: bool
    ) -> str:
        """Generates a contextual, structured explainability string."""
        summary = (
            f"Candidate {name} has a matching score of {score}% for the {job_title} role. "
        )
        
        # Skill remarks
        if matched_skills:
            summary += f"They possess crucial skills: {', '.join(matched_skills)}. "
        if missing_skills:
            summary += f"However, they lack: {', '.join(missing_skills)}. "
            
        # Certificate compliance remarks
        if matched_certs:
            summary += f"Importantly, their credentials verify the required licenses: {', '.join(matched_certs)}. "
        if missing_certs:
            summary += f"CRITICAL GAPS: They do NOT have the mandatory licenses: {', '.join(missing_certs)}. "
            
        if has_penalty:
            summary += "WARNING: An automatic 50% matching penalty has been applied due to missing safety regulatory certificates."
            
        return summary

    @classmethod
    def rank_candidates_for_job(cls, db: Session, job_id: int, limit: int = 10) -> list[dict]:
        """Computes matching scores for all active candidates in the DB and ranks them."""
        candidates = db.query(Candidate).filter(Candidate.status != "inactive").all()
        ranked = []
        
        for cand in candidates:
            try:
                res = cls.compute_match(db, cand.id, job_id)
                ranked.append(res)
            except Exception as e:
                logger.error(f"Error computing candidate match: {str(e)}")
                
        # Sort by overall score descending
        ranked.sort(key=lambda x: x["overall_score"], reverse=True)
        return ranked[:limit]

    @classmethod
    def recommend_jobs_for_candidate(cls, db: Session, candidate_id: int) -> list[dict]:
        """Ranks all active Job Descriptions in the DB for a specific candidate and recommends best fits."""
        jobs = db.query(JobDescription).all()
        recommendations = []
        
        for job in jobs:
            try:
                res = cls.compute_match(db, candidate_id, job.id)
                recommendations.append(res)
            except Exception as e:
                logger.error(f"Error recommending job match: {str(e)}")
                
        # Sort by overall score descending
        recommendations.sort(key=lambda x: x["overall_score"], reverse=True)
        return recommendations
