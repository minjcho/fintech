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
# Reduced pool size for multi-worker safety
# 4 workers × (3 + 5) = 32 connections
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,  # Reduced from 10
    max_overflow=5,  # Reduced from 20
    connect_args={
        "ssl": ssl_context
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