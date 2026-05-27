import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.settings import settings
from config.logging_config import logger

# Declare Base for SQLAlchemy models
Base = declarative_base()

# Attempt to configure the primary database URL
db_url = settings.DATABASE_URL
engine = None
SessionLocal = None
is_sqlite_fallback = False

try:
    # Set reasonable timeouts so it doesn't hang indefinitely on connection failures
    if "postgresql" in db_url:
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={"connect_timeout": 5}
        )
        # Verify connection immediately
        with engine.connect() as conn:
            pass
        logger.info("Successfully connected to primary PostgreSQL database.")
    else:
        raise ValueError("Non-Postgres DB url configured.")
except Exception as e:
    logger.warning(
        f"Could not connect to PostgreSQL primary database: {str(e)}. "
        "Initiating self-healing architecture: Falling back to local embedded SQLite database."
    )
    is_sqlite_fallback = True
    # Ensure data directory exists
    fallback_dir = os.path.dirname(settings.CHROMA_DB_PATH)
    os.makedirs(fallback_dir, exist_ok=True)
    fallback_path = os.path.join(fallback_dir, "local_fallback.db")
    db_url = f"sqlite:///{fallback_path}"
    
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False} # Required for SQLite with multithreading
    )
    logger.info(f"SQLite fallback database successfully initialized at: {fallback_path}")

# Create local session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """FastAPI dependency yielding a database session and closing it on request teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
