from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Financial Analysis Service"
    VERSION: str = "1.0.0"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    
    # Database - MySQL
    DATABASE_URL: str = Field(
        default=None,  # Required from .env file
        env="DATABASE_URL"
    )
    
    # Redis Settings
    REDIS_HOST: str = Field(default=None, env="REDIS_HOST")
    REDIS_PORT: int = Field(default=None, env="REDIS_PORT")
    REDIS_DB: int = Field(default=None, env="REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    # MinIO/S3 Settings (for fetching CSV files)
    MINIO_ENDPOINT: str = Field(default=None, env="MINIO_ENDPOINT")
    MINIO_ACCESS_KEY: str = Field(default=None, env="MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: str = Field(default=None, env="MINIO_SECRET_KEY")
    MINIO_BUCKET: str = Field(default=None, env="MINIO_BUCKET")
    MINIO_SECURE: bool = Field(default=True, env="MINIO_SECURE")
    VERIFY_SSL: bool = Field(default=False, env="VERIFY_SSL")
    
    # OpenAI GPT Configuration
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    # Analysis Settings
    MAX_DATA_POINTS: int = 10000
    CONFIDENCE_THRESHOLD: float = 0.8
    ANOMALY_THRESHOLD: float = 0.95
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()