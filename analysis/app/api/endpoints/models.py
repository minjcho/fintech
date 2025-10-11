"""
Pydantic models for data analysis endpoints
"""
from typing import Optional, Dict, List
from pydantic import BaseModel


class LeakCalculationResponse(BaseModel):
    """Response model for leak calculation"""
    file_id: str
    year: int
    month: int
    total_leak: float
    message: str


class LeakDataResponse(BaseModel):
    """Response model for leak data"""
    file_id: str
    year: int
    month: int
    leak_amount: float
    transactions_count: int
    details: dict


class CategoryDoojo(BaseModel):
    """두꺼비 조언 카테고리별 데이터"""
    min: float
    max: float
    current: float
    real: Optional[float] = None
    result: Optional[bool] = None
    avg: float


class MostSpentDetail(BaseModel):
    """최대 지출 거래 정보"""
    merchant: str
    amount: float
    date: str
    msg: Optional[str] = None


class MostFrequentDetail(BaseModel):
    """최다 이용 가맹점 정보"""
    merchant: str
    count: int
    total_amount: float
    msg: Optional[str] = None


class CategoryDetail(BaseModel):
    """카테고리별 상세 분석"""
    most_spent: MostSpentDetail
    most_frequent: MostFrequentDetail


class DoojoMonthData(BaseModel):
    """두꺼비 조언 월별 데이터"""
    month: int
    year: int
    categories_count: int
    categories_prediction: Dict[str, CategoryDoojo]
    categories_detail: Dict[str, CategoryDetail]


class DoojoResponse(BaseModel):
    """두꺼비 조언 응답 모델"""
    file_id: str
    doojo: List[DoojoMonthData]
