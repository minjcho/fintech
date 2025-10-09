"""
CSV management router with MinIO/S3 storage
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import pandas as pd
import io

from fastapi import APIRouter, File, Form, UploadFile, Query, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import Response

from app.deps.auth import Role, require_admin, require_user
from typing import Literal
from fastapi import Query as QueryParam
from app.models.schemas import (
    FileInfo, StatusResponse, ErrorResponse,
    UploadResponse, Status, ValidationResult, FileInfoWithValidation
)
from app.repos.csv_repo import get_csv_repo, S3CsvRepo
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/ai/csv",
    tags=["CSV Management"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)


def validate_csv_file(file: UploadFile) -> None:
    """
    Validate that the uploaded file is a CSV.

    Args:
        file: Uploaded file to validate

    Raises:
        HTTPException: If file is not a valid CSV
    """
    # Check file extension
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File must have .csv extension"
        )

    # Check content type
    valid_content_types = [
        'text/csv',
        'application/csv',
        'application/vnd.ms-excel',
        'text/plain'  # Sometimes CSV files are uploaded as plain text
    ]

    if file.content_type and file.content_type.lower() not in valid_content_types:
        logger.warning(f"Unusual content type for CSV: {file.content_type}")
        # Allow it but log warning - some browsers send wrong content type


def validate_csv_for_prophet(file_content: bytes) -> Dict[str, Any]:
    """
    Validate CSV content for Prophet analysis requirements.

    Args:
        file_content: Raw CSV file content as bytes

    Returns:
        Dict with validation results and metadata

    Raises:
        HTTPException: If CSV doesn't meet Prophet requirements
    """
    try:
        # Read CSV content
        df = pd.read_csv(io.BytesIO(file_content))

        # Check if DataFrame is empty
        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file is empty"
            )

        # Check required columns
        required_columns = ['transaction_date_time', 'category', 'merchant_name', 'amount']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            available_columns = list(df.columns)
            error_msg = f"Missing required columns: {', '.join(missing_columns)}."
            error_msg += f" Found columns: {', '.join(available_columns)}."
            error_msg += f" Required columns: {', '.join(required_columns)}."

            # Suggest potential matches
            suggestions = []
            for missing in missing_columns:
                for available in available_columns:
                    if missing.lower() in available.lower() or available.lower() in missing.lower():
                        suggestions.append(f"'{available}' might be '{missing}'")

            if suggestions:
                error_msg += f" Possible matches: {'; '.join(suggestions[:3])}."

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # Validate data types and content
        validation_errors = []

        # Check amount column
        try:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            null_amounts = df['amount'].isnull().sum()
            if null_amounts > 0:
                validation_errors.append(f"{null_amounts} rows have invalid amount values")
        except Exception as e:
            validation_errors.append(f"Amount column validation failed: {str(e)}")

        # Check date column
        try:
            df['transaction_date_time'] = pd.to_datetime(df['transaction_date_time'], errors='coerce')
            null_dates = df['transaction_date_time'].isnull().sum()
            if null_dates > 0:
                validation_errors.append(f"{null_dates} rows have invalid date values")
        except Exception as e:
            validation_errors.append(f"Date column validation failed: {str(e)}")

        # Remove rows with null values for calculation
        clean_df = df.dropna(subset=['transaction_date_time', 'amount', 'category'])

        if clean_df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid rows remaining after data cleaning"
            )

        # Check Prophet minimum data requirements
        total_days = (clean_df['transaction_date_time'].max() - clean_df['transaction_date_time'].min()).days + 1
        total_rows = len(clean_df)
        unique_categories = clean_df['category'].nunique()

        # Prophet analysis requirements
        prophet_warnings = []
        prophet_errors = []

        # Check total data requirement (30 days minimum for baseline analysis)
        if total_days < 30:
            prophet_errors.append(f"Insufficient data period: {total_days} days (minimum 30 days required for baseline analysis)")

        # Check if data spans at least 2 months for meaningful predictions
        if total_days < 60:
            prophet_warnings.append(f"Limited data period: {total_days} days. Recommend at least 60 days for accurate predictions.")

        # Check total rows
        if total_rows < 30:
            prophet_errors.append(f"Insufficient transactions: {total_rows} rows (minimum 30 required)")

        # Check category-wise data
        category_analysis = clean_df.groupby('category').agg({
            'transaction_date_time': ['count', 'nunique'],
            'amount': 'sum'
        }).round(2)

        categories_with_insufficient_data = []
        categories_with_warnings = []
        for category in clean_df['category'].unique():
            cat_data = clean_df[clean_df['category'] == category]
            cat_days = cat_data['transaction_date_time'].nunique()
            cat_rows = len(cat_data)

            if cat_rows < 2:
                categories_with_insufficient_data.append(f"'{category}' (only {cat_rows} transaction)")
            elif cat_days < 7:
                categories_with_warnings.append(f"'{category}' ({cat_days} days, {cat_rows} transactions)")

        if categories_with_insufficient_data:
            prophet_errors.append(f"Categories with insufficient data (< 2 transactions): {', '.join(categories_with_insufficient_data[:3])}{'...' if len(categories_with_insufficient_data) > 3 else ''}")

        if categories_with_warnings:
            prophet_warnings.append(f"Categories with limited data (< 7 days): {', '.join(categories_with_warnings[:3])}{'...' if len(categories_with_warnings) > 3 else ''}")

        # Create validation summary
        validation_summary = {
            "status": "valid",
            "total_rows": len(df),
            "valid_rows": len(clean_df),
            "date_range_days": total_days,
            "unique_categories": unique_categories,
            "categories": list(clean_df['category'].unique()),
            "date_range": {
                "start": clean_df['transaction_date_time'].min().isoformat(),
                "end": clean_df['transaction_date_time'].max().isoformat()
            },
            "total_amount": float(clean_df['amount'].sum()),
            "validation_errors": validation_errors,
            "prophet_warnings": prophet_warnings,
            "prophet_errors": prophet_errors,
            "prophet_ready": len(prophet_errors) == 0 and total_days >= 2 and len(clean_df) >= 2,
            "baseline_ready": len(prophet_errors) == 0 and total_days >= 30 and len(clean_df) >= 30
        }

        # If there are critical errors, raise exception with detailed information
        if validation_errors or prophet_errors:
            error_summary = []

            # Add basic file info
            error_summary.append(f"File: {df.shape[0]} total rows, {len(clean_df)} valid rows")

            # Add validation errors
            if validation_errors:
                error_summary.append(f"Data Issues: {'; '.join(validation_errors)}")

            # Add Prophet-specific errors
            if prophet_errors:
                error_summary.append(f"Prophet Requirements: {'; '.join(prophet_errors)}")

            # Add helpful context
            if total_days < 30:
                error_summary.append(f"Date Range: {total_days} days (need ≥30 for baseline analysis)")

            if total_rows < 30:
                error_summary.append(f"Transaction Count: {total_rows} rows (recommend ≥30 for reliable predictions)")

            # Show categories with insufficient data
            insufficient_categories = []
            for category in clean_df['category'].unique():
                cat_data = clean_df[clean_df['category'] == category]
                cat_days = cat_data['transaction_date_time'].nunique()
                if cat_days < 7:
                    insufficient_categories.append(f"'{category}' ({cat_days} days)")

            if insufficient_categories:
                error_summary.append(f"Categories with <7 days data: {', '.join(insufficient_categories[:5])}{'...' if len(insufficient_categories) > 5 else ''}")

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV validation failed. {' | '.join(error_summary)}"
            )

        return validation_summary

    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or contains no readable data. Please check your file format."
        )
    except pd.errors.ParserError as e:
        error_msg = str(e).lower()
        if "tokenizing" in error_msg or "delimiter" in error_msg:
            detail = "CSV format error: File appears to have inconsistent columns or incorrect delimiters. Please ensure all rows have the same number of columns separated by commas."
        elif "unicode" in error_msg or "encoding" in error_msg:
            detail = "CSV encoding error: File contains invalid characters. Please save your file as UTF-8 encoded CSV."
        else:
            detail = f"CSV parsing error: {str(e)}. Please check your file format and ensure it's a valid CSV."

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File could not be read. Please check the file exists and is accessible."
        )
    except MemoryError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV file is too large to process. Please reduce file size or split into smaller files."
        )
    except Exception as e:
        logger.error(f"CSV validation error: {str(e)}")
        error_type = type(e).__name__
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected validation error ({error_type}): {str(e)}. Please contact support if this issue persists."
        )


async def auto_clear_status(
    csv_repo: S3CsvRepo,
    file_id: str,
    delay_seconds: int
):
    """
    Background task to automatically clear status after delay.
    
    Args:
        csv_repo: Repository instance
        file_id: File ID to clear status for
        delay_seconds: Delay before clearing
    """
    await asyncio.sleep(delay_seconds)
    await csv_repo.set_status_by_id(file_id, "none")
    logger.info(f"Auto-cleared status for file_id '{file_id}' to 'none'")


@router.post(
    "/upload",
    response_model=FileInfoWithValidation,
    status_code=status.HTTP_202_ACCEPTED,  # Changed to 202 for async processing
    summary="Upload CSV file",
    description="Upload a new CSV file to storage with Prophet analysis validation (Admin only) - Async processing"
)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file to upload"),
    role: Role = Depends(require_admin),
    csv_repo: S3CsvRepo = Depends(get_csv_repo)
) -> FileInfo:
    """
    Upload a new CSV file to MinIO/S3 storage (asynchronous).
    
    Requires admin role.
    Returns immediately with file_id and status 'uploading'.
    Upload happens in background. Check status with GET /status endpoint.
    
    Args:
        background_tasks: FastAPI background tasks
        file: CSV file to upload
        role: Current user role (must be admin)
        csv_repo: Repository instance
    
    Returns:
        FileInfo with file_id (status will be 'uploading')
    
    Raises:
        400: If file already exists
        401: If not authenticated
        403: If not admin
        415: If not a CSV file
        500: For storage errors
    """
    # Validate CSV file format
    validate_csv_file(file)

    try:
        # Read file content into memory for validation and processing
        file_content = await file.read()

        # Validate CSV content for Prophet analysis
        validation_result = validate_csv_for_prophet(file_content)

        # Prepare upload (creates metadata and returns immediately)
        # No longer checking for duplicate filenames - each upload gets unique file_id
        file_info = await csv_repo.prepare_upload(
            file_name=file.filename
        )

        # Schedule background upload with validation metadata
        background_tasks.add_task(
            csv_repo.upload_file_background,
            file_name=file.filename,
            file_content=file_content,
            file_id=file_info.file_id,
            s3_key=file_info.s3_key
        )

        logger.info(f"Admin '{role}' initiated upload for CSV file '{file.filename}' with ID '{file_info.file_id}'")
        logger.info(f"CSV validation for '{file.filename}': {validation_result['valid_rows']}/{validation_result['total_rows']} valid rows, "
                   f"Prophet ready: {validation_result['prophet_ready']}, Baseline ready: {validation_result['baseline_ready']}")

        # Create response with validation results
        return FileInfoWithValidation(
            csv_file=file_info.csv_file,
            file_id=file_info.file_id,
            checksum=file_info.checksum,
            size_bytes=file_info.size_bytes,
            uploaded_at=file_info.uploaded_at,
            replaced_at=file_info.replaced_at,
            s3_key=file_info.s3_key,
            s3_url=file_info.s3_url,
            validation=ValidationResult(**validation_result)
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions from validation (with detailed error messages)
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Upload failed for '{file.filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage"
        )


@router.delete(
    "/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete CSV file",
    description="Delete a CSV file from storage by file ID (Admin only)"
)
async def delete_csv(
    file_id: str = Query(..., description="File ID to delete"),
    role: Role = Depends(require_admin),
    csv_repo: S3CsvRepo = Depends(get_csv_repo)
) -> Response:
    """
    Delete a CSV file from MinIO/S3 storage by file ID.
    
    Requires admin role.
    Removes file from storage and clears all metadata/status.
    
    Args:
        file_id: File ID to delete
        role: Current user role (must be admin)
        csv_repo: Repository instance
    
    Returns:
        204 No Content on success
    
    Raises:
        401: If not authenticated
        403: If not admin
        404: If file not found
        409: If file is being processed
        500: For storage errors
    """
    try:
        # Check if file exists
        file_info = await csv_repo.get_file_info_by_id(file_id)
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File with ID '{file_id}' not found"
            )
        
        # Check if file is being processed (optional business logic)
        current_status = await csv_repo.get_status_by_id(file_id)
        if current_status and current_status in ["ingesting", "analyzing"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete file while status is '{current_status}'"
            )
        
        # Delete file
        await csv_repo.delete_file_by_id(file_id)
        
        logger.info(f"Admin '{role}' deleted file with ID '{file_id}' ('{file_info.csv_file}')")
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete failed for file_id '{file_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file from storage"
        )


@router.put(
    "/change",
    response_model=FileInfo,
    status_code=status.HTTP_202_ACCEPTED,  # Changed to 202 for async
    summary="Replace CSV file",
    description="Replace an existing CSV file by file ID (Admin only) - Async processing"
)
async def replace_csv(
    background_tasks: BackgroundTasks,
    file_id: str = Query(..., description="File ID to replace"),
    file: UploadFile = File(..., description="New CSV file"),
    role: Role = Depends(require_admin),
    csv_repo: S3CsvRepo = Depends(get_csv_repo)
) -> FileInfo:
    """
    Replace an existing CSV file in MinIO/S3 storage by file ID (asynchronous).
    
    Requires admin role.
    Returns immediately with status 'uploading'.
    Keeps the same file_id but creates new S3 object.
    
    Args:
        background_tasks: FastAPI background tasks
        file_id: File ID to replace
        file: New CSV file content
        role: Current user role (must be admin)
        csv_repo: Repository instance
    
    Returns:
        FileInfo with same file_id (status will be 'uploading')
    
    Raises:
        401: If not authenticated
        403: If not admin
        404: If original file not found
        409: If file is being processed
        415: If not a CSV file
        500: For storage errors
    """
    # Validate CSV file
    validate_csv_file(file)
    
    try:
        # Check if original file exists
        existing = await csv_repo.get_file_info_by_id(file_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File with ID '{file_id}' not found. Use POST /upload for new files."
            )
        
        # Check if file is being processed
        current_status = await csv_repo.get_status_by_id(file_id)
        if current_status and current_status in ["uploading", "ingesting", "analyzing"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot replace file while status is '{current_status}'"
            )
        
        # Prepare replace (returns immediately)
        file_info, old_s3_key = await csv_repo.prepare_replace_by_id(file_id)
        
        # Read file content for background processing
        file_content = await file.read()
        
        # Schedule background replace
        background_tasks.add_task(
            csv_repo.replace_file_background,
            file_name=existing.csv_file,
            file_content=file_content,
            file_id=file_info.file_id,
            s3_key=file_info.s3_key,
            old_s3_key=old_s3_key
        )
        
        logger.info(f"Admin '{role}' initiated replace for file ID '{file_id}' ('{existing.csv_file}')")
        
        return file_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Replace failed for file_id '{file_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to replace file in storage"
        )


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Get CSV processing status",
    description="Get the current processing status of a CSV file by file ID (Admin/User)"
)
async def get_csv_status(
    file_id: str = Query(..., description="File ID to check status"),
    role: Role = Depends(require_user),  # Both admin and user allowed
    csv_repo: S3CsvRepo = Depends(get_csv_repo)
) -> StatusResponse:
    """
    Get the current processing status of a CSV file by file ID.
    
    Accessible to both admin and regular users.
    Returns one of: 'uploading', 'ingesting', 'analyzing', 'none'
    
    Args:
        file_id: File ID to check
        role: Current user role
        csv_repo: Repository instance
    
    Returns:
        StatusResponse with current status
    
    Raises:
        401: If not authenticated
        404: If file not found
        500: For storage errors
    """
    try:
        # Check if file exists
        file_info = await csv_repo.get_file_info_by_id(file_id)
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File with ID '{file_id}' not found"
            )
        
        # Get current status
        current_status = await csv_repo.get_status_by_id(file_id)
        if not current_status:
            current_status = "none"
        
        # Build response
        response = StatusResponse(
            csv_file=file_info.csv_file,
            status=current_status,
            progress=None,  # Could be calculated based on status
            last_updated=datetime.now(timezone.utc).isoformat(),
            details=None  # Could add processing details
        )
        
        logger.info(f"User '{role}' checked status for file_id '{file_id}': {current_status}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed for file_id '{file_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file status"
        )


@router.get(
    "/file",
    response_model=FileInfo,
    summary="Get file info",
    description="Get file information by file ID (Admin/User)"
)
async def get_file_info(
    file_id: str = Query(..., description="File ID to retrieve"),
    role: Role = Depends(require_user),
    csv_repo: S3CsvRepo = Depends(get_csv_repo)
) -> FileInfo:
    """
    Get file information by file ID.
    
    Args:
        file_id: File ID to retrieve
        role: Current user role
        csv_repo: Repository instance
    
    Returns:
        FileInfo with file details
    
    Raises:
        401: If not authenticated
        404: If file not found
    """
    file_info = await csv_repo.get_file_info_by_id(file_id)
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found"
        )
    
    logger.info(f"User '{role}' retrieved info for file_id '{file_id}'")
    return file_info


# Additional utility endpoints (optional)

@router.get(
    "/list",
    summary="List CSV files",
    description="List all uploaded CSV files (Admin only)",
    include_in_schema=False  # Hidden utility endpoint
)
async def list_csv_files(
    role: Role = Depends(require_admin),
    csv_repo: S3CsvRepo = Depends(get_csv_repo)
) -> dict:
    """
    List all CSV files (utility endpoint for debugging).
    
    Args:
        role: Current user role (must be admin)
        csv_repo: Repository instance
    
    Returns:
        Dictionary with file list
    """
    # Get all files from Redis using file_id based storage
    all_files = csv_repo.redis_client.list_all_files()
    files = []
    for file_id, metadata in all_files.items():
        status = await csv_repo.get_status_by_id(file_id)
        files.append({
            "file_id": file_id,
            "csv_file": metadata.get('csv_file'),
            "status": status or "none",
            "size_bytes": metadata.get('size_bytes'),
            "uploaded_at": metadata.get('uploaded_at'),
            "replaced_at": metadata.get('replaced_at')
        })
    
    return {
        "total": len(files),
        "files": files
    }