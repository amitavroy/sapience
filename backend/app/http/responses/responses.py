"""
Response models for API endpoints.

This module contains all Pydantic response models used across the application.
Models are organized by functionality and can be grouped together as needed.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class HealthResponse(BaseModel):
    """
    Health check response model containing system status information.

    Attributes:
        status: Current health status of the API
        timestamp: When the health check was performed
        version: API version
        python_version: Python runtime version
        platform: Operating system platform information
    """

    status: str
    timestamp: datetime
    version: str
    python_version: str
    platform: str


class FileUploadResponse(BaseModel):
    """
    File upload response model containing upload details.

    Attributes:
        success: Whether the upload was successful
        url: Public URL of the uploaded file
        filename: Original filename
        size: File size in bytes
        content_type: MIME type of the file
        upload_timestamp: When the file was uploaded
    """

    success: bool
    url: str
    filename: str
    size: int
    content_type: str
    upload_timestamp: datetime
