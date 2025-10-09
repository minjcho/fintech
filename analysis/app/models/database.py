"""
Database models and connection setup for Analysis Service
"""
from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from datetime import datetime
import os

# Database URL from environment (required)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required. Please set it in .env file")

# For MySQL with aiomysql
ASYNC_DATABASE_URL = DATABASE_URL.replace("mysql+pymysql://", "mysql+aiomysql://")

# SSL configuration for Azure MySQL
import ssl
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Create async engine with SSL config for aiomysql
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,
    connect_args={
        "ssl": ssl_context
    }
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class PredictionResult(Base):
    """Store Prophet prediction results"""
    __tablename__ = "prediction_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(255), nullable=False, index=True)
    prediction_id = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Prediction data
    current_month_actual = Column(Float)  # Actual spending for current month
    current_month_predicted = Column(Float)  # Predicted spending for current month
    next_month_predicted = Column(Float)  # Predicted spending for next month
    
    # Additional metrics
    trend_direction = Column(String(20))  # "increasing", "decreasing", "stable"
    confidence_lower = Column(Float)  # Lower bound of prediction
    confidence_upper = Column(Float)  # Upper bound of prediction
    
    # Metadata
    prediction_metadata = Column(JSON)  # Store additional info like model params
    status = Column(String(20), default="completed")  # "processing", "completed", "failed"
    error_message = Column(String(1000), nullable=True)
    
    # Time period info
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    

class LeakAnalysis(Base):
    """Store leak analysis results"""
    __tablename__ = "leak_analysis"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(255), nullable=False, index=True)
    analysis_id = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Analysis period
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    
    # Leak calculation
    expected_spending = Column(Float)  # Based on budget/average
    actual_spending = Column(Float)
    leak_amount = Column(Float)  # Difference between expected and actual
    leak_percentage = Column(Float)  # Percentage of leak
    
    # Category breakdown
    category_leaks = Column(JSON)  # JSON with category-wise leak analysis
    
    # Recommendations
    recommendations = Column(JSON)  # AI-generated recommendations
    status = Column(String(20), default="completed")


async def init_db():
    """Initialize database tables"""
    from app.db.models import Base as DBBase  # Import from db/models.py
    async with engine.begin() as conn:
        await conn.run_sync(DBBase.metadata.create_all)


async def get_db():
    """Get database session"""
    async with AsyncSessionLocal() as session:
        yield session