"""
Enhanced LLM-Assisted Resume and Document Parser.

Supports:
- Resume text extraction (Ollama/Gemini with regex fallback)
- Certificate-specific extraction
- Experience letter extraction
- Multi-document profile merging
"""

import json
import re
import requests
from typing import Optional, List
from config.settings import settings
from config.logging_config import logger
from services.resume_parser.schema import (
    IndustrialResumeSchema, ParsedCertification, IndustrialDetails,
    CertificateExtractionResult, ExperienceLetterResult
)
from services.resume_parser.prompts import (
    RESUME_PARSING_SYSTEM_PROMPT,
    CERTIFICATE_EXTRACTION_PROMPT,
    EXPERIENCE_LETTER_EXTRACTION_PROMPT,
    JD_PARSING_PROMPT,
)


class ResumeParser:
    """Executes LLM-assisted structural entity extraction from raw document text."""
    
    # ─────────────────────────────────────────────
    # HEURISTIC REGEX PARSER (Offline fallback)
    # ─────────────────────────────────────────────
    @classmethod
    def _parse_heuristically(cls, text: str) -> IndustrialResumeSchema:
        """
        Regex-based rule heuristic parser. Runs if LLM API is offline or key is missing.
        Extremely reliable for keeping local testing alive without any network cost.
        """
        logger.warning("Running heuristic regex-based resume parser fallback...")
        
        # 1. Extractor helpers
        phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text)
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        
        phone = phone_match.group(0).strip() if phone_match else ""
        if len(phone) == 10 and not phone.startswith("+"):
            phone = "+91" + phone
            
        email = email_match.group(0).lower().strip() if email_match else ""
        
        # Helper for strict regex-based word boundary keyword checking
        def has_kw(kw: str) -> bool:
            kw_clean = kw.lower().strip()
            if not kw_clean:
                return False
            pattern = re.escape(kw_clean)
            if kw_clean[0].isalnum():
                pattern = r'\b' + pattern
            if kw_clean[-1].isalnum():
                pattern = pattern + r'\b'
            try:
                return bool(re.search(pattern, text.lower()))
            except Exception:
                return kw_clean in text.lower()
        
        # 2. Extract Name (often first lines)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        name = "Unknown Worker"
        if lines:
            found_name = False
            for l in lines[:5]:
                bold_match = re.search(r'\*\*(.*?)\*\*', l)
                if bold_match:
                    possible_name = bold_match.group(1).strip()
                    if len(possible_name) > 2 and not any(char.isdigit() for char in possible_name) and "@" not in possible_name:
                        name = possible_name
                        found_name = True
                        break
            
            if not found_name:
                for l in lines[:5]:
                    l_clean = l.lower().strip()
                    if l_clean in ["resume", "curriculum vitae", "cv", "biodata", "profile", "contact info", "personal details", "name:", "name"]:
                        continue
                    if l.startswith("#"):
                        continue
                    if any(char.isdigit() for char in l):
                        prefix = re.split(r'\d', l)[0].strip().strip("*_-, ")
                        if len(prefix.split()) >= 2 and not any(char.isdigit() for char in prefix) and "@" not in prefix:
                            name = prefix
                            break
                        continue
                    if "@" not in l and len(l) > 3:
                        name = l.strip("*_ ")
                        break
        
        # 3. Detect domains & experience
        exp_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:years|yrs|year)\b', text, re.IGNORECASE)
        experience = float(exp_match.group(1)) if exp_match else 1.0
        
        domain = "Industrial"
        if any(has_kw(w) for w in ["mine", "mining", "coal", "dgms"]):
            domain = "Mining"
        elif any(has_kw(w) for w in ["power", "boiler", "turbine", "thermal"]):
            domain = "Thermal Power Plant"
        elif any(has_kw(w) for w in ["steel", "furnace", "foundry", "welder"]):
            domain = "Steel Plant"
        elif any(has_kw(w) for w in ["warehouse", "forklift", "dumper", "driver"]):
            domain = "Logistics"
        elif any(has_kw(w) for w in ["ca", "icai", "accountant", "finance", "audit", "tax", "taxation", "tds", "gst", "chartered accountant"]):
            domain = "Finance & Compliance"
        elif any(has_kw(w) for w in ["developer", "software", "coder", "aws", "react", "programming", "backend", "frontend"]):
            domain = "Software Engineering"
            
        # 4. Extract Location & Address
        location = "Dhanbad, Jharkhand"
        address = None
        for city in ["Dhanbad", "Ranchi", "Bhilai", "Jamshedpur", "Pune", "Mumbai", "Delhi", "Raipur", "Bangalore", "Bokaro", "Korba", "Singrauli"]:
            if has_kw(city):
                location = f"{city}, India"
                break
        
        # Try to find address
        addr_match = re.search(r'(?:address|addr|residence)[\s:]*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if addr_match:
            address = addr_match.group(1).strip()
                
        # 5. Keywords mapping for skills
        skills = []
        equipment = []
        safety = []
        
        keyword_skills = {
            "shovel": "Shovel Operation", "blasting safety": "Blasting Safety",
            "blasting": "Blasting Safety", "excavation": "Excavation",
            "shift management": "Shift Management", "gas testing": "Gas Testing",
            "frontend": "Frontend Development", "backend": "Backend Development",
            "ai/ml": "AI/ML", "database": "Database Management",
            "sql": "Database Management", "mobile": "Mobile App Development",
            "boiler": "Boiler Operations", "pressure regulation": "Pressure Regulation",
            "turbine": "Turbine Controls", "maintenance": "Maintenance",
            "tig": "TIG Welding", "arc welding": "Arc Welding",
            "welding": "Welding", "blueprint": "Blueprint Reading",
            "metal cutting": "Metal Cutting", "rigging": "Rigging",
            "fitter": "Mechanical Fitting", "electrical": "Electrical Wiring",
            "drilling": "Blasting & Drilling", "haulage": "Heavy Hauling",
            "crane": "Crane Operation", "forklift": "Forklift Operation",
            "grinding": "Grinding", "plumbing": "Plumbing",
            "scaffolding": "Scaffolding", "painting": "Industrial Painting",
        }
        for kw, skill in keyword_skills.items():
            if has_kw(kw):
                skills.append(skill)
                
        keyword_equip = {
            "excavator": "Hydraulic Excavator", "crane": "Mobile Gantry Crane",
            "dumper": "CAT Dumper", "komatsu": "Komatsu Excavator",
            "lathe": "Metal Lathe Machine", "bulldozer": "Bulldozer",
            "loader": "Front-End Loader", "drill rig": "Drill Rig",
            "compressor": "Air Compressor", "generator": "Generator Set",
        }
        for kw, eq in keyword_equip.items():
            if has_kw(kw):
                equipment.append(eq)
                
        keyword_safety = {
            "dgms gas testing": "DGMS Gas Testing Certificate",
            "dgms sirdar": "DGMS Mining Sirdar Certificate",
            "first aid": "First Aid License",
            "dgms safety": "DGMS Safety Certificate",
            "dgms": "DGMS Safety Certificate",
            "osha safety": "OSHA Safety Standard",
            "osha": "OSHA Safety Standard",
            "boiler attendant grade-1": "Boiler Attendant Grade-1 License",
            "boiler attendant": "Boiler Attendant License",
            "asme welder": "ASME Welder Certificate",
            "crane rigging safety": "Crane Rigging Safety License",
            "fire safety": "Fire Safety License",
            "confined space": "Confined Space Entry Certificate",
            "height work": "Work at Height Certificate",
        }
        for kw, sf in keyword_safety.items():
            if has_kw(kw):
                safety.append(sf)
                
        # Languages
        languages = ["Hindi"]
        for lang_name in ["english", "marathi", "telugu", "bengali", "tamil", "kannada", "gujarati", "punjabi"]:
            if has_kw(lang_name):
                languages.append(lang_name.title())
            
        # Certifications
        certs = []
        for s_cert in safety:
            issuer = "Government Authority"
            safety_domain = "general"
            if "dgms" in s_cert.lower():
                issuer = "DGMS, Ministry of Mines"
                safety_domain = "mining"
            elif "osha" in s_cert.lower():
                issuer = "OSHA"
            elif "first aid" in s_cert.lower():
                issuer = "Red Cross / St John"
                safety_domain = "general"
            elif "boiler" in s_cert.lower():
                issuer = "Boiler Inspectorate"
                safety_domain = "boiler"
            elif "crane" in s_cert.lower():
                issuer = "Factories Inspectorate"
                safety_domain = "crane"
            elif "weld" in s_cert.lower():
                issuer = "ASME/AWS"
                safety_domain = "welding"
            elif "fire" in s_cert.lower():
                safety_domain = "fire"
                
            certs.append(
                ParsedCertification(
                    name=s_cert, issuer=issuer,
                    issue_date="2023", expiry_date="2028",
                    safety_domain=safety_domain,
                    is_safety_critical=True,
                    confidence=0.6
                )
            )

        # Education
        education = "Secondary School"
        if has_kw("iti"):
            education = "ITI Technical Pass"
        elif has_kw("ca") or has_kw("icai") or has_kw("chartered accountant"):
            education = "Chartered Accountant (CA)"
        elif has_kw("b.com") or has_kw("bcom") or has_kw("degree") or has_kw("graduate"):
            education = "University Graduate"
        elif has_kw("diploma"):
            education = "Diploma"
        elif has_kw("b.tech") or has_kw("btech") or has_kw("b.e."):
            education = "Engineering Graduate"

        # Industrial details
        industrial = IndustrialDetails(
            mining_experience=f"{experience} years" if domain == "Mining" else None,
            power_plant_experience=f"{experience} years" if domain == "Thermal Power Plant" else None,
            safety_certifications=safety,
            heavy_machinery_operated=equipment,
            dgms_certificates=[c for c in safety if "dgms" in c.lower()],
            welding_certifications=[c for c in safety if "weld" in c.lower()],
            crane_operator_certifications=[c for c in safety if "crane" in c.lower()],
            boiler_certifications=[c for c in safety if "boiler" in c.lower()],
        )

        # Notice period extraction
        notice_period = None
        notice_match = re.search(
            r'(?:notice\s*period|joining\s*time)[:\s]*([\w\s]+?)(?:\.|,|\n|$)',
            text, re.IGNORECASE
        )
        if notice_match:
            notice_period = notice_match.group(1).strip()
        elif has_kw("immediate") or has_kw("immediately"):
            notice_period = "Immediate"

        # Expected salary extraction
        expected_salary = None
        salary_match = re.search(
            r'(?:expected|desired|salary|ctc|compensation)[:\s]*(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\s*[-–to]+\s*[\d,]+)?)',
            text, re.IGNORECASE
        )
        if salary_match:
            expected_salary = salary_match.group(1).replace(',', '').strip()

        return IndustrialResumeSchema(
            name=name, phone=phone, email=email,
            location=location, address=address,
            experience_years=experience, industry_domain=domain,
            skills=skills if skills else ["General Labor"],
            equipment_handled=equipment if equipment else ["Hand Tools"],
            safety_certifications=safety,
            languages=languages, education=education,
            availability="Immediate",
            notice_period=notice_period,
            expected_salary=expected_salary,
            previous_companies=["Industrial Contracting Inc."],
            certifications=certs,
            industrial_details=industrial
        )

    # ─────────────────────────────────────────────
    # LLM-BASED PARSING
    # ─────────────────────────────────────────────
    @classmethod
    def _call_llm(cls, prompt: str, expect_json: bool = True) -> Optional[str]:
        """Unified LLM call helper (Ollama or Gemini)."""
        provider = (settings.LLM_PROVIDER or "gemini").lower()
        
        if provider == "ollama":
            try:
                payload = {
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                }
                if expect_json:
                    payload["format"] = "json"
                    
                response = requests.post(settings.OLLAMA_URL, json=payload, timeout=300.0)
                if response.status_code == 200:
                    return response.json().get("response", "").strip()
            except Exception as e:
                logger.warning(f"Ollama call failed: {str(e)}")
        
        # Gemini fallback
        api_key = settings.GEMINI_API_KEY or ""
        if api_key and "YOUR_GEMINI_API" not in api_key:
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                config = types.GenerateContentConfig(temperature=0.1)
                if expect_json:
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=config
                )
                return response.text.strip()
            except Exception as e:
                logger.warning(f"Gemini call failed: {str(e)}")
        
        return None

    @classmethod
    def parse_resume(cls, resume_text: str) -> IndustrialResumeSchema:
        """
        Parses OCR resume text into structured profile.
        Routes to configured LLM provider with regex fallback.
        """
        if not resume_text:
            return cls._parse_heuristically("")
        
        prompt = f"{RESUME_PARSING_SYSTEM_PROMPT}\n{resume_text}"
        
        response = cls._call_llm(prompt, expect_json=True)
        
        if response:
            try:
                parsed_json = json.loads(response)
                parsed_data = IndustrialResumeSchema(**parsed_json)
                logger.info(f"LLM parsed resume successfully for candidate: {parsed_data.name}")
                return parsed_data
            except Exception as e:
                logger.error(f"LLM response parsing failed: {str(e)}. Falling back to heuristic parser.")
        
        return cls._parse_heuristically(resume_text)

    # ─────────────────────────────────────────────
    # CERTIFICATE PARSING
    # ─────────────────────────────────────────────
    @classmethod
    def parse_certificate(cls, text: str, source_filename: str = None) -> CertificateExtractionResult:
        """
        Extracts structured data from certificate text.
        """
        if not text or len(text.strip()) < 10:
            return CertificateExtractionResult(confidence=0.0, source_document=source_filename)
        
        prompt = f"{CERTIFICATE_EXTRACTION_PROMPT}\n{text}"
        response = cls._call_llm(prompt, expect_json=True)
        
        if response:
            try:
                parsed = json.loads(response)
                parsed["source_document"] = source_filename
                parsed["confidence"] = 0.85
                return CertificateExtractionResult(**parsed)
            except Exception as e:
                logger.warning(f"Certificate LLM parsing failed: {str(e)}")
        
        # Heuristic extraction for certificates
        return cls._parse_certificate_heuristically(text, source_filename)

    @classmethod
    def _parse_certificate_heuristically(cls, text: str, source_filename: str = None) -> CertificateExtractionResult:
        """Regex-based certificate extraction fallback."""
        text_lower = text.lower()
        
        # Try to find certificate name
        cert_name = None
        for pattern in [r'certificate\s+(?:of|in|for)\s+(.+?)(?:\n|$)', r'(?:this|the)\s+(.+?certificate.+?)(?:\n|$)']: 
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                cert_name = match.group(1).strip()[:100]
                break
        
        # Name extraction
        name_match = re.search(r'(?:awarded to|issued to|certify that|name)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
        recipient = name_match.group(1).strip() if name_match else None
        
        # Date extraction
        date_pattern = r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{4})'
        dates = re.findall(date_pattern, text)
        
        # Safety domain
        safety_domain = None
        if any(kw in text_lower for kw in ["dgms", "mining", "mine"]):
            safety_domain = "mining"
        elif any(kw in text_lower for kw in ["weld", "asme", "aws"]):
            safety_domain = "welding"
        elif any(kw in text_lower for kw in ["crane", "rigging"]):
            safety_domain = "crane"
        elif any(kw in text_lower for kw in ["boiler"]):
            safety_domain = "boiler"
        elif any(kw in text_lower for kw in ["fire", "safety"]):
            safety_domain = "fire"
        
        return CertificateExtractionResult(
            certificate_name=cert_name,
            recipient_name=recipient,
            issue_date=dates[0] if dates else None,
            expiry_date=dates[1] if len(dates) > 1 else None,
            safety_domain=safety_domain,
            is_safety_critical=safety_domain is not None,
            confidence=0.4,
            source_document=source_filename
        )

    # ─────────────────────────────────────────────
    # EXPERIENCE LETTER PARSING
    # ─────────────────────────────────────────────
    @classmethod
    def parse_experience_letter(cls, text: str, source_filename: str = None) -> ExperienceLetterResult:
        """Extracts structured data from experience letter text."""
        if not text or len(text.strip()) < 10:
            return ExperienceLetterResult(confidence=0.0, source_document=source_filename)
        
        prompt = f"{EXPERIENCE_LETTER_EXTRACTION_PROMPT}\n{text}"
        response = cls._call_llm(prompt, expect_json=True)
        
        if response:
            try:
                parsed = json.loads(response)
                parsed["source_document"] = source_filename
                parsed["confidence"] = 0.85
                return ExperienceLetterResult(**parsed)
            except Exception as e:
                logger.warning(f"Experience letter LLM parsing failed: {str(e)}")
        
        # Heuristic fallback
        return ExperienceLetterResult(
            confidence=0.3,
            source_document=source_filename
        )

    # ─────────────────────────────────────────────
    # MULTI-DOCUMENT PROFILE MERGING
    # ─────────────────────────────────────────────
    @classmethod
    def merge_multi_document_profiles(cls, 
                                       resume_data: Optional[IndustrialResumeSchema],
                                       certificates: List[CertificateExtractionResult],
                                       experience_letters: List[ExperienceLetterResult]
                                       ) -> IndustrialResumeSchema:
        """
        Merges information from multiple documents into a unified candidate profile.
        Resolves conflicts by preferring higher-confidence data sources.
        """
        if not resume_data:
            resume_data = IndustrialResumeSchema()
        
        # Merge certificates
        all_certs = list(resume_data.certifications) if resume_data.certifications else []
        all_safety = list(resume_data.safety_certifications) if resume_data.safety_certifications else []
        
        for cert in certificates:
            if cert.certificate_name:
                # Check if already exists
                existing_names = [c.name.lower() for c in all_certs]
                if cert.certificate_name.lower() not in existing_names:
                    all_certs.append(ParsedCertification(
                        name=cert.certificate_name,
                        issuer=cert.issuer,
                        issue_date=cert.issue_date,
                        expiry_date=cert.expiry_date,
                        registration_number=cert.registration_number,
                        grade_or_class=cert.grade_or_class,
                        safety_domain=cert.safety_domain,
                        is_safety_critical=cert.is_safety_critical,
                        source_document=cert.source_document,
                        confidence=cert.confidence
                    ))
                    if cert.is_safety_critical and cert.certificate_name not in all_safety:
                        all_safety.append(cert.certificate_name)
        
        resume_data.certifications = all_certs
        resume_data.safety_certifications = all_safety
        
        # Merge experience letters
        companies = list(resume_data.previous_companies) if resume_data.previous_companies else []
        for letter in experience_letters:
            if letter.employer_name and letter.employer_name not in companies:
                companies.append(letter.employer_name)
            
            # Update name if missing
            if not resume_data.name and letter.employee_name:
                resume_data.name = letter.employee_name
        
        resume_data.previous_companies = companies
        
        logger.info(
            f"Merged profile: {len(all_certs)} certifications, "
            f"{len(companies)} employers from multi-document extraction."
        )
        
        return resume_data

    @classmethod
    def serialize_parsed_data(cls, parsed_data: IndustrialResumeSchema) -> str:
        """Converts Parsed Pydantic schema into text/JSON for database storage."""
        return parsed_data.model_dump_json()

    # ─────────────────────────────────────────────
    # JOB DESCRIPTION PARSING
    # ─────────────────────────────────────────────
    @classmethod
    def parse_job_description(cls, jd_text: str) -> dict:
        """
        AI-powered extraction of structured requirements from a free-text job description.
        Falls back to keyword-based heuristics when LLM is unavailable.
        
        Returns:
            dict with keys: required_skills, nice_to_have_skills, required_certifications,
            experience_years, salary_range, shift_type, physical_requirements,
            key_responsibilities, location
        """
        if not jd_text or not jd_text.strip():
            return {
                "required_skills": [], "nice_to_have_skills": [],
                "required_certifications": [], "experience_years": 0.0,
                "salary_range": None, "shift_type": None,
                "physical_requirements": [], "key_responsibilities": [], "location": None
            }

        # Try LLM first
        try:
            prompt = JD_PARSING_PROMPT + jd_text
            response = cls._call_llm(prompt, expect_json=True)
            if response:
                parsed = json.loads(response)
                logger.info(f"JD parsed via LLM: {len(parsed.get('required_skills', []))} skills extracted")
                return {
                    "required_skills": parsed.get("required_skills", []),
                    "nice_to_have_skills": parsed.get("nice_to_have_skills", []),
                    "required_certifications": parsed.get("required_certifications", []),
                    "experience_years": float(parsed.get("experience_years", 0.0)),
                    "salary_range": parsed.get("salary_range"),
                    "shift_type": parsed.get("shift_type"),
                    "physical_requirements": parsed.get("physical_requirements", []),
                    "key_responsibilities": parsed.get("key_responsibilities", []),
                    "location": parsed.get("location")
                }
        except Exception as e:
            logger.warning(f"LLM JD parsing failed: {str(e)}. Using heuristic fallback.")

        # Heuristic fallback
        return cls._parse_jd_heuristically(jd_text)

    @classmethod
    def _parse_jd_heuristically(cls, text: str) -> dict:
        """Keyword-based JD requirement extraction."""
        text_lower = text.lower()

        # Skills extraction from common industrial skill keywords
        skill_keywords = [
            "welding", "rigging", "crane", "excavation", "drilling", "blasting",
            "scaffolding", "electrical", "plumbing", "machining", "grinding",
            "forklift", "dumper", "loader", "dozer", "compressor", "lathe",
            "fitting", "turning", "milling", "painting", "carpentry",
            "cutting", "fabrication", "assembly", "maintenance", "repair",
            "piping", "hvac", "boiler", "turbine", "generator", "motor",
            "safety", "supervision", "quality", "inspection", "testing"
        ]
        found_skills = [kw.title() for kw in skill_keywords if kw in text_lower]

        # Certification extraction
        cert_keywords = [
            "dgms", "osha", "first aid", "fire safety", "crane safety",
            "rigging safety", "scaffolding", "gas testing", "blasting license",
            "boiler attendant", "iti", "asme", "aws", "confined space"
        ]
        found_certs = [kw.title() for kw in cert_keywords if kw in text_lower]

        # Experience years
        exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)', text_lower)
        exp_years = float(exp_match.group(1)) if exp_match else 0.0

        # Salary
        salary_match = re.search(
            r'(?:salary|ctc|compensation|pay)[:\s]*(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\s*[-–to]+\s*[\d,]+)?)',
            text, re.IGNORECASE
        )
        salary_range = salary_match.group(1).replace(',', '').strip() if salary_match else None

        # Shift type
        shift_type = None
        if "rotational" in text_lower or "shift rotation" in text_lower:
            shift_type = "rotational"
        elif "night shift" in text_lower:
            shift_type = "night"
        elif "day shift" in text_lower:
            shift_type = "day"

        return {
            "required_skills": found_skills,
            "nice_to_have_skills": [],
            "required_certifications": found_certs,
            "experience_years": exp_years,
            "salary_range": salary_range,
            "shift_type": shift_type,
            "physical_requirements": [],
            "key_responsibilities": [],
            "location": None
        }
