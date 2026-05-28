import os
import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.connection import SessionLocal, Base, engine
from database.models import JobDescription, Candidate
from services.agents.orchestrator import AgentOrchestrator
from services.matching.engine import MatchingEngine
from config.logging_config import logger

def seed_job_descriptions():
    """Seeds typical industrial job descriptions if they do not exist."""
    db = SessionLocal()
    try:
        logger.info("Verifying and seeding industrial job descriptions...")
        
        jobs = [
            JobDescription(
                title="DGMS Coal Mining Sirdar",
                description="Responsible for supervising underground or open-cast coal mining shifts, enforcing blasting safety, overseeing shovel operations, and carrying out mandatory gas testing checks in coal faces.",
                required_skills="Shovel operation, Blasting safety, Excavation, Shift management, Gas testing",
                required_certifications="DGMS Gas Testing Certificate, First Aid License",
                location="Dhanbad, Jharkhand",
                experience_years_required=3.0
            ),
            JobDescription(
                title="Software Engineer",
                description="Responsible for maintaing & Creation of Websites & Apps for the Plant",
                required_skills="Frontend , Backend , AI/ML , Database Management, Mobile App Development",
                required_certifications="AWS",
                location="Mumbai, Maharashtra",
                experience_years_required=0.0
            ),
            JobDescription(
                title="Grade-A Boiler Attendant",
                description="Responsible for maintaining steam boiler operations in a high-pressure thermal power plant, monitoring pressure valves, regulating water levels, and ensuring compliance with thermal plant safety protocols.",
                required_skills="Boiler operations, Pressure regulation, Turbine controls, Maintenance",
                required_certifications="Boiler Attendant Grade-1, OSHA Safety",
                location="Raipur, Chhattisgarh",
                experience_years_required=5.0
            ),
            JobDescription(
                title="Heavy Structural Welder",
                description="Performs high-precision MIG, TIG, and Arc welding on heavy steel plate assemblies, structural columns, and pressure vessel enclosures in a metallurgy plant environment.",
                required_skills="TIG welding, Arc welding, Blueprint reading, Metal cutting, Rigging",
                required_certifications="ASME Welder Certificate, Crane Rigging Safety",
                location="Jamshedpur, Jharkhand",
                experience_years_required=2.0
            )
        ]
        
        seeded_count = 0
        for job_data in jobs:
            existing = db.query(JobDescription).filter(JobDescription.title == job_data.title).first()
            if not existing:
                db.add(job_data)
                seeded_count += 1
                logger.info(f"Seeded new Job Description: {job_data.title}")
                
        db.commit()
        logger.info(f"Job descriptions verified. Seeded {seeded_count} new postings.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to seed jobs: {str(e)}")
    finally:
        db.close()

def run_sample_agent_simulation():
    """Creates a mock physical resume scan and runs the agent pipeline to prove execution."""
    logger.info("Initializing Agent Ingestion workflow simulation...")
    
    # 1. Setup mock directories
    mock_dir = Path(__file__).resolve().parent.parent / "data" / "uploads"
    os.makedirs(mock_dir, exist_ok=True)
    
    mock_resume_path = mock_dir / "ramesh_kumar_resume_photo.txt"
    
    # Write a messy mock OCR resume file containing typical industrial profiles
    resume_text = (
        "RAMESH KUMAR (Heavy Excavator Operator)\n"
        "Contact: +91 9876543210 | Email: ramesh.mining.corp@gmail.com\n"
        "Location: Dhanbad, Jharkhand\n"
        "Experience: I have worked for 6 years in coal mines operating heavy excavators.\n"
        "Companies: Dhanbad Contracting Co., Coal India Ltd.\n"
        "Languages: Hindi and a little English.\n"
        "Education: Secondary School (10th standard pass).\n"
        "Skills: Shovel operations, heavy dumpers, digging, drilling, crane safety.\n"
        "Equipment: Komatsu PC2000, CAT 777D Excavator.\n"
        "Licenses: DGMS Gas Testing Certificate issued in 2022, First Aid License.\n"
    )
    
    with open(mock_resume_path, "w") as f:
        f.write(resume_text)
        
    logger.info(f"Sample resume file created at: {mock_resume_path}")
    
    # 2. Trigger Orchestrator workflow
    state = AgentOrchestrator.process_resume(str(mock_resume_path))
    
    # 3. If ingestion succeeded, run a mock job match
    if state.status == "completed" and state.candidate_id:
        db = SessionLocal()
        try:
            logger.info("Executing sample matching score computation...")
            # Fetch the seeded Coal Sirdar Job Description
            sirdar_job = db.query(JobDescription).filter(JobDescription.title == "DGMS Coal Mining Sirdar").first()
            if sirdar_job:
                match = MatchingEngine.compute_match(db, state.candidate_id, sirdar_job.id)
                logger.info(f"--- MATCHING RESULT SIMULATION ---")
                logger.info(f"Candidate: {match['candidate_name']}")
                logger.info(f"Job Role: {match['job_title']}")
                logger.info(f"Overall Match Score: {match['overall_score']}%")
                logger.info(f"Skills Matched: {match['matched_skills']}")
                logger.info(f"Mandatory Certifications Matched: {match['matched_certs']}")
                logger.info(f"Explanation: {match['explanation']}")
                logger.info(f"---------------------------------")
        except Exception as e:
            logger.error(f"Failed matching simulation: {str(e)}")
        finally:
            db.close()

if __name__ == "__main__":
    # Ensure database is active
    Base.metadata.create_all(bind=engine)
    seed_job_descriptions()
    run_sample_agent_simulation()
