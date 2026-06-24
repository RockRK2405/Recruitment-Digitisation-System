"""
Document Type Classifier for Multi-Modal Document Intelligence.

Classifies extracted OCR text into document types:
  resume, certificate, experience_letter, id_card, training_record, unknown

Uses keyword frequency scoring with configurable confidence thresholds
and optional LLM-based fallback for ambiguous documents.
"""

import re
from config.logging_config import logger
from config.settings import settings


# Document type keyword dictionaries with weighted terms
_DOC_TYPE_KEYWORDS = {
    "resume": {
        "high": ["resume", "curriculum vitae", "cv", "biodata", "career objective",
                 "work experience", "professional summary", "job objective",
                 "experience", "skills", "education"],
        "medium": ["qualification", "employer", "company", "responsibilities",
                   "projects", "achievements", "languages", "hobbies",
                   "references", "availability", "phone", "email", "contact"],
        "low": ["address", "name", "location"]
    },
    "certificate": {
        "high": ["certificate", "certification", "certified", "diploma",
                 "license", "licence", "awarded", "conferred", "competency"],
        "medium": ["issued", "authority", "registration", "valid", "expiry",
                   "accredited", "board", "examination", "grade", "class",
                   "dgms", "osha", "asme", "aws", "boiler attendant",
                   "gas testing", "sirdar", "first aid", "safety"],
        "low": ["seal", "signature", "stamp", "official", "government", "ministry"]
    },
    "experience_letter": {
        "high": ["experience letter", "experience certificate", "relieving letter",
                 "service certificate", "to whom it may concern", "employment certificate"],
        "medium": ["worked with us", "employed", "tenure", "relieved", "resignation",
                   "designation", "department", "conduct", "satisfactory",
                   "this is to certify", "we hereby confirm"],
        "low": ["performance", "duties", "role", "organization", "company"]
    },
    "id_card": {
        "high": ["aadhaar", "aadhar", "pan card", "voter id", "passport",
                 "driving license", "driving licence", "identity card",
                 "ration card", "election commission"],
        "medium": ["government of india", "unique identification", "date of birth",
                   "father's name", "husband's name", "uid", "enrollment"],
        "low": ["photo", "address", "male", "female", "signature"]
    },
    "training_record": {
        "high": ["training certificate", "training record", "training completion",
                 "course completion", "workshop certificate", "attended training"],
        "medium": ["training", "workshop", "seminar", "course", "module",
                   "participant", "trainee", "instructor", "batch",
                   "safety training", "induction training", "refresher"],
        "low": ["hours", "duration", "completed", "attended", "session"]
    }
}

# Display names
_DOC_TYPE_DISPLAY = {
    "resume": "Resume / CV",
    "certificate": "Certificate / License",
    "experience_letter": "Experience Letter",
    "id_card": "Identity Document",
    "training_record": "Training Record",
    "unknown": "Unknown Document"
}


class DocumentClassifier:
    """ML-grade keyword-scored document type classifier with LLM fallback."""

    @classmethod
    def classify(cls, text: str, use_llm_fallback: bool = False) -> dict:
        """
        Classifies extracted OCR text into a document type.
        
        Args:
            text: OCR-extracted text from the document
            use_llm_fallback: If True and keyword classification is ambiguous, try LLM
            
        Returns:
            dict: {
                "doc_type": str,
                "doc_type_display": str,
                "confidence": float (0.0-1.0),
                "all_scores": dict,
                "classification_method": str
            }
        """
        if not text or len(text.strip()) < 10:
            return {
                "doc_type": "unknown",
                "doc_type_display": _DOC_TYPE_DISPLAY["unknown"],
                "confidence": 0.0,
                "all_scores": {},
                "classification_method": "insufficient_text"
            }

        text_lower = text.lower()
        scores = {}

        for doc_type, keyword_groups in _DOC_TYPE_KEYWORDS.items():
            score = 0.0
            
            # High-weight keywords (3 points each)
            for kw in keyword_groups.get("high", []):
                if kw in text_lower:
                    score += 3.0

            # Medium-weight keywords (1.5 points each)
            for kw in keyword_groups.get("medium", []):
                if kw in text_lower:
                    score += 1.5

            # Low-weight keywords (0.5 points each)
            for kw in keyword_groups.get("low", []):
                if kw in text_lower:
                    score += 0.5

            scores[doc_type] = round(score, 2)

        # Determine best match
        if not scores or max(scores.values()) == 0:
            best_type = "unknown"
            confidence = 0.0
        else:
            best_type = max(scores, key=scores.get)
            max_score = scores[best_type]
            total_score = sum(scores.values())
            
            # Confidence is the ratio of best score to total, scaled
            if total_score > 0:
                confidence = min(1.0, (max_score / total_score) * 1.2)
            else:
                confidence = 0.0

        # Apply confidence threshold
        threshold = settings.CLASSIFIER_CONFIDENCE_THRESHOLD
        if confidence < threshold:
            # If below threshold and LLM fallback is enabled, try LLM
            if use_llm_fallback:
                llm_result = cls._classify_with_llm(text)
                if llm_result and llm_result.get("doc_type") != "unknown":
                    logger.info(f"LLM classifier override: {llm_result['doc_type']} (confidence: {llm_result['confidence']:.1%})")
                    llm_result["all_scores"] = scores
                    return llm_result

            # If still ambiguous, default to resume (most common upload type)
            if best_type == "unknown" and len(text.strip()) > 100:
                best_type = "resume"
                confidence = 0.4

        result = {
            "doc_type": best_type,
            "doc_type_display": _DOC_TYPE_DISPLAY.get(best_type, "Unknown"),
            "confidence": round(confidence, 3),
            "all_scores": scores,
            "classification_method": "keyword_scoring"
        }

        logger.info(f"Document classified as '{best_type}' with confidence {confidence:.1%}")
        return result

    @classmethod
    def _classify_with_llm(cls, text: str) -> dict:
        """Optional LLM-based classification for ambiguous documents."""
        try:
            from services.resume_parser.parser import ResumeParser
            prompt = (
                "Classify the following OCR-extracted document text into exactly one of these types: "
                "resume, certificate, experience_letter, id_card, training_record.\n"
                "Respond with ONLY a JSON object: {\"doc_type\": \"...\", \"confidence\": 0.0}\n\n"
                f"TEXT:\n{text[:2000]}"
            )
            response = ResumeParser._call_llm(prompt, expect_json=True)
            if response:
                import json
                parsed = json.loads(response)
                doc_type = parsed.get("doc_type", "unknown")
                if doc_type in _DOC_TYPE_DISPLAY:
                    return {
                        "doc_type": doc_type,
                        "doc_type_display": _DOC_TYPE_DISPLAY[doc_type],
                        "confidence": float(parsed.get("confidence", 0.7)),
                        "classification_method": "llm"
                    }
        except Exception as e:
            logger.warning(f"LLM classification fallback failed: {str(e)}")

        return None