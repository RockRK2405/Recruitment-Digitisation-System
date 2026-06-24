import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "Industrial Workforce Recruitment Platform"
    ENV: str = "development"
    DEBUG: bool = True
    
    # Paths
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    CHROMA_DB_PATH: str = str(BASE_DIR / "data" / "chromadb")
    
    # API & UI configurations
    API_PORT: int = 8000
    UI_PORT: int = 8501
    
    # PostgreSQL Configuration
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_secure_pwd_2026"
    POSTGRES_DB: str = "workforce_recruitment"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql://postgres:postgres_secure_pwd_2026@localhost:5432/workforce_recruitment"
    
    # Embeddings Configuration
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-base"
    
    # LLM Provider Configurations ('gemini' or 'ollama')
    LLM_PROVIDER: str = "ollama"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    
    # Local Ollama Settings
    OLLAMA_MODEL: str = "qwen3.6:latest"
    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_VISION_MODEL: str = "qwen3.6:latest"
    OLLAMA_VISION_URL: str = "http://localhost:11434/api/generate"
    
    # OCR & Document Intelligence Configurations
    EASYOCR_LANGUAGES: list = ["en", "hi"]
    VISION_ENABLED: bool = True
    CLASSIFIER_CONFIDENCE_THRESHOLD: float = 0.6
    FIELD_CONFIDENCE_THRESHOLD: float = 0.5
    
    # Logger
    LOG_LEVEL: str = "INFO"

    # Configure Pydantic to read from environment variables and .env file
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
settings = Settings()

# Ensure critical directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)
