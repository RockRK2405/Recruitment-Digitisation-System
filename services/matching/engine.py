import json
import re
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
    def _is_safety_certification(cls, cert: str) -> bool:
        """Determines if a certification is a mandatory safety/regulatory credential."""
        safety_keywords = [
            "safety", "dgms", "osha", "boiler", "weld", "crane", "rigging", 
            "gas", "first aid", "license", "permit", "operator", "competency", 
            "blasting", "sirdar", "hazard", "attendant", "mining", "first class", "second class"
        ]
        cert_lower = cert.lower().strip()
        return any(kw in cert_lower for kw in safety_keywords)

    @classmethod
    def _evaluate_match_score(cls, requirement: str, parsed_items: list[str], raw_text: str) -> float:
        """
        Evaluates how well a requirement (skill or certification) matches a candidate's profile.
        Returns a score between 0.0 and 1.0:
          - 1.0 (Strong match): Exact match or significant keyword overlap
          - 0.8 (Good match): Substantial keyword match
          - 0.6 (Partial match): Some keyword matches
          - 0.0: No match at all
        """
        req_clean = requirement.lower().strip()
        if not req_clean:
            return 1.0

        # Helper for whole phrase/word boundary matching
        def has_whole_phrase(phrase: str, target: str) -> bool:
            if not phrase or not target:
                return False
            pattern = ""
            if re.match(r"^\w", phrase):
                pattern += r"\b"
            pattern += re.escape(phrase)
            if re.match(r".*\w$", phrase):
                pattern += r"\b"
            return bool(re.search(pattern, target))

        # Helper for token matching with boundary constraints
        def match_token(tok: str, target: str) -> bool:
            tok = tok.lower().strip()
            target = target.lower().strip()
            if not tok or not target:
                return False
            if len(tok) <= 3 or tok.isdigit():
                pattern = ""
                if re.match(r"^\w", tok):
                    pattern += r"\b"
                pattern += re.escape(tok)
                if re.match(r".*\w$", tok):
                    pattern += r"\b"
                return bool(re.search(pattern, target))
            else:
                esc_tok = re.escape(tok)
                if re.search(rf"\b{esc_tok}", target) or re.search(rf"{esc_tok}\b", target):
                    return True
                # Reverse match: check if target contains tok as word-boundary prefix/suffix
                # Ensure t_word is at least 4 characters to prevent tiny character false-positives (like 'b' or 'a')
                for t_word in re.split(r"\W+", target):
                    if not t_word or len(t_word) < 4:
                        continue
                    esc_t = re.escape(t_word)
                    if re.search(rf"\b{esc_t}", tok) or re.search(rf"{esc_t}\b", tok):
                        return True
                return False

        # 1. Exact/Whole-phrase Match (Strong match)
        # Check parsed items
        in_parsed_exact = any(
            has_whole_phrase(req_clean, item.lower()) or has_whole_phrase(item.lower(), req_clean)
            for item in parsed_items
        )
        # Check raw text
        in_raw_exact = has_whole_phrase(req_clean, raw_text.lower())
        
        if in_parsed_exact or in_raw_exact:
            return 1.0

        # 2. Tokenized Keyword Match
        stopwords = {
            "and", "or", "of", "in", "for", "with", "a", "an", "the", 
            "certificate", "license", "cert", "holder", "training", "course", 
            "management", "operation", "operations", "safety", "supervision"
        }
        
        # Split terms and clean up punctuation
        delimiters = r"[\s\-\/]+"
        req_words = [
            w.strip() for w in re.split(delimiters, req_clean) 
            if w.strip() and w.strip() not in stopwords
        ]
        
        # If all words were stopwords, fallback to all words
        if not req_words:
            req_words = [w.strip() for w in re.split(delimiters, req_clean) if w.strip()]
            
        if not req_words:
            return 0.0
            
        matched_words = []
        for word in req_words:
            # Check parsed items
            in_parsed = any(match_token(word, item.lower()) for item in parsed_items)
            # Check raw text
            in_raw = match_token(word, raw_text.lower())
            if in_parsed or in_raw:
                matched_words.append(word)
                
        if matched_words:
            match_ratio = len(matched_words) / len(req_words)
            if match_ratio >= 0.8:
                return 1.0  # Strong match for high overlap
            elif match_ratio >= 0.5:
                return 0.8  # Good match
            else:
                return 0.6  # Partial match
                
        return 0.0

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
        # Directly compute similarity using embeddings for accuracy
        vector_score = 0.0
        try:
            job_text = f"{job.title} {job.description}"
            resume_text = resume.raw_text or ""
            if resume_text.strip():
                from services.embeddings.model import EmbeddingModel
                import numpy as np
                job_vec = np.array(EmbeddingModel.embed_query(job_text))
                resume_vec = np.array(EmbeddingModel.embed_text(resume_text))
                
                # Compute cosine similarity
                jn = np.linalg.norm(job_vec)
                rn = np.linalg.norm(resume_vec)
                if jn > 0 and rn > 0:
                    similarity = float(np.dot(job_vec, resume_vec) / (jn * rn))
                    # Cosine similarity of e5 model can be in [-1, 1], map/clip to [0.0, 1.0]
                    similarity = max(0.0, min(1.0, similarity))
                    # Calibrate / scale vector similarity using linear range [0.70, 0.85] to map to [0.0, 1.0]
                    vector_score = max(0.0, min(1.0, (similarity - 0.70) / 0.15))
        except Exception as e:
            logger.error(f"Failed to compute direct vector score: {str(e)}")
            vector_score = 0.5  # Neutral fallback

        # 3. Hard Skill Overlap (Tiered keyword matching)
        jd_skills = cls._parse_comma_list(job.required_skills)
        candidate_skills = cls._parse_comma_list(resume.skills_list)
        raw_text = resume.raw_text or ""
        
        matched_skills = []
        missing_skills = []
        skill_score = 1.0 # Default if job has no skills defined
        
        if jd_skills:
            skill_scores = []
            for s in jd_skills:
                match_val = cls._evaluate_match_score(s, candidate_skills, raw_text)
                skill_scores.append(match_val)
                if match_val >= 1.0:
                    matched_skills.append(s)
                elif match_val >= 0.5:
                    matched_skills.append(f"{s} (Partial)")
                else:
                    missing_skills.append(s)
            skill_score = sum(skill_scores) / len(jd_skills)

        # 4. Mandatory Safety Certification Check (Compliance matching)
        jd_certs = cls._parse_comma_list(job.required_certifications)
        cand_certs = [c.name.lower() for c in candidate.certifications]
        
        matched_certs = []
        missing_certs = []
        cert_score = 1.0 # Default if job has no certificates required
        
        if jd_certs:
            cert_scores = []
            for cert in jd_certs:
                match_val = cls._evaluate_match_score(cert, cand_certs, raw_text)
                cert_scores.append(match_val)
                if match_val >= 0.5:
                    if match_val >= 1.0:
                        matched_certs.append(cert)
                    else:
                        matched_certs.append(f"{cert} (Partial)")
                else:
                    missing_certs.append(cert)
            cert_score = sum(cert_scores) / len(jd_certs)

        # 5. Compile Weighted Score (0 to 100 scale)
        # Base weights: Vector Similarity: 30%, Skills: 40%, Certifications: 30%
        # Adaptive weights from recruiter feedback may override these
        weights = cls.get_adjusted_weights(db, job.id)
        # NOTE: Compliance Penalty: If candidate is missing ALL required safety certificates, we penalize the overall score by 50%!
        w_vector = vector_score * 100.0 * weights[0]
        w_skill = skill_score * 100.0 * weights[1]
        w_cert = cert_score * 100.0 * weights[2]
        
        overall_score = w_vector + w_skill + w_cert
        
        # Penalty block: Only apply the 50% penalty if the job has required safety/compliance certifications
        # and the candidate has zero matches on those safety-critical credentials.
        has_penalty = False
        required_safety_certs = [cert for cert in jd_certs if cls._is_safety_certification(cert)]
        if required_safety_certs:
            # Check if any required safety certs scored >= 0.6
            matched_safety_certs = []
            for cert in required_safety_certs:
                match_val = cls._evaluate_match_score(cert, cand_certs, raw_text)
                if match_val >= 0.6:
                    matched_safety_certs.append(cert)
            
            if not matched_safety_certs:
                # Apply 50% compliance penalty
                overall_score = overall_score * 0.5  # 50% penalty as specified in manual
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
        if overall_score >= 80.0:
            hiring_status = "Passed"
            status_color = "#00e676"  # Forest green
        elif overall_score >= 60.0:
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

    @classmethod
    def get_adjusted_weights(cls, db: Session, job_id: int) -> tuple:
        """
        Returns adaptive scoring weights based on recruiter feedback for this job.
        
        Logic:
        - If recruiters consistently rate high-scoring matches poorly (< 3 stars),
          reduce vector weight and increase skill weight.
        - If recruiters rate low-scoring matches highly (>= 4 stars),
          increase vector weight (semantic understanding is capturing something keywords miss).
        - Default: (0.3, 0.4, 0.3) — vector, skill, cert
        
        Returns:
            tuple: (w_vector, w_skill, w_cert) that sum to 1.0
        """
        default_weights = (0.3, 0.4, 0.3)
        
        try:
            from database.models import RecruiterFeedback
            
            feedbacks = db.query(RecruiterFeedback).filter(
                RecruiterFeedback.job_id == job_id
            ).all()
            
            if len(feedbacks) < 3:
                # Not enough feedback to adjust
                return default_weights
            
            # Analyze feedback patterns
            high_score_low_rating = 0  # System scored high but recruiter rated poorly
            low_score_high_rating = 0  # System scored low but recruiter rated highly
            total = len(feedbacks)
            
            for fb in feedbacks:
                if fb.original_score and fb.original_score >= 70 and fb.match_quality_rating <= 2:
                    high_score_low_rating += 1
                elif fb.original_score and fb.original_score < 50 and fb.match_quality_rating >= 4:
                    low_score_high_rating += 1
            
            w_vector, w_skill, w_cert = 0.3, 0.4, 0.3
            
            # If system overvalues matches (> 30% of feedback says bad match on high scores)
            if high_score_low_rating / total > 0.3:
                # Reduce vector (semantic may be misleading), increase skill
                w_vector = 0.20
                w_skill = 0.50
                w_cert = 0.30
                logger.info(f"Adaptive weights for job {job_id}: Reduced vector weight due to feedback")
            
            # If system undervalues matches
            elif low_score_high_rating / total > 0.3:
                # Increase vector (semantic is catching things keywords miss)
                w_vector = 0.40
                w_skill = 0.30
                w_cert = 0.30
                logger.info(f"Adaptive weights for job {job_id}: Increased vector weight due to feedback")
            
            return (w_vector, w_skill, w_cert)
            
        except Exception as e:
            logger.warning(f"Feedback weight adjustment failed: {str(e)}. Using defaults.")
            return default_weights
