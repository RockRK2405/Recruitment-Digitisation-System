"""
Vision-Language Model Wrapper for Document Intelligence.

Provides image-based document analysis using:
  1. Ollama VLM (local, with base64 image encoding)
  2. Gemini Vision (cloud fallback)
  3. Heuristic fallback (when no VLM is available)

Exposes methods for document classification, certificate verification,
and general image extraction — all called by VisionAnalysisAgent and ClassificationAgent.
"""

import os
import json
import base64
import requests
from config.settings import settings
from config.logging_config import logger


class VisionModel:
    """Vision-Language Model wrapper for document image analysis."""

    @classmethod
    def is_available(cls) -> dict:
        """
        Checks availability of VLM backends.
        
        Returns:
            dict: {"any_available": bool, "ollama_vlm": bool, "gemini_vision": bool}
        """
        ollama_ok = False
        gemini_ok = False

        # Check Ollama VLM
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2.0)
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                vlm_model = settings.OLLAMA_VISION_MODEL
                ollama_ok = any(vlm_model.split(":")[0] in m for m in models) or len(models) > 0
        except Exception:
            pass

        # Check Gemini
        api_key = settings.GEMINI_API_KEY or ""
        if api_key and "YOUR_GEMINI_API" not in api_key:
            gemini_ok = True

        return {
            "any_available": ollama_ok or gemini_ok,
            "ollama_vlm": ollama_ok,
            "gemini_vision": gemini_ok
        }

    @classmethod
    def _encode_image_base64(cls, image_path: str) -> str:
        """Encodes an image file to base64 string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @classmethod
    def _call_ollama_vlm(cls, image_path: str, prompt: str) -> dict:
        """Sends image + prompt to Ollama VLM and returns parsed response."""
        img_b64 = cls._encode_image_base64(image_path)
        payload = {
            "model": settings.OLLAMA_VISION_MODEL,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
            "format": "json"
        }
        resp = requests.post(settings.OLLAMA_VISION_URL, json=payload, timeout=120.0)
        if resp.status_code == 200:
            raw = resp.json().get("response", "")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw_response": raw}
        return {}

    @classmethod
    def _call_gemini_vision(cls, image_path: str, prompt: str) -> dict:
        """Sends image + prompt to Gemini Vision API."""
        api_key = settings.GEMINI_API_KEY
        if not api_key or "YOUR_GEMINI_API" in api_key:
            return {}
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            # Read image
            img_b64 = cls._encode_image_base64(image_path)
            ext = os.path.splitext(image_path)[1].lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                        ".bmp": "image/bmp", ".tiff": "image/tiff", ".tif": "image/tiff"}
            mime = mime_map.get(ext, "image/jpeg")

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=base64.b64decode(img_b64), mime_type=mime),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return json.loads(response.text)
        except Exception as e:
            logger.warning(f"Gemini Vision call failed: {str(e)}")
            return {}

    @classmethod
    def _call_vlm(cls, image_path: str, prompt: str) -> dict:
        """Routes to available VLM backend."""
        availability = cls.is_available()

        if availability["ollama_vlm"]:
            try:
                result = cls._call_ollama_vlm(image_path, prompt)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Ollama VLM failed: {str(e)}")

        if availability["gemini_vision"]:
            try:
                result = cls._call_gemini_vision(image_path, prompt)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Gemini Vision failed: {str(e)}")

        return {}

    @classmethod
    def classify_document_visually(cls, image_path: str) -> dict:
        """
        Classifies a document image using visual cues.
        
        Returns:
            dict: {"doc_type": str, "confidence": float, "visual_cues": str}
        """
        prompt = (
            "Analyze this document image and classify it as one of: "
            "resume, certificate, experience_letter, id_card, training_record.\n"
            "Respond with JSON: {\"doc_type\": \"...\", \"confidence\": 0.0, "
            "\"visual_cues\": \"description of visual elements that led to classification\"}"
        )

        result = cls._call_vlm(image_path, prompt)

        if result and result.get("doc_type"):
            return {
                "doc_type": result.get("doc_type", "unknown"),
                "confidence": float(result.get("confidence", 0.5)),
                "visual_cues": result.get("visual_cues", "")
            }

        # Heuristic fallback based on filename
        filename = os.path.basename(image_path).lower()
        if any(kw in filename for kw in ["cert", "license", "diploma"]):
            return {"doc_type": "certificate", "confidence": 0.3, "visual_cues": "filename hint"}
        elif any(kw in filename for kw in ["exp", "letter", "reliev"]):
            return {"doc_type": "experience_letter", "confidence": 0.3, "visual_cues": "filename hint"}
        elif any(kw in filename for kw in ["id", "aadhar", "pan", "passport"]):
            return {"doc_type": "id_card", "confidence": 0.3, "visual_cues": "filename hint"}

        return {"doc_type": "unknown", "confidence": 0.1, "visual_cues": "no VLM available, no filename hints"}

    @classmethod
    def verify_certificate(cls, image_path: str) -> dict:
        """
        Performs visual verification of a certificate image.
        
        Returns:
            dict with certificate_name, verification_confidence, concerns, authenticity_markers
        """
        prompt = (
            "Analyze this certificate/license document image. Verify its authenticity by checking for:\n"
            "- Official seals or stamps\n"
            "- Signatures\n"
            "- Logos of issuing authority\n"
            "- Registration numbers\n"
            "- Quality of printing\n\n"
            "Respond with JSON: {\n"
            "  \"certificate_name\": \"name of certificate\",\n"
            "  \"verification_confidence\": 0.0,\n"
            "  \"concerns\": [\"list of concerns if any\"],\n"
            "  \"authenticity_markers\": {\"seal_visible\": true/false, \"signature_present\": true/false, "
            "\"logo_present\": true/false, \"registration_number_visible\": true/false}\n"
            "}"
        )

        result = cls._call_vlm(image_path, prompt)

        if result and result.get("certificate_name"):
            return {
                "certificate_name": result.get("certificate_name", "Unknown"),
                "verification_confidence": float(result.get("verification_confidence", 0.5)),
                "concerns": result.get("concerns", []),
                "authenticity_markers": result.get("authenticity_markers", {})
            }

        # Fallback: return neutral result
        return {
            "certificate_name": "Unknown Certificate",
            "verification_confidence": 0.3,
            "concerns": ["Visual verification unavailable — no VLM backend running"],
            "authenticity_markers": {
                "seal_visible": None, "signature_present": None,
                "logo_present": None, "registration_number_visible": None
            }
        }

    @classmethod
    def extract_from_image(cls, image_path: str) -> dict:
        """
        General extraction from a document image.
        
        Returns:
            dict with document_type and extracted_data containing name, certifications, etc.
        """
        prompt = (
            "Extract all visible information from this document image.\n"
            "Respond with JSON: {\n"
            "  \"document_type\": \"detected type\",\n"
            "  \"extracted_data\": {\n"
            "    \"name\": \"person name if visible\",\n"
            "    \"certifications\": [\"list of certifications mentioned\"],\n"
            "    \"dates\": [\"any dates visible\"],\n"
            "    \"organizations\": [\"any organizations mentioned\"],\n"
            "    \"key_text\": \"main text content\"\n"
            "  }\n"
            "}"
        )

        result = cls._call_vlm(image_path, prompt)

        if result and result.get("extracted_data"):
            return result

        # Fallback
        return {
            "document_type": "unknown",
            "extracted_data": {
                "name": None,
                "certifications": [],
                "dates": [],
                "organizations": [],
                "key_text": "Visual extraction unavailable"
            }
        }