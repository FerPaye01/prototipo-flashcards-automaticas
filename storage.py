import os
import boto3
from botocore.config import Config
from typing import BinaryIO, Optional

class S3Manager:
    def __init__(self):
        self.endpoint_url = os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566")
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "flashcards-media")
        self.region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
            region_name=self.region,
            config=Config(s3={'addressing_style': 'path'})
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except:
            print(f"📦 Bucket {self.bucket_name} not found. Creating...")
            self.s3_client.create_bucket(Bucket=self.bucket_name)

    async def upload_file(self, file_content: BinaryIO, object_name: str) -> bool:
        """Sube un archivo a S3 (LocalStack)."""
        try:
            self.s3_client.upload_fileobj(file_content, self.bucket_name, object_name)
            return True
        except Exception as e:
            print(f"❌ Error uploading to S3: {e}")
            return False

    def get_file_url(self, object_name: str) -> Optional[str]:
        """Genera una URL para acceder al archivo (mock en LocalStack)."""
        return f"{self.endpoint_url}/{self.bucket_name}/{object_name}"

storage_manager = S3Manager()
