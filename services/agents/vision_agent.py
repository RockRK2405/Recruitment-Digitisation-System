"""
Vision Analysis Agent.

Sends image documents to the Vision-Language Model for visual analysis,
extracts certifications visible in images, and cross-validates OCR findings.
"""

import os
from services.agents.state import AgentState
from services.document_intelligence.vision_model import VisionModel
from config.logging_config import logger


class VisionAnalysisAgent:
    """Vision Agent Node: Performs VLM-powered image understanding and extraction."""
    
    @staticmethod
    def execute(state: AgentState) -> AgentState:
        state.current_node = "vision_analysis"
        state.log_transition("Vision Agent", "Initializing Vision-Language Model analysis pipeline...")
        
        if state.status == "failed":
            state.log_transition("Vision Agent", "Skipping vision analysis due to prior failures.")
            return state
        
        # Check if VLM is available
        vlm_status = VisionModel.is_available()
        if not vlm_status.get("any_available", False):
            state.log_transition(
                "Vision Agent",
                "No Vision-Language Model available (Ollama VLM or Gemini). "
                "Skipping visual analysis. Pipeline continues with OCR-only extraction."
            )
            return state
        
        try:
            # Identify image files that need vision analysis
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
            image_files = []
            
            all_files = state.file_paths if state.file_paths else ([state.file_path] if state.file_path else [])
            
            for file_path in all_files:
                ext = os.path.splitext(file_path)[1].lower()
                if ext in image_extensions and os.path.exists(file_path):
                    image_files.append(file_path)
            
            if not image_files:
                state.log_transition("Vision Agent", "No image files in batch. Skipping VLM analysis.")
                return state
            
            state.log_transition(
                "Vision Agent",
                f"Found {len(image_files)} image files for vision analysis."
            )
            
            vision_results = {}
            
            for file_path in image_files:
                filename = os.path.basename(file_path)
                
                # Get document classification for routing
                doc_type = "unknown"
                if file_path in state.document_classifications:
                    doc_type = state.document_classifications[file_path].get("doc_type", "unknown")
                
                state.log_transition("Vision Agent", f"Analyzing '{filename}' (type: {doc_type})...")
                
                # Run appropriate vision analysis based on document type
                if doc_type == "certificate":
                    # Certificate-specific analysis
                    result = VisionModel.verify_certificate(file_path)
                    analysis_type = "certificate_verification"
                    state.log_transition(
                        "Vision Agent",
                        f"Certificate analysis complete for '{filename}'. "
                        f"Cert: {result.get('certificate_name', 'Unknown')} | "
                        f"Verification confidence: {result.get('verification_confidence', 'N/A')}"
                    )
                else:
                    # General extraction
                    result = VisionModel.extract_from_image(file_path)
                    analysis_type = "general_extraction"
                    
                    doc_type_from_vision = result.get("document_type", "unknown")
                    state.log_transition(
                        "Vision Agent",
                        f"Vision extraction complete for '{filename}'. "
                        f"VLM detected type: {doc_type_from_vision}"
                    )
                
                vision_results[file_path] = {
                    "analysis_type": analysis_type,
                    "result": result,
                    "filename": filename,
                    "doc_type": doc_type
                }
            
            state.vision_analysis_results = vision_results
            
            # Cross-validate OCR with vision findings
            cross_validation_notes = []
            for file_path, vis_result in vision_results.items():
                extraction = vis_result.get("result", {})
                extracted_data = extraction.get("extracted_data", {})
                
                # Check if vision found certifications not in OCR text
                vision_certs = extracted_data.get("certifications", [])
                if vision_certs:
                    ocr_text = ""
                    if file_path in state.per_file_ocr_results:
                        ocr_text = state.per_file_ocr_results[file_path].get("text", "").lower()
                    elif file_path == state.file_path and state.ocr_raw_text:
                        ocr_text = state.ocr_raw_text.lower()
                    
                    for cert in vision_certs:
                        if cert.lower() not in ocr_text:
                            cross_validation_notes.append(
                                f"VLM found certification '{cert}' in {os.path.basename(file_path)} "
                                f"not detected by OCR"
                            )
            
            if cross_validation_notes:
                state.log_transition(
                    "Vision Agent",
                    f"Cross-validation: {len(cross_validation_notes)} discrepancies found between OCR and VLM. "
                    f"Details: {'; '.join(cross_validation_notes[:3])}"
                )
            
            state.log_transition(
                "Vision Agent",
                f"Vision analysis complete. {len(vision_results)} images analyzed."
            )
            
        except Exception as e:
            state.errors.append(f"Vision analysis error: {str(e)}")
            state.log_transition(
                "Vision Agent",
                f"WARNING: Vision analysis encountered error: {str(e)}. Pipeline continues."
            )
        
        return state
