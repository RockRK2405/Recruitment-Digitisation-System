from typing import List, Optional
from pydantic import BaseModel, Field

class ParsedCertification(BaseModel):
    """Pydantic model representing parsed licenses and safety credentials."""
    name: str = Field(description="Name of the certification or license (e.g. DGMS Mining Sirdar, OSHA-10, Heavy Crane Operator)")
    issuer: Optional[str] = Field(None, description="Issuer of the certification (e.g. Ministry of Mines, OSHA, Red Cross)")
    issue_date: Optional[str] = Field(None, description="Issue date if mentioned (e.g. 2022, Oct 2021)")
    expiry_date: Optional[str] = Field(None, description="Expiry date if mentioned")
    verification_status: str = Field("pending", description="Initial verification state (default 'pending')")

class IndustrialResumeSchema(BaseModel):
    """Pydantic model representing parsed industrial worker profiles."""
    name: Optional[str] = Field(None, description="Full name of the candidate")
    phone: Optional[str] = Field(None, description="Contact phone number (preferably standardized e.g., +91...)")
    email: Optional[str] = Field(None, description="Contact email address")
    location: Optional[str] = Field(None, description="Current location or home town (e.g. Dhanbad, Jharkhand)")
    
    experience_years: float = Field(0.0, description="Total years of work experience in industrial fields")
    industry_domain: Optional[str] = Field(None, description="Primary industry domain (e.g. Coal Mining, Thermal Power, Steel Manufacturing, Construction, Logistics)")
    
    skills: List[str] = Field(default_list=[], description="Key skills and techniques (e.g. welding, excavation, rigging, electrical wiring)")
    equipment_handled: List[str] = Field(default_list=[], description="Heavy equipment or tools operated (e.g. Komatsu PC2000, CAT Dumper, MIG Welder, CNC Milling)")
    safety_certifications: List[str] = Field(default_list=[], description="List of safety related certifications (e.g. DGMS First Class Sirdar, First Aid, Crane Safety, Scaffold Rigging)")
    
    languages: List[str] = Field(default_list=[], description="Languages spoken/understood by the candidate (e.g. Hindi, English, Spanish, Telugu, Bengali)")
    education: Optional[str] = Field(None, description="Highest education completed (e.g. 10th Standard Pass, ITI Electrician, Diploma in Mining)")
    availability: Optional[str] = Field(None, description="Candidate availability or notice period (e.g. Immediate, 15 Days, 1 Month)")
    
    previous_companies: List[str] = Field(default_list=[], description="Names of previous employers or contractors")
    certifications: List[ParsedCertification] = Field(default_list=[], description="Detailed list of parsed certifications")
