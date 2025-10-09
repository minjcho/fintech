from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional
from datetime import datetime

from app.models.schemas import (
    SingleClassificationResponse,
    BatchClassificationResponse,
    ClassificationStatus
)
from app.services.classifier_service import ClassifierService

router = APIRouter()


@router.get("")
async def classify_single(
    merchant_name: str = Query(..., description="Merchant name"),
    amount: float = Query(..., description="Transaction amount"),
    transaction_date_time: datetime = Query(..., description="Transaction timestamp in ISO 8601 format"),
    description: Optional[str] = Query(None, description="Optional transaction description"),
    classifier_service: ClassifierService = Depends(lambda: ClassifierService())
):
    """
    카테고리 분류 (단건)

    Classify a single transaction based on merchant_name, amount, and timestamp.

    Example:
    GET /api/ai/classify?merchant_name=스타벅스&amount=4800&transaction_date_time=2025-09-05T10:12:00Z

    Returns:
        Category classification result for the transaction
    """
    try:
        result = await classifier_service.classify_single(
            merchant_name=merchant_name,
            amount=amount,
            timestamp=transaction_date_time,
            description=description
        )

        return SingleClassificationResponse(
            merchant_name=merchant_name,
            amount=amount,
            category=result["category"],
            subcategory=result.get("subcategory"),
            confidence=result["confidence"],
            timestamp=transaction_date_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.post("")
async def classify_batch(
    file_id: str = Query(..., description="File ID from CSV upload"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    classifier_service: ClassifierService = Depends(lambda: ClassifierService())
):
    """
    카테고리 분류 (배치)

    Classify all transactions in the CSV file identified by file_id.
    Processes the file asynchronously and adds category information.

    Example:
    POST /api/ai/classify?file_id=abc-123

    Returns:
        Job ID or status for tracking the classification process
    """
    try:
        import uuid
        from datetime import datetime

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Start background processing
        background_tasks.add_task(
            classifier_service.process_batch,
            job_id=job_id,
            csv_key=file_id,
            options={}
        )

        return BatchClassificationResponse(
            job_id=job_id,
            status="processing",
            message="Batch classification started",
            created_at=datetime.utcnow()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start batch classification: {str(e)}")


@router.get("/download")
async def download_classified_file(
    job_id: str = Query(..., description="Job ID from batch classification"),
    classifier_service: ClassifierService = Depends(lambda: ClassifierService())
):
    """
    카테고리 분류된 파일 다운로드

    Download the CSV file with category classifications added.
    The file must have been previously processed through the classify endpoint.

    Example:
    GET /api/ai/classify/download?job_id=abc-123

    Returns:
        CSV file with category column added to original data
    """
    try:
        import os

        # Check job status
        job = await classifier_service.get_job_status(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        if job.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job not completed yet. Current status: {job.status}"
            )

        # Get result file
        result_file = await classifier_service.get_result_file(job_id)

        if not result_file or not os.path.exists(result_file):
            raise HTTPException(status_code=404, detail="Result file not found")

        # Return file
        return FileResponse(
            path=result_file,
            media_type='text/csv',
            filename=f"classified_{job_id}.csv"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")