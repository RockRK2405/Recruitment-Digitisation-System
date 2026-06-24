"""
Multi-Modal Document Intelligence — Database Migration Script.

Creates all new tables and automatically detects and adds missing columns
to existing tables based on SQLAlchemy models.
"""

import sys
import os
from sqlalchemy import inspect, text

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.logging_config import logger
from database.connection import Base, engine
from database import models  # Import all models to register with Base

def run_migration():
    """Creates all tables that don't yet exist and dynamically migrates new columns."""
    logger.info("=" * 60)
    logger.info("Multi-Modal Document Intelligence — Database Migration")
    logger.info("=" * 60)
    
    try:
        # 1. Create new tables
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created or verified.")
        
        # 2. Automatically detect and add missing columns
        inspector = inspect(engine)
        db_tables = inspector.get_table_names()
        
        with engine.begin() as connection:
            for table_name, table_obj in Base.metadata.tables.items():
                if table_name in db_tables:
                    existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
                    for col_obj in table_obj.columns:
                        col_name = col_obj.name
                        if col_name not in existing_cols:
                            # Compile column type to string representation
                            col_type = str(col_obj.type)
                            logger.info(f"Adding missing column '{col_name}' ({col_type}) to table '{table_name}'...")
                            
                            # Execute ALTER TABLE statement
                            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                            logger.info(f"  ✓ Added column '{col_name}' to table '{table_name}'")
                            
        logger.info("=" * 60)
        logger.info("All tables and columns migrated successfully.")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise


if __name__ == "__main__":
    run_migration()
