"""
Recruiter Review API Routes.

Provides endpoints for:
- Submitting recruiter decisions (accept/reject/hold) on candidate-job matches
- Submitting match quality feedback for scoring improvement
- Managing candidate tags
- Retrieving shortlists and feedback data
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from database.connection import get_db
from database.models import (
    RecruiterDecision, RecruiterFeedback, CandidateTag,
    Candidate, JobDescription
)
from config.logging_config import logger

router = APIRouter()


# ─────────────────────────────────────────────
# REQUEST SCHEMAS
# ─────────────────────────────────────────────

class DecisionRequest(BaseModel):
    candidate_id: int = Field(description="Candidate ID")
    job_id: int = Field(description="Job Description ID")
    decision: str = Field(description="Decision: accepted, rejected, hold, shortlisted")
    notes: Optional[str] = Field(None, description="Recruiter notes")
    recruiter_username: Optional[str] = Field(None, description="Username of the recruiter")


class FeedbackRequest(BaseModel):
    candidate_id: int = Field(description="Candidate ID")
    job_id: int = Field(description="Job Description ID")
    match_quality_rating: int = Field(description="Rating 1-5 stars")
    comment: Optional[str] = Field(None, description="Free-text feedback")
    original_score: Optional[float] = Field(None, description="The system's original match score")
    recruiter_username: Optional[str] = Field(None, description="Username of the recruiter")


class TagRequest(BaseModel):
    candidate_id: int = Field(description="Candidate ID")
    tag: str = Field(description="Tag text (e.g. 'interview scheduled')")
    tagged_by: Optional[str] = Field(None, description="Username of the tagger")


# ─────────────────────────────────────────────
# DECISION ENDPOINTS
# ─────────────────────────────────────────────

@router.post("/decision", summary="Submit recruiter decision on a candidate-job match")
def submit_decision(payload: DecisionRequest, db: Session = Depends(get_db)):
    """Records a recruiter's accept/reject/hold decision for a candidate-job pair."""
    # Validate decision value
    valid_decisions = ["accepted", "rejected", "hold", "shortlisted"]
    if payload.decision not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision '{payload.decision}'. Must be one of: {valid_decisions}"
        )

    # Verify candidate and job exist
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job = db.query(JobDescription).filter(JobDescription.id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job description not found")

    try:
        # Check for existing decision and update, or create new
        existing = db.query(RecruiterDecision).filter(
            RecruiterDecision.candidate_id == payload.candidate_id,
            RecruiterDecision.job_id == payload.job_id
        ).first()

        if existing:
            existing.decision = payload.decision
            existing.notes = payload.notes
            existing.recruiter_username = payload.recruiter_username
            db.commit()
            logger.info(f"Updated decision for candidate {payload.candidate_id} on job {payload.job_id}: {payload.decision}")
            return {"status": "updated", "decision_id": existing.id, "decision": payload.decision}
        else:
            decision = RecruiterDecision(
                candidate_id=payload.candidate_id,
                job_id=payload.job_id,
                decision=payload.decision,
                recruiter_username=payload.recruiter_username,
                notes=payload.notes
            )
            db.add(decision)
            db.commit()
            db.refresh(decision)
            logger.info(f"New decision for candidate {payload.candidate_id} on job {payload.job_id}: {payload.decision}")
            return {"status": "created", "decision_id": decision.id, "decision": payload.decision}
    except Exception as e:
        db.rollback()
        logger.error(f"Decision submission failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save decision: {str(e)}")


# ─────────────────────────────────────────────
# FEEDBACK ENDPOINTS
# ─────────────────────────────────────────────

@router.post("/feedback", summary="Submit match quality feedback for scoring improvement")
def submit_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    """Records recruiter feedback on match quality for adaptive weight adjustment."""
    if payload.match_quality_rating < 1 or payload.match_quality_rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    try:
        feedback = RecruiterFeedback(
            candidate_id=payload.candidate_id,
            job_id=payload.job_id,
            match_quality_rating=payload.match_quality_rating,
            comment=payload.comment,
            original_score=payload.original_score,
            recruiter_username=payload.recruiter_username
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        logger.info(
            f"Feedback recorded for candidate {payload.candidate_id} on job {payload.job_id}: "
            f"{payload.match_quality_rating}/5 stars"
        )
        return {"status": "recorded", "feedback_id": feedback.id}
    except Exception as e:
        db.rollback()
        logger.error(f"Feedback submission failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {str(e)}")


@router.get("/feedback/{job_id}", summary="Get aggregated feedback for a job")
def get_feedback_summary(job_id: int, db: Session = Depends(get_db)):
    """Returns feedback statistics and individual entries for a job."""
    feedbacks = db.query(RecruiterFeedback).filter(
        RecruiterFeedback.job_id == job_id
    ).order_by(RecruiterFeedback.created_at.desc()).all()

    if not feedbacks:
        return {"job_id": job_id, "total_feedback": 0, "average_rating": 0.0, "entries": []}

    avg_rating = sum(f.match_quality_rating for f in feedbacks) / len(feedbacks)

    return {
        "job_id": job_id,
        "total_feedback": len(feedbacks),
        "average_rating": round(avg_rating, 2),
        "entries": [
            {
                "candidate_id": f.candidate_id,
                "rating": f.match_quality_rating,
                "comment": f.comment,
                "original_score": f.original_score,
                "recruiter": f.recruiter_username,
                "created_at": f.created_at
            }
            for f in feedbacks
        ]
    }


# ─────────────────────────────────────────────
# TAG ENDPOINTS
# ─────────────────────────────────────────────

@router.post("/tag", summary="Add a tag to a candidate")
def add_tag(payload: TagRequest, db: Session = Depends(get_db)):
    """Adds a free-form tag to a candidate."""
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        # Check for duplicate tags
        existing = db.query(CandidateTag).filter(
            CandidateTag.candidate_id == payload.candidate_id,
            CandidateTag.tag == payload.tag
        ).first()
        if existing:
            return {"status": "exists", "tag_id": existing.id, "message": "Tag already exists"}

        tag = CandidateTag(
            candidate_id=payload.candidate_id,
            tag=payload.tag,
            tagged_by=payload.tagged_by
        )
        db.add(tag)
        db.commit()
        db.refresh(tag)
        return {"status": "created", "tag_id": tag.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add tag: {str(e)}")


@router.delete("/tag/{tag_id}", summary="Remove a tag from a candidate")
def remove_tag(tag_id: int, db: Session = Depends(get_db)):
    """Removes a tag by its ID."""
    tag = db.query(CandidateTag).filter(CandidateTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()
    return {"status": "deleted", "tag_id": tag_id}


@router.get("/tags/{candidate_id}", summary="Get all tags for a candidate")
def get_candidate_tags(candidate_id: int, db: Session = Depends(get_db)):
    """Returns all tags assigned to a candidate."""
    tags = db.query(CandidateTag).filter(
        CandidateTag.candidate_id == candidate_id
    ).all()
    return {
        "candidate_id": candidate_id,
        "tags": [{"id": t.id, "tag": t.tag, "tagged_by": t.tagged_by, "created_at": t.created_at} for t in tags]
    }


# ─────────────────────────────────────────────
# SHORTLIST ENDPOINTS
# ─────────────────────────────────────────────

@router.get("/shortlist/{job_id}", summary="Get all recruiter decisions for a job")
def get_shortlist(job_id: int, status_filter: Optional[str] = None, db: Session = Depends(get_db)):
    """Returns all recruiter decisions for a specific job, optionally filtered by status."""
    query = db.query(RecruiterDecision).filter(RecruiterDecision.job_id == job_id)
    if status_filter:
        query = query.filter(RecruiterDecision.decision == status_filter)

    decisions = query.order_by(RecruiterDecision.created_at.desc()).all()

    results = []
    for d in decisions:
        candidate = db.query(Candidate).filter(Candidate.id == d.candidate_id).first()
        results.append({
            "decision_id": d.id,
            "candidate_id": d.candidate_id,
            "candidate_name": candidate.name if candidate else "Unknown",
            "decision": d.decision,
            "notes": d.notes,
            "recruiter": d.recruiter_username,
            "created_at": d.created_at
        })

    return {
        "job_id": job_id,
        "total_decisions": len(results),
        "decisions": results
    }
