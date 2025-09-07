"""
MinIO Client Example for Sapience Backend

This module provides a simple interface for interacting with MinIO
(S3-compatible object storage) during development.

For production, replace MinIO with AWS S3 or other S3-compatible services.
"""

import os
from typing import Optional
from minio import Minio
from minio.error import S3Error


class MinIOClient:
    """
    MinIO client wrapper for S3-compatible operations.
    """

    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "sapience-dev")

        # Initialize MinIO client
        self.client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=False,  # Set to True for HTTPS
        )

        # Ensure bucket exists
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"✅ Created bucket: {self.bucket_name}")
        except S3Error as e:
            print(f"❌ Error creating bucket: {e}")

    def upload_file(self, file_path: str, object_name: Optional[str] = None) -> str:
        """
        Upload a file to MinIO.

        Args:
            file_path: Path to the file to upload
            object_name: Name for the object in MinIO (defaults to filename)

        Returns:
            URL of the uploaded file
        """
        if not object_name:
            object_name = os.path.basename(file_path)

        try:
            self.client.fput_object(self.bucket_name, object_name, file_path)
            url = f"{self.endpoint}/{self.bucket_name}/{object_name}"
            print(f"✅ Uploaded: {url}")
            return url
        except S3Error as e:
            print(f"❌ Upload error: {e}")
            raise

    def download_file(self, object_name: str, file_path: str):
        """
        Download a file from MinIO.

        Args:
            object_name: Name of the object in MinIO
            file_path: Local path to save the file
        """
        try:
            self.client.fget_object(self.bucket_name, object_name, file_path)
            print(f"✅ Downloaded: {object_name} -> {file_path}")
        except S3Error as e:
            print(f"❌ Download error: {e}")
            raise

    def delete_file(self, object_name: str):
        """
        Delete a file from MinIO.

        Args:
            object_name: Name of the object to delete
        """
        try:
            self.client.remove_object(self.bucket_name, object_name)
            print(f"✅ Deleted: {object_name}")
        except S3Error as e:
            print(f"❌ Delete error: {e}")
            raise

    def list_files(self, prefix: str = "") -> list:
        """
        List files in the bucket.

        Args:
            prefix: Filter files by prefix

        Returns:
            List of object names
        """
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            print(f"❌ List error: {e}")
            return []

    def get_file_url(self, object_name: str) -> str:
        """
        Get the public URL for a file.

        Args:
            object_name: Name of the object

        Returns:
            Public URL of the file
        """
        return f"{self.endpoint}/{self.bucket_name}/{object_name}"
