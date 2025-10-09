from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SpendingByCategory(BaseModel):
    category: str
    amount: float
    percentage: float
    transaction_count: int


class MonthlyTrend(BaseModel):
    month: str
    total_spending: float
    income: float
    net_savings: float


class MerchantAnalysis(BaseModel):
    merchant_name: str
    total_spent: float
    frequency: int
    average_transaction: float


class FinancialSummary(BaseModel):
    total_income: float
    total_expenses: float
    net_savings: float
    average_daily_spending: float
    largest_expense: Dict[str, Any]
    most_frequent_merchant_name: str


class AnalysisResult(BaseModel):
    summary: FinancialSummary
    spending_by_category: List[SpendingByCategory]
    monthly_trends: List[MonthlyTrend]
    top_merchants: List[MerchantAnalysis]
    insights: List[str]
    analysis_period: Dict[str, str]


class AnalysisResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    file_info: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AnalysisJob(BaseModel):
    job_id: str
    status: JobStatus
    progress: float = Field(ge=0.0, le=100.0)
    message: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None