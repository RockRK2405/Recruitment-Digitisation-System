from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from database.connection import get_db
from database.models import JobDescription
from config.logging_config import logger

router = APIRouter()

# Schema for incoming JD creation requests
class JobDescriptionCreate(BaseModel):
    title: str = Field(description="Job Title (e.g. Excavator Operator, Welder)")
    description: str = Field(description="Full text description of the role")
    required_skills: str = Field(description="Comma-separated required skills (e.g. welding, lathe, rigging)")
    required_certifications: str = Field(description="Comma-separated safety certificates (e.g. DGMS Sirdar, First Aid)")
    location: Optional[str] = Field("Jamshedpur, India", description="Job location")
    experience_years_required: float = Field(2.0, description="Minimum experience required in years")

@router.post("/", summary="Create a new industrial job description")
def create_job_description(payload: JobDescriptionCreate, db: Session = Depends(get_db)):
    """Registers a new job listing with required capabilities and safety credentials."""
    try:
        job = JobDescription(
            title=payload.title,
            description=payload.description,
            required_skills=payload.required_skills,
            required_certifications=payload.required_certifications,
            location=payload.location,
            experience_years_required=payload.experience_years_required
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info(f"Registered new job description ID {job.id}: {job.title}")
        return {"success": True, "job_id": job.id, "title": job.title}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save job description: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database write error: {str(e)}")


@router.get("/", summary="List all registered job listings")
def list_job_descriptions(db: Session = Depends(get_db)):
    """Retrieves all active jobs in the recruitment database."""
    jobs = db.query(JobDescription).order_by(JobDescription.created_at.desc()).all()
    return [
        {
            "id": j.id,
            "title": j.title,
            "description": j.description,
            "required_skills": [s.strip() for s in (j.required_skills or "").split(",") if s.strip()],
            "required_certifications": [c.strip() for c in (j.required_certifications or "").split(",") if c.strip()],
            "location": j.location,
            "experience_years_required": j.experience_years_required,
            "created_at": j.created_at
        }
        for j in jobs
    ]


@router.get("/{job_id}", summary="Retrieve a single job details")
def get_job_description(job_id: int, db: Session = Depends(get_db)):
    """Fetches details of a specific job posting."""
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job description not found.")
        
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "required_skills": [s.strip() for s in (job.required_skills or "").split(",") if s.strip()],
        "required_certifications": [c.strip() for c in (job.required_certifications or "").split(",") if c.strip()],
        "location": job.location,
        "experience_years_required": job.experience_years_required,
        "created_at": job.created_at
    }
