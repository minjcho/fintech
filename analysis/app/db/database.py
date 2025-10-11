"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import ssl

# SSL configuration for Azure MySQL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Create database engine with SSL
# Dynamic pool sizing based on worker count
# Workers=4: pool_size=20, max_overflow=40 (total 60 connections/worker)
# Total connections: 60 × 4 workers = 240 connections
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,  # Dynamic: workers * 5
    max_overflow=settings.DB_MAX_OVERFLOW,  # Dynamic: workers * 10
    pool_recycle=settings.DB_POOL_RECYCLE,  # Prevent Azure MySQL 8-hour timeout
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Wait time for available connection
    connect_args={
        "ssl": ssl_context,
        "connect_timeout": settings.DB_CONNECT_TIMEOUT  # Connection establishment timeout
    }
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

def get_db():
    """
    Dependency for getting database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()