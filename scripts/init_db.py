import sys
from pathlib import Path

# Adjust path to enable absolute imports from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.connection import Base, engine
from config.logging_config import logger
import database.models # Force load all model definitions to bind tables

def initialize_database():
    """Initializes the database schema by binding and creating all metadata tables."""
    logger.info("Initializing system database schema...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas and indexes built successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    initialize_database()
