from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Financial Analysis Service"
    VERSION: str = "1.0.0"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8002

    # Database - MySQL
    DATABASE_URL: str = Field(
        ...,
        description="MySQL database connection URL",
        env="DATABASE_URL"
    )

    # Redis Settings
    REDIS_HOST: str = Field(..., description="Redis server host", env="REDIS_HOST")
    REDIS_PORT: int = Field(..., description="Redis server port", env="REDIS_PORT")
    REDIS_DB: int = Field(..., description="Redis database number", env="REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    # MinIO/S3 Settings (for fetching CSV files)
    MINIO_ENDPOINT: str = Field(..., description="MinIO/S3 endpoint URL", env="MINIO_ENDPOINT")
    MINIO_ACCESS_KEY: str = Field(..., description="MinIO access key", env="MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: str = Field(..., description="MinIO secret key", env="MINIO_SECRET_KEY")
    MINIO_BUCKET: str = Field(..., description="MinIO bucket name", env="MINIO_BUCKET")
    MINIO_SECURE: bool = Field(default=True, env="MINIO_SECURE")
    VERIFY_SSL: bool = Field(default=False, env="VERIFY_SSL")

    @validator('DATABASE_URL')
    def validate_database_url(cls, v):
        if not v:
            raise ValueError(
                "DATABASE_URL is required. "
                "Please set it in .env file. "
                "Format: mysql+pymysql://user:password@host:port/database"
            )
        if not v.startswith(('mysql://', 'mysql+pymysql://', 'mysql+aiomysql://')):
            raise ValueError(
                "DATABASE_URL must be a MySQL connection string. "
                "Expected format: mysql+pymysql://user:password@host:port/database"
            )
        return v

    @validator('REDIS_HOST')
    def validate_redis_host(cls, v):
        if not v:
            raise ValueError(
                "REDIS_HOST is required. "
                "Please set it in .env file (e.g., redis or localhost)"
            )
        return v

    @validator('MINIO_ENDPOINT')
    def validate_minio_endpoint(cls, v):
        if not v:
            raise ValueError(
                "MINIO_ENDPOINT is required. "
                "Please set it in .env file (e.g., minio:9000)"
            )
        return v
    
    # OpenAI GPT Configuration
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    # Analysis Settings
    MAX_DATA_POINTS: int = 10000
    CONFIDENCE_THRESHOLD: float = 0.8
    ANOMALY_THRESHOLD: float = 0.95

    # Uvicorn Settings
    UVICORN_WORKERS: int = Field(default=4, env="UVICORN_WORKERS")

    # Database Pool Settings
    # Dynamic pool sizing based on worker count
    # pool_size = workers * 5, max_overflow = workers * 10
    @property
    def DB_POOL_SIZE(self) -> int:
        return max(10, self.UVICORN_WORKERS * 5)

    @property
    def DB_MAX_OVERFLOW(self) -> int:
        return max(20, self.UVICORN_WORKERS * 10)

    DB_POOL_RECYCLE: int = Field(default=3600, env="DB_POOL_RECYCLE")  # 1 hour
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")
    DB_CONNECT_TIMEOUT: int = Field(default=10, env="DB_CONNECT_TIMEOUT")

    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()