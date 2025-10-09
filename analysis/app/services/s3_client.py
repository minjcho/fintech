"""
S3/MinIO client for fetching CSV files
"""
import boto3
from botocore.client import Config
import pandas as pd
import io
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Client:
    """S3/MinIO client for fetching CSV files"""
    
    def __init__(self):
        """Initialize S3 client"""
        try:
            # Parse endpoint
            endpoint = settings.MINIO_ENDPOINT
            if not endpoint.startswith(('http://', 'https://')):
                endpoint = f"{'https' if settings.MINIO_SECURE else 'http'}://{endpoint}"
            
            # Create S3 client
            self.s3_client = boto3.client(
                's3',
                endpoint_url=endpoint,
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(signature_version='s3v4'),
                verify=settings.VERIFY_SSL
            )
            
            self.bucket_name = settings.MINIO_BUCKET
            logger.info(f"Connected to S3/MinIO at {endpoint}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    async def fetch_csv_data(self, file_id: str, s3_key: str) -> Optional[pd.DataFrame]:
        """
        Fetch CSV data from S3/MinIO
        
        Args:
            file_id: File identifier
            s3_key: S3 object key
            
        Returns:
            DataFrame with CSV data or None
        """
        try:
            # Get object from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            # Read CSV data
            csv_content = response['Body'].read()
            df = pd.read_csv(io.BytesIO(csv_content))
            
            logger.info(f"Fetched CSV data for file_id {file_id}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch CSV from S3: {e}")
            return None