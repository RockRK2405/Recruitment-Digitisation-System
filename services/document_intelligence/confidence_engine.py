"""
Per-Field Extraction Confidence Engine.

Tracks confidence scores for each extracted field with source provenance,
computes aggregate confidence reports, and identifies low-confidence fields
that need human review.
"""

from typing import Optional, Any
from sqlalchemy.orm import Session
from config.logging_config import logger


class ConfidenceEngine:
    """Tracks and reports per-field extraction confidence with source provenance."""

    @classmethod
    def track_extraction(cls, db: Session, candidate_id: int, document_id: Optional[int],
                         field_name: str, field_value: Any, confidence: float,
                         extraction_method: str = "llm", source_page: Optional[int] = None,
                         bounding_box_json: Optional[str] = None):
        """
        Records a single field extraction with confidence metadata.
        
        Args:
            db: Database session
            candidate_id: ID of the candidate this field belongs to
            document_id: Source document ID
            field_name: Name of the extracted field (e.g. 'name', 'phone', 'email')
            field_value: The extracted value
            confidence: Confidence score (0.0-1.0)
            extraction_method: How it was extracted ('ocr', 'vision', 'llm', 'heuristic')
            source_page: Page number the field was found on
            bounding_box_json: Bounding box coordinates as JSON string
        """
        try:
            from database.models import ExtractionConfidence

            record = ExtractionConfidence(
                candidate_id=candidate_id,
                document_id=document_id,
                field_name=field_name,
                field_value=str(field_value) if field_value is not None else None,
                confidence_score=confidence,
                extraction_method=extraction_method,
                source_page=source_page,
                bounding_box_json=bounding_box_json
            )
            db.add(record)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to track extraction confidence for '{field_name}': {str(e)}")

    @classmethod
    def track_extraction_batch(cls, db: Session, candidate_id: int,
                               document_id: Optional[int], fields: dict,
                               confidence: float, extraction_method: str = "llm"):
        """
        Records multiple field extractions in a single batch.
        
        Args:
            db: Database session
            candidate_id: Candidate ID
            document_id: Source document ID
            fields: Dict of {field_name: field_value}
            confidence: Base confidence score applied to all fields
            extraction_method: Extraction method identifier
        """
        try:
            from database.models import ExtractionConfidence

            for field_name, field_value in fields.items():
                # Adjust confidence per field based on value presence
                field_conf = confidence
                if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
                    field_conf = 0.0
                elif isinstance(field_value, (int, float)) and field_value == 0:
                    field_conf = max(0.0, confidence - 0.3)

                record = ExtractionConfidence(
                    candidate_id=candidate_id,
                    document_id=document_id,
                    field_name=field_name,
                    field_value=str(field_value) if field_value is not None else None,
                    confidence_score=round(field_conf, 3),
                    extraction_method=extraction_method
                )
                db.add(record)

            db.commit()
            logger.info(f"Tracked {len(fields)} field confidences for candidate {candidate_id}")
        except Exception as e:
            db.rollback()
            logger.warning(f"Batch confidence tracking failed: {str(e)}")

    @classmethod
    def get_confidence_report(cls, db: Session, candidate_id: int) -> dict:
        """
        Generates an aggregate confidence report for a candidate.
        
        Returns:
            dict: {
                "candidate_id": int,
                "total_fields": int,
                "average_confidence": float,
                "low_confidence_fields": list,
                "high_confidence_fields": list,
                "fields": list[dict],
                "needs_review": bool
            }
        """
        try:
            from database.models import ExtractionConfidence
            from config.settings import settings

            records = db.query(ExtractionConfidence).filter(
                ExtractionConfidence.candidate_id == candidate_id
            ).order_by(ExtractionConfidence.confidence_score.asc()).all()

            if not records:
                return {
                    "candidate_id": candidate_id,
                    "total_fields": 0,
                    "average_confidence": 0.0,
                    "low_confidence_fields": [],
                    "high_confidence_fields": [],
                    "fields": [],
                    "needs_review": True
                }

            threshold = settings.FIELD_CONFIDENCE_THRESHOLD
            fields = []
            low_conf = []
            high_conf = []

            total_conf = 0.0
            for rec in records:
                field_data = {
                    "field_name": rec.field_name,
                    "field_value": rec.field_value,
                    "confidence": rec.confidence_score,
                    "extraction_method": rec.extraction_method,
                    "source_page": rec.source_page
                }
                fields.append(field_data)
                total_conf += rec.confidence_score

                if rec.confidence_score < threshold:
                    low_conf.append(rec.field_name)
                elif rec.confidence_score >= 0.8:
                    high_conf.append(rec.field_name)

            avg_conf = total_conf / len(records) if records else 0.0

            return {
                "candidate_id": candidate_id,
                "total_fields": len(records),
                "average_confidence": round(avg_conf, 3),
                "low_confidence_fields": low_conf,
                "high_confidence_fields": high_conf,
                "fields": fields,
                "needs_review": len(low_conf) > 0 or avg_conf < threshold
            }
        except Exception as e:
            logger.error(f"Confidence report generation failed: {str(e)}")
            return {
                "candidate_id": candidate_id,
                "total_fields": 0,
                "average_confidence": 0.0,
                "low_confidence_fields": [],
                "high_confidence_fields": [],
                "fields": [],
                "needs_review": True,
                "error": str(e)
            }