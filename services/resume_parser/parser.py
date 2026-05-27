import json
import re
import requests
from typing import Optional
from config.settings import settings
from config.logging_config import logger
from services.resume_parser.schema import IndustrialResumeSchema, ParsedCertification
from services.resume_parser.prompts import RESUME_PARSING_SYSTEM_PROMPT

class ResumeParser:
    """Executes LLM-assisted structural entity extraction from raw resume text."""
    
    @classmethod
    def _parse_heuristically(cls, text: str) -> IndustrialResumeSchema:
        """
        Regex-based rule heuristic parser. Runs if Gemini API is offline or key is missing.
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
        
        # 2. Extract Name (often first lines)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        name = "Unknown Worker"
        if lines:
            for l in lines[:3]:
                if "@" not in l and not any(char.isdigit() for char in l) and len(l) > 3:
                    name = l
                    break
        
        # 3. Detect domains & experience
        exp_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:years|yrs|year)\b', text, re.IGNORECASE)
        experience = float(exp_match.group(1)) if exp_match else 1.0
        
        domain = "Industrial"
        if any(w in text.lower() for w in ["mine", "mining", "coal", "dgms"]):
            domain = "Mining"
        elif any(w in text.lower() for w in ["power", "boiler", "turbine", "thermal"]):
            domain = "Thermal Power Plant"
        elif any(w in text.lower() for w in ["steel", "furnace", "foundry", "welder"]):
            domain = "Steel Plant"
        elif any(w in text.lower() for w in ["warehouse", "forklift", "dumper", "driver"]):
            domain = "Logistics"
            
        # 4. Extract Location
        location = "Dhanbad, Jharkhand" # Default
        for city in ["Dhanbad", "Ranchi", "Bhilai", "Jamshedpur", "Pune", "Mumbai", "Delhi", "Raipur"]:
            if city.lower() in text.lower():
                location = f"{city}, India"
                break
                
        # 5. Keywords mapping for blue-collar skills
        skills = []
        equipment = []
        safety = []
        
        keyword_skills = {
            "welding": "Arc Welding",
            "fitter": "Mechanical Fitting",
            "electrical": "Electrical Wiring",
            "rigging": "Scaffold Rigging",
            "drilling": "Blasting & Drilling",
            "haulage": "Heavy Hauling"
        }
        for kw, skill in keyword_skills.items():
            if kw in text.lower():
                skills.append(skill)
                
        keyword_equip = {
            "excavator": "Hydraulic Excavator",
            "crane": "Mobile Gantry Crane",
            "dumper": "CAT Dumper",
            "boiler": "Boiler Operations",
            "lathe": "Metal Lathe Machine"
        }
        for kw, eq in keyword_equip.items():
            if kw in text.lower():
                equipment.append(eq)
                
        keyword_safety = {
            "dgms": "DGMS Safety Certificate",
            "osha": "OSHA Safety Standard",
            "first aid": "St John First Aid Cert",
            "fire": "Fire Safety License"
        }
        for kw, sf in keyword_safety.items():
            if kw in text.lower():
                safety.append(sf)
                
        # Create standard lists
        languages = ["Hindi"]
        if "english" in text.lower():
            languages.append("English")
            
        # Create detailed certifications list
        certs = []
        for s_cert in safety:
            certs.append(
                ParsedCertification(
                    name=s_cert,
                    issuer="Government Authority" if "dgms" in s_cert.lower() else "OSHA Coordinator",
                    issue_date="2023",
                    expiry_date="2028"
                )
            )

        return IndustrialResumeSchema(
            name=name,
            phone=phone,
            email=email,
            location=location,
            experience_years=experience,
            industry_domain=domain,
            skills=skills if skills else ["General Labor"],
            equipment_handled=equipment if equipment else ["Hand Tools"],
            safety_certifications=safety,
            languages=languages,
            education="ITI Technical Pass" if "iti" in text.lower() else "Secondary School",
            availability="Immediate",
            previous_companies=["Industrial Contracting Inc."],
            certifications=certs
        )

    @classmethod
    def parse_resume(cls, resume_text: str) -> IndustrialResumeSchema:
        """
        Parses OCR resume text. Routes to the configured provider:
        - 'ollama': calls local Ollama server running the configured model
        - 'gemini': calls google-genai structured generation API
        Falls back to rule-based parser on failures.
        """
        if not resume_text:
            return cls._parse_heuristically("")
            
        provider = (settings.LLM_PROVIDER or "gemini").lower()
        
        # --- PATHWAY A: LOCAL OLLAMA ---
        if provider == "ollama":
            try:
                url = settings.OLLAMA_URL
                model = settings.OLLAMA_MODEL
                logger.info(f"Querying local Ollama server ({url}) using model: {model}...")
                
                payload = {
                    "model": model,
                    "prompt": f"{RESUME_PARSING_SYSTEM_PROMPT}\n{resume_text}",
                    "format": "json",
                    "stream": False
                }
                
                response = requests.post(url, json=payload, timeout=60.0)
                if response.status_code == 200:
                    response_json = response.json()
                    response_text = response_json.get("response", "").strip()
                    
                    # Bind generated text to Pydantic validation
                    parsed_json = json.loads(response_text)
                    parsed_data = IndustrialResumeSchema(**parsed_json)
                    
                    logger.info(f"Local Ollama model '{model}' parsed resume successfully for candidate: {parsed_data.name}")
                    return parsed_data
                else:
                    raise RuntimeError(f"Ollama returned bad status: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.error(
                    f"Local Ollama structured parse failed: {str(e)}. "
                    "Initiating regex heuristic parsing fallback to maintain system execution."
                )
                return cls._parse_heuristically(resume_text)
                
        # --- PATHWAY B: GOOGLE GEMINI ---
        else:
            api_key = settings.GEMINI_API_KEY or ""
            if not api_key or "YOUR_GEMINI_API" in api_key:
                logger.info("Gemini API key is not configured. Redirecting to heuristic regex parser.")
                return cls._parse_heuristically(resume_text)
                
            try:
                logger.info("Triggering Gemini structured parsing engine...")
                from google import genai
                from google.genai import types
                
                client = genai.Client(api_key=api_key)
                
                # Formulate structured prompt
                prompt = f"{RESUME_PARSING_SYSTEM_PROMPT}\n{resume_text}"
                
                # Execute Gemini with strict schema binding
                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=IndustrialResumeSchema,
                        temperature=0.1
                    )
                )
                
                # Parse output JSON into Pydantic schema
                parsed_json = json.loads(response.text)
                parsed_data = IndustrialResumeSchema(**parsed_json)
                
                logger.info(f"Gemini parsed resume successfully for candidate: {parsed_data.name}")
                return parsed_data
                
            except Exception as e:
                logger.error(
                    f"Gemini API structured parse failed: {str(e)}. "
                    "Initiating regex heuristic parsing fallback to maintain system execution."
                )
                return cls._parse_heuristically(resume_text)
            
    @classmethod
    def serialize_parsed_data(cls, parsed_data: IndustrialResumeSchema) -> str:
        """Converts Parsed Pydantic schema into text/JSON for database storage."""
        return parsed_data.model_dump_json()
