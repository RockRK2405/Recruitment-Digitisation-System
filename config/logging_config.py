import logging
import sys
from config.settings import settings

def setup_logging():
    """Sets up global structured logging for both FastAPI and Streamlit pipelines."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Define log format
    log_format = (
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(filename)s:%(lineno)d] - %(message)s"
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    
    # If handlers already exist (e.g. uvicorn has some), clear them to avoid duplicate outputs
    if root_logger.handlers:
        root_logger.handlers = []
        
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Suppress verbose secondary library logs (e.g. chromadb, sentence-transformers, pydantic)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pypdf").setLevel(logging.WARNING)
    
    logger = logging.getLogger("workforce_platform")
    logger.info(f"Structured logging system initialized with level: {settings.LOG_LEVEL}")
    
    return logger

# Primary logger instance
logger = setup_logging()
