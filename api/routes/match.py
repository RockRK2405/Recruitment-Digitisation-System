from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.connection import get_db
from database.models import Candidate, JobDescription
from services.embeddings.vector_store import VectorStoreService
from services.matching.engine import MatchingEngine
from config.logging_config import logger

router = APIRouter()

# Request Pydantic models
class SemanticSearchQuery(BaseModel):
    query: str
    limit: int = 5

@router.post("/semantic", summary="Search candidates semantically using conversational text")
def semantic_search(payload: SemanticSearchQuery, db: Session = Depends(get_db)):
    """
    Executes a vector search over applicant resumes using the candidate's profile vectors.
    Resolves conversational constraints (e.g., 'heavy excavators', 'welding sirdar').
    """
    try:
        # 1. Run vector lookup
        matches = VectorStoreService.search_candidates(payload.query, limit=payload.limit)
        
        # 2. Look up candidate records from SQL DB to enrich response
        results = []
        for m in matches:
            cid = int(m["id"])
            candidate = db.query(Candidate).filter(Candidate.id == cid).first()
            if candidate:
                resume = candidate.resume
                results.append({
                    "candidate_id": candidate.id,
                    "name": candidate.name,
                    "location": candidate.location,
                    "phone": candidate.phone,
                    "status": candidate.status,
                    "low_literacy_flag": candidate.low_literacy_flag,
                    "vector_similarity_score": round(float(m["score"]) * 100, 1),
                    "primary_domain": resume.primary_domain if resume else None,
                    "experience_years": resume.experience_years if resume else 0.0,
                    "skills": [s.strip() for s in (resume.skills_list or "").split(",") if s.strip()] if resume else []
                })
        return {
            "search_query": payload.query,
            "total_matches": len(results),
            "candidates": results
        }
    except Exception as e:
        logger.error(f"Semantic search route failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/rank/{job_id}", summary="Compute compliance-first rank for all candidates against a JD")
def rank_candidates(job_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """
    Ranks all active candidates against a specific job posting.
    Applies vector scores, skills overlap, and regulatory license compliance audits.
    """
    try:
        # Check if job exists
        job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job description not found.")
            
        rankings = MatchingEngine.rank_candidates_for_job(db, job_id, limit)
        return {
            "job_id": job.id,
            "job_title": job.title,
            "total_scored": len(rankings),
            "rankings": rankings
        }
    except Exception as e:
        logger.error(f"Ranking computation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ranking execution failed: {str(e)}")


@router.get("/score", summary="Get match details for a single candidate against a specific job")
def get_match_score(
    candidate_id: int = Query(..., description="ID of the candidate"),
    job_id: int = Query(..., description="ID of the job description"),
    db: Session = Depends(get_db)
):
    """Computes and explains a detailed matching score between one candidate and one job."""
    try:
        match_details = MatchingEngine.compute_match(db, candidate_id, job_id)
        return match_details
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Detailed score computation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scoring error: {str(e)}")


@router.get("/recommendations/{candidate_id}", summary="Recommend best-fit job descriptions for a candidate")
def recommend_jobs(candidate_id: int, db: Session = Depends(get_db)):
    """
    Ranks all active Job Descriptions in the system for a specific candidate.
    Identifies which vacancy matches their skills and safety credentials.
    """
    try:
        # Check if candidate exists
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found.")
            
        recommendations = MatchingEngine.recommend_jobs_for_candidate(db, candidate_id)
        return {
            "candidate_id": candidate.id,
            "candidate_name": candidate.name,
            "total_jobs_evaluated": len(recommendations),
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Job recommendation computation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendation execution failed: {str(e)}")


class TriggerMatchRequest(BaseModel):
    job_id: int

@router.post("/trigger", summary="Trigger batch match scoring for all candidates against a job")
def trigger_match(payload: TriggerMatchRequest, db: Session = Depends(get_db)):
    """
    Called automatically when a new job is created via the API Gateway.
    Scores all active candidates against the job and persists results to match_results.
    Returns immediately with a count of candidates scored.
    """
    try:
        job = db.query(JobDescription).filter(JobDescription.id == payload.job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {payload.job_id} not found.")

        results = MatchingEngine.rank_candidates_for_job(db, payload.job_id, limit=500)
        logger.info(f"Auto-match trigger: scored {len(results)} candidates for job {payload.job_id}")
        return {
            "job_id": payload.job_id,
            "candidates_scored": len(results),
            "status": "completed"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Match trigger failed for job {payload.job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Match trigger failed: {str(e)}")
