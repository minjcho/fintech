"""
Doojo analysis endpoints - Category spending analysis with GPT-5-nano advice
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status
from datetime import datetime
import pandas as pd
import logging
import os
from openai import OpenAI

from app.services.redis_client import RedisClient
from app.services.s3_client import S3Client
from app.api.endpoints.models import (
    DoojoResponse,
    DoojoMonthData,
    CategoryDoojo,
    CategoryDetail,
    MostSpentDetail,
    MostFrequentDetail
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
redis_client = RedisClient()
s3_client = S3Client()


@router.get(
    "/doojo",
    response_model=DoojoResponse,
    summary="Get doojo (stamp breaking) data",
    description="Get category spending analysis with min/max ranges from S3 CSV data",
    responses={
        404: {"description": "File not found or no analysis data"}
    }
)
async def get_doojo_data(
    file_id: str = Query(..., description="File ID for CSV data"),
    year: Optional[int] = Query(None, description="Year to query (default: current year)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month to query (1-12, default: current month)")
) -> DoojoResponse:
    """
    두꺼비 조언 데이터 조회 - S3 CSV 파일 기반 카테고리별 지출 분석

    S3 CSV 데이터에서 카테고리별 지출 통계를 계산하여 제공합니다.

    각 카테고리별로 다음 정보를 제공:
    - min: 과거 12개월간 최소 지출액
    - max: 과거 12개월간 최대 지출액
    - current: 이번달 누수 기준 (평균값)
    - real: 실제 사용 금액
    - result: real > current 이면 true, 아니면 false
    - avg: 평균 지출액

    Args:
        file_id: CSV 파일 ID
        year: 조회할 연도 (선택, 기본값: 현재 연도)
        month: 조회할 월 (선택, 1-12, 기본값: 현재 월)

    Returns:
        DoojoResponse with category analysis from S3 CSV

    Raises:
        404: File not found or no analysis data
    """
    # Check if analysis is in progress
    analysis_status = redis_client.get_csv_status(file_id)
    if analysis_status == 'analyzing':
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Analysis is still in progress. Please try again later."
        )

    # Get file metadata from Redis
    file_metadata = redis_client.get_file_metadata(file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found"
        )

    s3_key = file_metadata.get('s3_key')
    if not s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No S3 key found for file {file_id}"
        )

    # Fetch CSV data from S3
    csv_data = await s3_client.fetch_csv_data(file_id, s3_key)
    if csv_data is None or csv_data.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for file {file_id}"
        )

    # Rename merchant_name to merchant for consistency
    if 'merchant_name' in csv_data.columns:
        csv_data = csv_data.rename(columns={'merchant_name': 'merchant'})

    # Use provided year/month or default to current
    current_date = datetime.now()
    query_year = year if year is not None else current_date.year
    query_month = month if month is not None else current_date.month

    # Ensure transaction_date_time is datetime
    csv_data['transaction_date_time'] = pd.to_datetime(csv_data['transaction_date_time'])

    # Add year_month column
    csv_data['year_month'] = csv_data['transaction_date_time'].dt.to_period('M')

    # Calculate monthly spending per category
    monthly_spending = csv_data.groupby(['category', 'year_month'])['amount'].sum().reset_index()

    # Initialize result structures
    categories_prediction = {}
    categories_detail = {}

    # Get current month data
    current_month_data = csv_data[
        (csv_data['transaction_date_time'].dt.year == query_year) &
        (csv_data['transaction_date_time'].dt.month == query_month)
    ]

    # Initialize OpenAI client for message generation
    api_key = os.getenv('GMS_API_KEY')
    if not api_key:
        logger.error("GMS_API_KEY not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI advice service not configured. Please contact administrator."
        )

    gms_client = OpenAI(
        api_key=api_key,
        base_url=os.getenv('GMS_BASE_URL', 'https://gms.ssafy.io/gmsapi/api.openai.com/v1')
    )

    def generate_merchant_message(category: str, merchant: str, message_type: str, amount: float = None, count: int = None) -> str:
        """Generate personalized advice message using GPT-5-nano"""
        try:
            if message_type == 'most_spent':
                prompt = f"{category} 카테고리 '{merchant}'에서 {amount:,.0f}원 지출했어. 한 줄로 조언해줘 (반말, 이모지 없이)"
            else:  # most_frequent
                prompt = f"{category} 카테고리 '{merchant}'에 {count}회 방문해서 총 {amount:,.0f}원 썼어. 한 줄로 조언해줘 (반말, 이모지 없이)"

            response = gms_client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate message for {merchant}: {e}")
            # Return fallback message instead of None
            if message_type == 'most_spent':
                return f"{merchant}에서 {amount:,.0f}원 지출했네. 지출 패턴을 확인해보자."
            else:
                return f"{merchant}에 {count}회 방문했네. 자주 가는 곳이니 할인 혜택을 찾아보는 것도 좋을 것 같아."

    # Process each category
    for category in csv_data['category'].unique():
        # Skip "보험 / 세금" category
        if category == "보험 / 세금":
            continue

        # Calculate min/max/avg from monthly spending
        cat_monthly = monthly_spending[monthly_spending['category'] == category]['amount'].tolist()
        if not cat_monthly:
            continue

        min_amount = float(min(cat_monthly))
        max_amount = float(max(cat_monthly))
        avg_amount = float(sum(cat_monthly) / len(cat_monthly))

        # Current threshold is the average
        current_threshold = avg_amount

        # Get real amount for current month
        cat_current = current_month_data[current_month_data['category'] == category]
        real_amount = float(cat_current['amount'].sum()) if not cat_current.empty else None

        # Calculate result
        result = None
        if real_amount is not None:
            result = real_amount > current_threshold

        # Build category prediction
        categories_prediction[category] = CategoryDoojo(
            min=min_amount,
            max=max_amount,
            current=current_threshold,
            real=real_amount,
            result=result,
            avg=avg_amount
        )

        # Build category detail (most_spent and most_frequent)
        if not cat_current.empty:
            # Find most spent transaction
            max_txn_idx = cat_current['amount'].idxmax()
            max_txn = cat_current.loc[max_txn_idx]

            # Calculate most frequent merchant
            merchant_counts = cat_current.groupby('merchant').agg({
                'amount': ['count', 'sum']
            }).reset_index()
            merchant_counts.columns = ['merchant', 'count', 'total_amount']
            most_freq_idx = merchant_counts['count'].idxmax()
            most_frequent = merchant_counts.loc[most_freq_idx]

            # Generate personalized messages using GPT-5-nano
            most_spent_msg = generate_merchant_message(
                category=category,
                merchant=str(max_txn['merchant']),
                message_type='most_spent',
                amount=float(max_txn['amount'])
            )

            most_freq_msg = generate_merchant_message(
                category=category,
                merchant=str(most_frequent['merchant']),
                message_type='most_frequent',
                amount=float(most_frequent['total_amount']),
                count=int(most_frequent['count'])
            )

            categories_detail[category] = CategoryDetail(
                most_spent=MostSpentDetail(
                    merchant=str(max_txn['merchant']),
                    amount=float(max_txn['amount']),
                    date=max_txn['transaction_date_time'].isoformat(),
                    msg=most_spent_msg
                ),
                most_frequent=MostFrequentDetail(
                    merchant=str(most_frequent['merchant']),
                    count=int(most_frequent['count']),
                    total_amount=float(most_frequent['total_amount']),
                    msg=most_freq_msg
                )
            )

    # Create month data
    doojo_month = DoojoMonthData(
        month=query_month,
        year=query_year,
        categories_count=len(categories_prediction),
        categories_prediction=categories_prediction,
        categories_detail=categories_detail
    )

    return DoojoResponse(
        file_id=file_id,
        doojo=[doojo_month]
    )
