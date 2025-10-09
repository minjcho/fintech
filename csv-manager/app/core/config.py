"""
Application configuration and settings
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Settings
    API_PREFIX: str = "/api"
    PROJECT_NAME: str = "AI Fintech Gateway"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["*"],
        env="BACKEND_CORS_ORIGINS"
    )
    
    # MinIO/S3 Settings
    MINIO_ENDPOINT: str = Field(
        default="https://j13a409.p.ssafy.io:8909",
        env="MINIO_ENDPOINT"
    )
    MINIO_ACCESS_KEY: str = Field(
        default="minioadmin",
        env="MINIO_ACCESS_KEY"
    )
    MINIO_SECRET_KEY: str = Field(
        default="minioadmin",
        env="MINIO_SECRET_KEY"
    )
    MINIO_BUCKET: str = Field(
        default="csv",
        env="MINIO_BUCKET"
    )
    MINIO_REGION: str = Field(
        default="us-east-1",
        env="MINIO_REGION"
    )
    MINIO_SECURE: bool = Field(
        default=True,
        env="MINIO_SECURE"
    )
    
    # CSV Processing Settings
    CSV_STATUS_AUTO_CLEAR: bool = Field(
        default=False,  # Changed to False - status should be managed by services
        env="CSV_STATUS_AUTO_CLEAR"
    )
    CSV_STATUS_CLEAR_DELAY: int = Field(
        default=300,  # 5 minutes - only used if AUTO_CLEAR is true
        env="CSV_STATUS_CLEAR_DELAY"
    )
    PRESIGNED_URL_EXPIRY: int = Field(
        default=900,  # 15 minutes
        env="PRESIGNED_URL_EXPIRY"
    )
    
    # Authentication Settings (Development mode)
    AUTH_ENABLED: bool = Field(
        default=False,  # Set to True in production
        env="AUTH_ENABLED"
    )
    JWT_SECRET_KEY: Optional[str] = Field(
        default=None,
        env="JWT_SECRET_KEY"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        env="JWT_ALGORITHM"
    )
    
    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        env="LOG_LEVEL"
    )
    
    # SSL/TLS Settings for MinIO
    VERIFY_SSL: bool = Field(
        default=True,  # Set to False for self-signed certificates (not recommended for production)
        env="VERIFY_SSL"
    )
    
    # Redis Settings
    REDIS_HOST: str = Field(
        default=None,  # Required from .env
        env="REDIS_HOST"
    )
    REDIS_PORT: int = Field(
        default=None,  # Required from .env
        env="REDIS_PORT"
    )
    REDIS_DB: int = Field(
        default=None,  # Required from .env
        env="REDIS_DB"
    )
    REDIS_PASSWORD: Optional[str] = Field(
        default=None,
        env="REDIS_PASSWORD"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"


# Create settings instance
settings = Settings()