"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import ssl
import logging
import os

logger = logging.getLogger(__name__)

# SSL configuration for Azure MySQL
# WARNING: Current configuration disables SSL verification for development
# For production, use proper certificate validation (see comments below)
ssl_context = ssl.create_default_context()

# TODO: Enable SSL verification for production
# Production configuration:
# ssl_context.check_hostname = True
# ssl_context.verify_mode = ssl.CERT_REQUIRED
# ssl_context.load_verify_locations('/path/to/DigiCertGlobalRootCA.crt.pem')

# Development configuration (INSECURE - do not use in production)
if os.getenv("ENV", "development") == "development":
    logger.warning("⚠️  SSL certificate verification is DISABLED (development mode)")
    logger.warning("⚠️  Do NOT use this configuration in production!")
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
else:
    # Production mode - require proper SSL
    logger.info("✅ SSL certificate verification ENABLED (production mode)")
    ssl_context.check_hostname = True
    ssl_context.verify_mode = ssl.CERT_REQUIRED

# Create database engine with SSL
# NOTE: SQLAlchemy connection pool is SHARED across all Uvicorn workers
# Workers=4: pool_size=20, max_overflow=40
# Total connections available: pool_size + max_overflow = 60 connections (shared by all workers)
# NOT 240 connections! The pool is created once and shared by all worker processes.
try:
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

    # Log pool configuration
    logger.info(f"📊 Database pool configured: size={settings.DB_POOL_SIZE}, "
                f"max_overflow={settings.DB_MAX_OVERFLOW}, "
                f"total={settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW} connections")
    logger.info(f"🔄 Pool recycle: {settings.DB_POOL_RECYCLE}s, "
                f"timeout: {settings.DB_POOL_TIMEOUT}s, "
                f"connect_timeout: {settings.DB_CONNECT_TIMEOUT}s")

except Exception as e:
    logger.error(f"❌ Failed to create database engine: {e}")
    logger.error(f"DATABASE_URL format: mysql+pymysql://user:pass@host:port/db")
    raise

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