from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List


class Settings(BaseSettings):
    PROJECT_NAME: str = "Expense Classifier Service"
    VERSION: str = "1.0.0"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "https://j13a409.p.ssafy.io",
        "https://j13a409.p.ssafy.io:3002"
    ]

    # Database
    DATABASE_URL: Optional[str] = None

    # S3 Configuration
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: str = "expense-classifier-bucket"
    AWS_REGION: str = "us-east-1"

    # OpenAI GPT Configuration (via GMS)
    GMS_API_KEY: str = Field(
        ...,
        description="SSAFY GMS API Key for GPT-5-nano access"
    )
    GMS_BASE_URL: str = Field(
        default="https://gms.ssafy.io/gmsapi/api.openai.com/v1",
        description="GMS API base URL"
    )
    OPENAI_MODEL: str = "gpt-5-nano"
    OPENAI_MAX_TOKENS: int = 4000
    OPENAI_TEMPERATURE: float = 0.3

    @validator('GMS_API_KEY')
    def validate_api_key(cls, v):
        if not v:
            raise ValueError(
                "GMS_API_KEY is required. "
                "Please set it in .env file or environment variables."
            )
        if not v.startswith('S13P'):
            raise ValueError(
                f"Invalid GMS_API_KEY format: {v[:10]}... "
                "Expected format: S13P22A409-xxxx-xxxx-xxxx"
            )
        return v

    @validator('GMS_BASE_URL')
    def validate_base_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError(
                "GMS_BASE_URL must start with http:// or https://"
            )
        return v
    
    # Classification Settings
    BATCH_SIZE: int = 10  # Smaller batches for API rate limits
    MAX_WORKERS: int = 4
    CONFIDENCE_THRESHOLD: float = 0.7
    DEFAULT_CATEGORY: str = "Other"
    GPT_TIMEOUT: int = 30  # seconds
    GPT_RETRY_COUNT: int = 3
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()