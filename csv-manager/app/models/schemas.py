"""
Data models and schemas for CSV management
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

# Status enum - simplified states
Status = Literal["uploading", "ingesting", "analyzing", "none"]


class FileInfo(BaseModel):
    """File information and metadata"""
    csv_file: str = Field(..., description="Original filename")
    file_id: str = Field(..., description="Unique file identifier")
    checksum: Optional[str] = Field(None, description="SHA-256 checksum")
    size_bytes: int = Field(..., description="File size in bytes")
    uploaded_at: str = Field(..., description="ISO 8601 UTC timestamp of initial upload")
    replaced_at: Optional[str] = Field(None, description="ISO 8601 UTC timestamp of last replacement")
    s3_key: Optional[str] = Field(None, description="S3 object key")
    s3_url: Optional[str] = Field(None, description="Presigned URL for download")


class StatusResponse(BaseModel):
    """Status response for CSV processing"""
    csv_file: str = Field(..., description="Filename")
    status: Status = Field(..., description="Current processing status")
    progress: Optional[int] = Field(None, description="Progress percentage (0-100)")
    last_updated: Optional[str] = Field(None, description="Last status update timestamp")
    details: Optional[List[str]] = Field(None, description="Additional status details")


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")


class UploadResponse(BaseModel):
    """Response after successful upload"""
    message: str = Field(..., description="Success message")
    file_info: FileInfo = Field(..., description="Uploaded file information")


class DeleteResponse(BaseModel):
    """Response after successful deletion"""
    message: str = Field(..., description="Success message")
    csv_file: str = Field(..., description="Deleted filename")


class ValidationResult(BaseModel):
    """CSV validation result for Prophet analysis"""
    status: str = Field(..., description="Validation status")
    total_rows: int = Field(..., description="Total rows in CSV")
    valid_rows: int = Field(..., description="Valid rows after cleaning")
    date_range_days: int = Field(..., description="Date range in days")
    unique_categories: int = Field(..., description="Number of unique categories")
    categories: List[str] = Field(..., description="List of categories")
    date_range: dict = Field(..., description="Date range start and end")
    total_amount: float = Field(..., description="Total transaction amount")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")
    prophet_warnings: List[str] = Field(default_factory=list, description="Prophet warnings")
    prophet_errors: List[str] = Field(default_factory=list, description="Prophet errors")
    prophet_ready: bool = Field(..., description="Ready for Prophet analysis")
    baseline_ready: bool = Field(..., description="Ready for baseline analysis")


class FileInfoWithValidation(BaseModel):
    """File information with validation results"""
    csv_file: str = Field(..., description="Original filename")
    file_id: str = Field(..., description="Unique file identifier")
    checksum: Optional[str] = Field(None, description="SHA-256 checksum")
    size_bytes: int = Field(..., description="File size in bytes")
    uploaded_at: str = Field(..., description="ISO 8601 UTC timestamp of initial upload")
    replaced_at: Optional[str] = Field(None, description="ISO 8601 UTC timestamp of last replacement")
    s3_key: Optional[str] = Field(None, description="S3 object key")
    s3_url: Optional[str] = Field(None, description="Presigned URL for download")
    validation: ValidationResult = Field(..., description="CSV validation results")