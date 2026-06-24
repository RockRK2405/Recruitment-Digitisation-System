from pydantic_settings import BaseSettings
from typing import List, Optional
import json
import os


class Settings(BaseSettings):
    project_name: str = "WorkforceAI AI Service"
    env: str = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/workforce_recruitment"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Vector DB
    chroma_db_path: str = "./data/chromadb"
    embedding_model_name: str = "intfloat/multilingual-e5-base"

    # LLM
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "qwen3.6:latest"
    ollama_vision_model: str = "llava:13b"
    ollama_vision_url: str = "http://localhost:11434/api/generate"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"

    # OCR
    easyocr_languages: str = '["en", "hi"]'
    ocr_engine_cascade: str = "paddle,easyocr,tesseract"
    vision_enabled: bool = True

    # Thresholds
    classifier_confidence_threshold: float = 0.6
    field_confidence_threshold: float = 0.5

    # Upload
    upload_dir: str = "./uploads"
    max_file_size: int = 52428800

    # API
    api_port: int = 8000

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def easyocr_languages_list(self) -> List[str]:
        try:
            return json.loads(self.easyocr_languages)
        except (json.JSONDecodeError, TypeError):
            return ["en", "hi"]


settings = Settings()
os.makedirs(settings.chroma_db_path, exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)
