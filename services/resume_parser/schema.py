"""
Extended Pydantic schemas for Multi-Modal Document Intelligence.

Covers industrial resume profiles, certificate extraction, experience letters,
per-field confidence tracking with provenance, and multi-document aggregation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# CONFIDENCE & PROVENANCE TRACKING
# ─────────────────────────────────────────────

class ExtractedField(BaseModel):
    """Wraps any extracted value with confidence and source provenance."""
    value: Any = Field(description="The extracted value")
    confidence: float = Field(0.0, description="Extraction confidence score (0.0-1.0)")
    source_document: Optional[str] = Field(None, description="Source filename")
    source_page: Optional[int] = Field(None, description="Source page number")
    bounding_box: Optional[List[List[int]]] = Field(None, description="OCR bounding box coordinates [[x1,y1],[x2,y2],...]")
    extraction_method: Optional[str] = Field(None, description="Method used: ocr/vision/llm/heuristic")


# ─────────────────────────────────────────────
# CERTIFICATION MODEL
# ─────────────────────────────────────────────

class ParsedCertification(BaseModel):
    """Pydantic model representing parsed licenses and safety credentials."""
    name: str = Field(description="Name of the certification or license (e.g. DGMS Mining Sirdar, OSHA-10, Heavy Crane Operator)")
    issuer: Optional[str] = Field(None, description="Issuer of the certification (e.g. Ministry of Mines, OSHA, Red Cross)")
    issue_date: Optional[str] = Field(None, description="Issue date if mentioned (e.g. 2022, Oct 2021)")
    expiry_date: Optional[str] = Field(None, description="Expiry date if mentioned")
    registration_number: Optional[str] = Field(None, description="Certificate registration/serial number")
    grade_or_class: Optional[str] = Field(None, description="Grade, class, or score (e.g. First Class, Grade A)")
    verification_status: str = Field("pending", description="Initial verification state (default 'pending')")
    safety_domain: Optional[str] = Field(None, description="Safety domain: mining/electrical/welding/crane/boiler/fire/general")
    is_safety_critical: bool = Field(False, description="Whether this is a mandatory safety certification")
    source_document: Optional[str] = Field(None, description="Source document this was extracted from")
    confidence: float = Field(0.0, description="Extraction confidence for this certification")


# ─────────────────────────────────────────────
# INDUSTRIAL DETAILS MODEL
# ─────────────────────────────────────────────

class IndustrialDetails(BaseModel):
    """Specialized industrial experience data for mining, power, manufacturing sectors."""
    mining_experience: Optional[str] = Field(None, description="Mining experience details (opencast/underground, years)")
    power_plant_experience: Optional[str] = Field(None, description="Power plant experience (thermal/hydro/solar, years)")
    manufacturing_experience: Optional[str] = Field(None, description="Manufacturing/steel/foundry experience")
    safety_certifications: List[str] = Field(default_factory=list, description="List of safety-specific certifications")
    heavy_machinery_operated: List[str] = Field(default_factory=list, description="Heavy machinery & HEMM operated")
    welding_certifications: List[str] = Field(default_factory=list, description="Welding-specific certifications (TIG, ARC, MIG, etc.)")
    crane_operator_certifications: List[str] = Field(default_factory=list, description="Crane/rigging operator certifications")
    boiler_certifications: List[str] = Field(default_factory=list, description="Boiler attendant/operator certifications")
    industrial_training: List[str] = Field(default_factory=list, description="Industrial training programs completed")
    dgms_certificates: List[str] = Field(default_factory=list, description="DGMS-specific certifications")
    shift_experience: Optional[str] = Field(None, description="Shift work experience (rotational/fixed)")


# ─────────────────────────────────────────────
# MAIN RESUME SCHEMA
# ─────────────────────────────────────────────

class IndustrialResumeSchema(BaseModel):
    """Pydantic model representing parsed industrial worker profiles."""
    name: Optional[str] = Field(None, description="Full name of the candidate")
    phone: Optional[str] = Field(None, description="Contact phone number (preferably standardized e.g., +91...)")
    email: Optional[str] = Field(None, description="Contact email address")
    location: Optional[str] = Field(None, description="Current location or home town (e.g. Dhanbad, Jharkhand)")
    address: Optional[str] = Field(None, description="Full address if available")
    
    experience_years: float = Field(0.0, description="Total years of work experience in industrial fields")
    industry_domain: Optional[str] = Field(None, description="Primary industry domain (e.g. Coal Mining, Thermal Power, Steel Manufacturing, Construction, Logistics)")
    
    skills: List[str] = Field(default_factory=list, description="Key skills and techniques (e.g. welding, excavation, rigging, electrical wiring)")
    equipment_handled: List[str] = Field(default_factory=list, description="Heavy equipment or tools operated (e.g. Komatsu PC2000, CAT Dumper, MIG Welder, CNC Milling)")
    safety_certifications: List[str] = Field(default_factory=list, description="List of safety related certifications (e.g. DGMS First Class Sirdar, First Aid, Crane Safety, Scaffold Rigging)")
    
    languages: List[str] = Field(default_factory=list, description="Languages spoken/understood by the candidate (e.g. Hindi, English, Spanish, Telugu, Bengali)")
    education: Optional[str] = Field(None, description="Highest education completed (e.g. 10th Standard Pass, ITI Electrician, Diploma in Mining)")
    availability: Optional[str] = Field(None, description="Candidate availability or notice period (e.g. Immediate, 15 Days, 1 Month)")
    notice_period: Optional[str] = Field(None, description="Notice period at current employer (e.g. Immediate, 15 days, 1 month, 3 months)")
    expected_salary: Optional[str] = Field(None, description="Expected monthly salary in INR or range (e.g. 25000, 30000-40000)")
    
    previous_companies: List[str] = Field(default_factory=list, description="Names of previous employers or contractors")
    certifications: List[ParsedCertification] = Field(default_factory=list, description="Detailed list of parsed certifications")
    
    # Extended industrial details
    industrial_details: Optional[IndustrialDetails] = Field(None, description="Detailed industrial-domain-specific information")


# ─────────────────────────────────────────────
# CERTIFICATE EXTRACTION RESULT
# ─────────────────────────────────────────────

class CertificateExtractionResult(BaseModel):
    """Result from certificate-specific extraction."""
    certificate_name: Optional[str] = Field(None, description="Full certificate title")
    issuer: Optional[str] = Field(None, description="Issuing authority")
    recipient_name: Optional[str] = Field(None, description="Name on the certificate")
    issue_date: Optional[str] = Field(None, description="Date of issue")
    expiry_date: Optional[str] = Field(None, description="Expiry date")
    registration_number: Optional[str] = Field(None, description="Registration/certificate number")
    grade_or_class: Optional[str] = Field(None, description="Grade, class, or score")
    safety_domain: Optional[str] = Field(None, description="Safety domain classification")
    is_safety_critical: bool = Field(False, description="Whether safety-critical")
    additional_details: Optional[str] = Field(None, description="Extra details")
    confidence: float = Field(0.0, description="Overall extraction confidence")
    source_document: Optional[str] = Field(None, description="Source filename")


# ─────────────────────────────────────────────
# EXPERIENCE LETTER EXTRACTION RESULT
# ─────────────────────────────────────────────

class ExperienceLetterResult(BaseModel):
    """Result from experience letter extraction."""
    employee_name: Optional[str] = Field(None, description="Employee name")
    employer_name: Optional[str] = Field(None, description="Company/organization name")
    designation: Optional[str] = Field(None, description="Job title/role")
    department: Optional[str] = Field(None, description="Department")
    start_date: Optional[str] = Field(None, description="Employment start date")
    end_date: Optional[str] = Field(None, description="Employment end date")
    tenure_description: Optional[str] = Field(None, description="Tenure summary")
    reason_for_leaving: Optional[str] = Field(None, description="Reason for leaving")
    conduct_assessment: Optional[str] = Field(None, description="Conduct assessment")
    letter_date: Optional[str] = Field(None, description="Date letter was issued")
    signatory: Optional[str] = Field(None, description="Who signed the letter")
    confidence: float = Field(0.0, description="Overall extraction confidence")
    source_document: Optional[str] = Field(None, description="Source filename")


# ─────────────────────────────────────────────
# MULTI-DOCUMENT AGGREGATED RESULT
# ─────────────────────────────────────────────

class DocumentExtractionResult(BaseModel):
    """Aggregated extraction result from multiple documents."""
    candidate_profile: Optional[IndustrialResumeSchema] = Field(None, description="Merged candidate profile")
    certificates: List[CertificateExtractionResult] = Field(default_factory=list, description="All extracted certificates")
    experience_letters: List[ExperienceLetterResult] = Field(default_factory=list, description="All experience letters")
    document_classifications: List[Dict[str, Any]] = Field(default_factory=list, description="Classification results per document")
    field_confidences: List[ExtractedField] = Field(default_factory=list, description="Per-field confidence tracking")
    total_documents_processed: int = Field(0, description="Number of documents processed")
    overall_confidence: float = Field(0.0, description="Average confidence across all extractions")
    inconsistencies: List[str] = Field(default_factory=list, description="Cross-document inconsistencies detected")
    missing_information: List[str] = Field(default_factory=list, description="Information gaps identified")
