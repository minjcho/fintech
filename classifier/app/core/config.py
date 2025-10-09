from pydantic_settings import BaseSettings
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
    GMS_API_KEY: Optional[str] = None
    GMS_BASE_URL: str = "https://gms.ssafy.io/gmsapi/api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-5-nano"
    OPENAI_MAX_TOKENS: int = 4000
    OPENAI_TEMPERATURE: float = 0.3
    
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