from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api.router import api_router
from app.core.config import settings
from app.models.database import init_db, engine as async_engine
from app.db.database import engine as sync_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup and cleanup on shutdown"""
    import sys
    from sqlalchemy import text

    # Validate environment variables
    logger.info("Validating environment variables...")

    missing_vars = []
    required_vars = {
        'DATABASE_URL': settings.DATABASE_URL,
        'REDIS_HOST': settings.REDIS_HOST,
        'REDIS_PORT': settings.REDIS_PORT,
        'REDIS_DB': settings.REDIS_DB,
        'MINIO_ENDPOINT': settings.MINIO_ENDPOINT,
        'MINIO_ACCESS_KEY': settings.MINIO_ACCESS_KEY,
        'MINIO_SECRET_KEY': settings.MINIO_SECRET_KEY,
        'MINIO_BUCKET': settings.MINIO_BUCKET,
    }

    for var_name, var_value in required_vars.items():
        if var_value is None or var_value == "":
            missing_vars.append(var_name)

    if missing_vars:
        error_message = (
            f"\n{'='*60}\n"
            f"❌ CONFIGURATION ERROR - Analysis Service\n"
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

    # Test database connection
    logger.info("Testing database connection...")
    try:
        from app.db.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful")
    except Exception as e:
        error_message = (
            f"\n{'='*60}\n"
            f"❌ DATABASE CONNECTION ERROR\n"
            f"{'='*60}\n"
            f"Failed to connect to database.\n\n"
            f"Error: {str(e)}\n\n"
            f"Please check:\n"
            f"1. DATABASE_URL is correctly set in .env\n"
            f"2. MySQL server is running and accessible\n"
            f"3. Network/firewall rules allow connection\n"
            f"4. SSL certificate is valid (if using production)\n"
            f"{'='*60}\n"
        )
        logger.error(error_message)
        sys.exit(1)

    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Graceful shutdown: close database connections (both async and sync engines)
    logger.info("Shutting down...")
    await async_engine.dispose()
    sync_engine.dispose()
    logger.info("Database connections closed")


app = FastAPI(
    title="Data Analysis Service",
    version="1.0.0",
    description="Financial data analysis with Prophet forecasting",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True
    }
)

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

app.include_router(api_router, prefix="/ai")


@app.get("/")
async def root():
    return {
        "service": "Data Analysis",
        "version": "1.0.0",
        "endpoints": {
            "start_analysis": "POST /ai/data",
            "get_predictions": "GET /ai/data/leak",
            "get_baseline": "GET /ai/data/baseline",
            "get_doojo": "GET /ai/data/doojo (requires JWT)"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "analysis"}