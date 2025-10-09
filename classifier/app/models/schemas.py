from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExpenseCategory(str, Enum):
    FOOD_DINING = "Food & Dining"
    TRANSPORTATION = "Transportation"
    SHOPPING = "Shopping"
    ENTERTAINMENT = "Entertainment"
    BILLS_UTILITIES = "Bills & Utilities"
    HEALTHCARE = "Healthcare"
    EDUCATION = "Education"
    TRAVEL = "Travel"
    PERSONAL_CARE = "Personal Care"
    BUSINESS = "Business"
    OTHER = "Other"


class SingleClassificationRequest(BaseModel):
    merchant_name: str
    amount: float
    timestamp: Optional[datetime] = None
    description: Optional[str] = None


class SingleClassificationResponse(BaseModel):
    merchant_name: str
    amount: float
    category: str
    subcategory: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: Optional[datetime] = None


class BatchClassificationRequest(BaseModel):
    csv_key: str = Field(..., description="S3 key or file reference for CSV")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    estimated_records: Optional[int] = None


class BatchClassificationResponse(BaseModel):
    job_id: str
    status: str
    message: str
    total_records: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClassificationJob(BaseModel):
    job_id: str
    status: JobStatus
    progress: float = Field(ge=0.0, le=100.0)
    total_records: int
    processed_records: int
    failed_records: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    result_file: Optional[str] = None
    error_message: Optional[str] = None


class ClassificationStatus(BaseModel):
    job_id: str
    status: JobStatus
    progress: float
    message: Optional[str] = None


class ClassificationResult(BaseModel):
    transaction_id: Optional[str] = None
    merchant_name: str
    amount: float
    original_category: Optional[str] = None
    predicted_category: str
    predicted_subcategory: Optional[str] = None
    confidence: float
    timestamp: Optional[datetime] = None


class CategoryMapping(BaseModel):
    category: str
    subcategories: List[str]
    keywords: List[str]
    examples: List[str]


class TrainingRequest(BaseModel):
    training_data_key: str
    model_name: Optional[str] = None
    hyperparameters: Optional[Dict[str, Any]] = None