"""
File validation service for handling file uploads.

This module provides file validation functionality including:
- File type validation
- File size validation
- Content type verification
"""

import logging
from typing import List, Tuple
from fastapi import UploadFile, HTTPException

# Configure logging
logger = logging.getLogger(__name__)

# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes

# Allowed file extensions and their MIME types
ALLOWED_FILE_TYPES = {
    # PDF files
    "pdf": ["application/pdf"],
    # Microsoft Word documents
    "doc": ["application/msword"],
    "docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    # Microsoft Excel documents
    "xls": ["application/vnd.ms-excel"],
    "xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    # Images
    "jpg": ["image/jpeg"],
    "jpeg": ["image/jpeg"],
    "png": ["image/png"],
    "gif": ["image/gif"],
    "bmp": ["image/bmp"],
    "webp": ["image/webp"],
    "svg": ["image/svg+xml"],
    "tiff": ["image/tiff"],
    "tif": ["image/tiff"],
    # HTML files
    "html": ["text/html"],
    "htm": ["text/html"],
    # CSV files
    "csv": ["text/csv", "application/csv"],
    # JSON files
    "json": ["application/json", "text/json"],
    # XML files
    "xml": ["application/xml", "text/xml"],
}


class FileValidationError(Exception):
    """Custom exception for file validation errors."""

    pass


class FileValidator:
    """
    File validation service for uploads.
    """

    @staticmethod
    def validate_file(file: UploadFile) -> Tuple[bool, str]:
        """
        Validate uploaded file for type and size.

        Args:
            file: FastAPI UploadFile object

        Returns:
            Tuple of (is_valid, error_message)

        Raises:
            FileValidationError: If validation fails
        """
        try:
            # Check if file is provided
            if not file.filename:
                error_msg = "No file provided"
                logger.warning(f"File validation failed: {error_msg}")
                return False, error_msg

            # Get file extension
            file_extension = FileValidator._get_file_extension(file.filename)
            if not file_extension:
                error_msg = f"File '{file.filename}' has no extension"
                logger.warning(f"File validation failed: {error_msg}")
                return False, error_msg

            # Check if file type is allowed
            if file_extension.lower() not in ALLOWED_FILE_TYPES:
                error_msg = f"File type '.{file_extension}' is not allowed. Allowed types: {list(ALLOWED_FILE_TYPES.keys())}"
                logger.warning(f"File validation failed: {error_msg}")
                return False, error_msg

            # Check file size
            file_size = FileValidator._get_file_size(file)
            if file_size > MAX_FILE_SIZE:
                error_msg = f"File size {file_size / (1024*1024):.2f}MB exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024)}MB"
                logger.warning(f"File validation failed: {error_msg}")
                return False, error_msg

            # Validate content type
            if file.content_type:
                allowed_mime_types = ALLOWED_FILE_TYPES[file_extension.lower()]
                if file.content_type not in allowed_mime_types:
                    error_msg = f"Content type '{file.content_type}' does not match file extension '.{file_extension}'"
                    logger.warning(f"File validation failed: {error_msg}")
                    return False, error_msg

            logger.info(
                f"File validation passed: '{file.filename}' ({file_size / (1024*1024):.2f}MB, {file.content_type})"
            )
            return True, ""

        except Exception as e:
            error_msg = f"File validation error: {str(e)}"
            logger.error(f"File validation failed: {error_msg}")
            return False, error_msg

    @staticmethod
    def _get_file_extension(filename: str) -> str:
        """
        Extract file extension from filename.

        Args:
            filename: Name of the file

        Returns:
            File extension without dot
        """
        if "." not in filename:
            return ""
        return filename.split(".")[-1].lower()

    @staticmethod
    def _get_file_size(file: UploadFile) -> int:
        """
        Get file size from UploadFile.

        Args:
            file: FastAPI UploadFile object

        Returns:
            File size in bytes
        """
        # Read the file content to get size
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        return size

    @staticmethod
    def get_allowed_file_types() -> List[str]:
        """
        Get list of allowed file extensions.

        Returns:
            List of allowed file extensions
        """
        return list(ALLOWED_FILE_TYPES.keys())

    @staticmethod
    def get_max_file_size_mb() -> float:
        """
        Get maximum file size in MB.

        Returns:
            Maximum file size in MB
        """
        return MAX_FILE_SIZE / (1024 * 1024)
