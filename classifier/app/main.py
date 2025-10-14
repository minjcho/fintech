from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

from app.api.router import api_router
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Expense Classifier Service",
    version="1.0.0",
    description="AI-powered expense categorization service"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/ai")


@app.on_event("startup")
async def validate_environment():
    """Validate all required environment variables on startup"""
    logger.info("Validating environment variables...")

    missing_vars = []

    # Check required variables
    required_vars = {
        'GMS_API_KEY': settings.GMS_API_KEY,
        'GMS_BASE_URL': settings.GMS_BASE_URL,
    }

    for var_name, var_value in required_vars.items():
        if not var_value:
            missing_vars.append(var_name)

    if missing_vars:
        error_message = (
            f"\n{'='*60}\n"
            f"❌ CONFIGURATION ERROR - Classifier Service\n"
            f"{'='*60}\n"
            f"Missing required environment variables:\n"
        )
        for var in missing_vars:
            error_message += f"  - {var}\n"
        error_message += (
            f"\nPlease:\n"
            f"1. Copy .env.example to .env\n"
            f"2. Fill in the required values\n"
            f"3. Restart the service\n"
            f"{'='*60}\n"
        )

        logger.error(error_message)
        sys.exit(1)

    logger.info("✅ All required environment variables are set")


@app.get("/")
async def root():
    return {
        "service": "Expense Classifier",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "classifier"}