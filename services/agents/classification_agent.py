"""
Document Classification Agent.

Runs ML classifier on each document in the batch, determines document types,
and routes documents to appropriate extraction pipelines.
"""

import os
from services.agents.state import AgentState
from services.document_intelligence.classifier import DocumentClassifier
from services.document_intelligence.vision_model import VisionModel
from config.logging_config import logger


class ClassificationAgent:
    """Classification Agent Node: Identifies document types with confidence scores."""
    
    @staticmethod
    def execute(state: AgentState) -> AgentState:
        state.current_node = "classification"
        state.log_transition("Classification Agent", "Initiating ML document classification pipeline...")
        
        if state.status == "failed":
            state.log_transition("Classification Agent", "Skipping classification due to prior failures.")
            return state
        
        try:
            # Gather all files to classify
            files_to_classify = []
            
            if state.per_file_ocr_results:
                files_to_classify = list(state.per_file_ocr_results.keys())
            elif state.ocr_raw_text and state.file_path:
                files_to_classify = [state.file_path]
            
            if not files_to_classify:
                state.log_transition("Classification Agent", "No documents to classify. Continuing pipeline.")
                return state
            
            classifications = {}
            
            for file_path in files_to_classify:
                filename = os.path.basename(file_path)
                
                # Get OCR text for this file
                ocr_text = ""
                if file_path in state.per_file_ocr_results:
                    ocr_text = state.per_file_ocr_results[file_path].get("text", "")
                elif file_path == state.file_path:
                    ocr_text = state.ocr_raw_text or ""
                
                # Run keyword-based classification
                result = DocumentClassifier.classify(ocr_text, use_llm_fallback=True)
                
                # Cross-validate with vision model if it's an image file
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
                    try:
                        visual_result = VisionModel.classify_document_visually(file_path)
                        if visual_result.get("doc_type") and visual_result.get("doc_type") != "unknown":
                            # If vision and text classifiers agree, boost confidence
                            if visual_result.get("doc_type") == result["doc_type"]:
                                result["confidence"] = min(1.0, result["confidence"] + 0.15)
                                result["visual_validation"] = "confirmed"
                            else:
                                # Disagreement: use higher confidence result
                                visual_conf = float(visual_result.get("confidence", 0))
                                if visual_conf > result["confidence"]:
                                    result["doc_type"] = visual_result["doc_type"]
                                    result["confidence"] = visual_conf
                                    result["visual_validation"] = "vision_override"
                                else:
                                    result["visual_validation"] = "text_preferred"
                            
                            result["visual_cues"] = visual_result.get("visual_cues", "")
                    except Exception as e:
                        logger.warning(f"Visual classification failed for {filename}: {str(e)}")
                
                classifications[file_path] = result
                
                state.log_transition(
                    "Classification Agent",
                    f"Document '{filename}' classified as '{result['doc_type_display']}' "
                    f"(confidence: {result['confidence']:.1%}, method: {result.get('classification_method', 'unknown')})"
                )
            
            state.document_classifications = classifications
            
            # Summary
            type_counts = {}
            for cls_result in classifications.values():
                dt = cls_result.get("doc_type", "unknown")
                type_counts[dt] = type_counts.get(dt, 0) + 1
            
            state.log_transition(
                "Classification Agent",
                f"Classification complete. {len(classifications)} documents processed. "
                f"Types: {', '.join(f'{k}={v}' for k, v in type_counts.items())}"
            )
            
        except Exception as e:
            state.errors.append(f"Classification error: {str(e)}")
            state.log_transition("Classification Agent", f"WARNING: Classification failed: {str(e)}. Pipeline continues.")
        
        return state
