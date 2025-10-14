"""
CSV Manager Service - Dedicated service for CSV file management
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

from app.api.endpoints import csv
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CSV Manager Service",
    description="Dedicated service for CSV file upload and management with MinIO/S3 storage",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


@app.on_event("startup")
async def validate_environment():
    """Validate all required environment variables on startup"""
    logger.info("Validating environment variables...")

    missing_vars = []

    # Check required variables
    required_vars = {
        'MINIO_ENDPOINT': settings.MINIO_ENDPOINT,
        'MINIO_ACCESS_KEY': settings.MINIO_ACCESS_KEY,
        'MINIO_SECRET_KEY': settings.MINIO_SECRET_KEY,
        'MINIO_BUCKET': settings.MINIO_BUCKET,
    }

    for var_name, var_value in required_vars.items():
        if not var_value:
            missing_vars.append(var_name)

    if missing_vars:
        error_message = (
            f"\n{'='*60}\n"
            f"❌ CONFIGURATION ERROR - CSV Manager Service\n"
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "https://j13a409.p.ssafy.io",
        "https://j13a409.p.ssafy.io:3002"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include CSV router
app.include_router(csv.router)


@app.get("/")
async def root():
    """Root endpoint showing service information"""
    return {
        "service": "CSV Manager Service",
        "version": "1.0.0",
        "description": "CSV file management with MinIO/S3 storage",
        "endpoints": {
            "upload": "POST /api/ai/csv/upload",
            "delete": "DELETE /api/ai/csv/delete",
            "replace": "PUT /api/ai/csv/change",
            "status": "GET /api/ai/csv/status"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "csv-manager"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)