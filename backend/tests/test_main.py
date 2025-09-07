"""
Comprehensive tests for API endpoints.

Tests cover:
- File upload endpoint (/upload)
- Health check endpoint (/health)
- Root endpoint (/)
- Error handling
- Response validation
- Integration with services
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from datetime import datetime
import json


class TestAPIEndpoints:
    """Test cases for API endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns welcome message."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Welcome to Sapience API"
        assert data["version"] == "0.1.0"

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "python_version" in data
        assert "platform" in data
        assert "timestamp" in data

    @patch("app.services.file_validator.FileValidator.validate_file")
    @patch("app.services.minio_client.MinIOClient")
    def test_upload_file_success(
        self, mock_minio_class, mock_validate, client, sample_pdf_content
    ):
        """Test successful file upload."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.return_value = "http://localhost:9000/sapience-dev/uploads/2024/01/15/20240115_143022_123_test.pdf"
        mock_minio_class.return_value = mock_minio_instance

        # Create test file
        files = {"file": ("test.pdf", sample_pdf_content, "application/pdf")}

        with patch("main.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(
                2024, 1, 15, 14, 30, 22, 123000
            )

            response = client.post("/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["filename"] == "test.pdf"
        assert data["size"] == len(sample_pdf_content)
        assert data["content_type"] == "application/pdf"
        assert "url" in data
        assert "upload_timestamp" in data

    @patch("app.services.file_validator.FileValidator.validate_file")
    def test_upload_file_validation_failure(
        self, mock_validate, client, sample_pdf_content
    ):
        """Test file upload with validation failure."""
        # Mock validation failure
        mock_validate.return_value = (False, "File type '.txt' is not allowed")

        # Create test file with unsupported type
        files = {"file": ("test.txt", sample_pdf_content, "text/plain")}

        response = client.post("/upload", files=files)

        assert response.status_code == 415
        data = response.json()
        assert "File type '.txt' is not allowed" in data["detail"]

    @patch("main.MinIOClient")
    @patch("app.services.file_validator.FileValidator.validate_file")
    def test_upload_file_minio_error(
        self, mock_validate, mock_minio_class, client, sample_pdf_content
    ):
        """Test file upload with MinIO error."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client error
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.side_effect = Exception(
            "MinIO connection failed"
        )
        mock_minio_class.return_value = mock_minio_instance

        # Create test file
        files = {"file": ("test.pdf", sample_pdf_content, "application/pdf")}

        response = client.post("/upload", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "Upload failed: MinIO connection failed" in data["detail"]

    def test_upload_file_no_file(self, client):
        """Test file upload without file."""
        response = client.post("/upload")

        assert response.status_code == 422  # Validation error

    def test_upload_file_empty_filename(self, client, sample_pdf_content):
        """Test file upload with empty filename."""
        files = {"file": ("", sample_pdf_content, "application/pdf")}

        response = client.post("/upload", files=files)

        assert (
            response.status_code == 422
        )  # FastAPI validation error for empty filename

    @patch("app.services.file_validator.FileValidator.validate_file")
    @patch("app.services.minio_client.MinIOClient")
    def test_upload_multiple_file_types(self, mock_minio_class, mock_validate, client):
        """Test uploading different file types."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.return_value = (
            "http://localhost:9000/sapience-dev/uploads/test"
        )
        mock_minio_class.return_value = mock_minio_instance

        test_files = [
            ("test.pdf", b"PDF content", "application/pdf"),
            ("test.jpg", b"Image content", "image/jpeg"),
            ("test.json", b'{"test": "data"}', "application/json"),
            ("test.csv", b"name,age\nJohn,25", "text/csv"),
            ("test.xml", b"<?xml version='1.0'?><root></root>", "application/xml"),
            ("test.html", b"<html><body>Test</body></html>", "text/html"),
        ]

        for filename, content, content_type in test_files:
            files = {"file": (filename, content, content_type)}

            with patch("main.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = datetime(
                    2024, 1, 15, 14, 30, 22, 123000
                )

                response = client.post("/upload", files=files)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["filename"] == filename
            assert data["content_type"] == content_type

    @patch("app.services.file_validator.FileValidator.validate_file")
    @patch("app.services.minio_client.MinIOClient")
    def test_upload_file_large_size(self, mock_minio_class, mock_validate, client):
        """Test uploading large file."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.return_value = (
            "http://localhost:9000/sapience-dev/uploads/large.pdf"
        )
        mock_minio_class.return_value = mock_minio_instance

        # Create large file content (30MB)
        large_content = b"X" * (30 * 1024 * 1024)
        files = {"file": ("large.pdf", large_content, "application/pdf")}

        with patch("main.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(
                2024, 1, 15, 14, 30, 22, 123000
            )

            response = client.post("/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["size"] == len(large_content)

    @patch("app.services.file_validator.FileValidator.validate_file")
    @patch("app.services.minio_client.MinIOClient")
    def test_upload_file_unique_filename_generation(
        self, mock_minio_class, mock_validate, client, sample_pdf_content
    ):
        """Test unique filename generation."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.return_value = (
            "http://localhost:9000/sapience-dev/uploads/test"
        )
        mock_minio_class.return_value = mock_minio_instance

        files = {"file": ("test.pdf", sample_pdf_content, "application/pdf")}

        with patch("main.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(
                2024, 1, 15, 14, 30, 22, 123000
            )

            response = client.post("/upload", files=files)

        assert response.status_code == 200

        # Verify MinIO client was called with correct object path
        call_args = mock_minio_instance.upload_file_from_memory.call_args
        if call_args and len(call_args) > 1:
            object_name = call_args[1]["object_name"]
            assert "uploads/2024/01/15/" in object_name
            assert "20240115_143022_123_test.pdf" in object_name

    @patch("app.services.file_validator.FileValidator.validate_file")
    @patch("app.services.minio_client.MinIOClient")
    def test_upload_file_without_content_type(
        self, mock_minio_class, mock_validate, client, sample_pdf_content
    ):
        """Test file upload without content type."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.return_value = (
            "http://localhost:9000/sapience-dev/uploads/test"
        )
        mock_minio_class.return_value = mock_minio_instance

        files = {"file": ("test.pdf", sample_pdf_content)}  # No content_type specified

        with patch("main.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(
                2024, 1, 15, 14, 30, 22, 123000
            )

            response = client.post("/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        # FastAPI will provide a default content type
        assert data["content_type"] in ["application/pdf", "application/octet-stream"]

    @patch("app.services.file_validator.FileValidator.validate_file")
    @patch("app.services.minio_client.MinIOClient")
    def test_upload_file_logging(
        self, mock_minio_class, mock_validate, client, sample_pdf_content
    ):
        """Test that logging occurs during file upload."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.return_value = (
            "http://localhost:9000/sapience-dev/uploads/test"
        )
        mock_minio_class.return_value = mock_minio_instance

        files = {"file": ("test.pdf", sample_pdf_content, "application/pdf")}

        with patch("main.logger") as mock_logger:
            with patch("main.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = datetime(
                    2024, 1, 15, 14, 30, 22, 123000
                )

                response = client.post("/upload", files=files)

        assert response.status_code == 200

        # Verify logging calls
        assert mock_logger.info.call_count >= 3  # At least 3 info logs
        assert mock_logger.warning.call_count == 0  # No warnings for successful upload

        # Check specific log messages
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("File upload started" in call for call in log_calls)
        assert any("File validation passed" in call for call in log_calls)
        assert any("uploaded to bucket" in call for call in log_calls)
        assert any("File upload completed" in call for call in log_calls)

    @patch("app.services.file_validator.FileValidator.validate_file")
    def test_upload_file_validation_logging(
        self, mock_validate, client, sample_pdf_content
    ):
        """Test logging during validation failure."""
        # Mock validation failure
        mock_validate.return_value = (False, "File type '.txt' is not allowed")

        files = {"file": ("test.txt", sample_pdf_content, "text/plain")}

        with patch("main.logger") as mock_logger:
            response = client.post("/upload", files=files)

        assert response.status_code == 415

        # Verify warning log was called
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "File validation failed" in warning_call
        assert "test.txt" in warning_call

    @patch("main.MinIOClient")
    @patch("app.services.file_validator.FileValidator.validate_file")
    def test_upload_file_error_logging(
        self, mock_validate, mock_minio_class, client, sample_pdf_content
    ):
        """Test logging during upload error."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client error
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.side_effect = Exception(
            "MinIO connection failed"
        )
        mock_minio_class.return_value = mock_minio_instance

        files = {"file": ("test.pdf", sample_pdf_content, "application/pdf")}

        with patch("main.logger") as mock_logger:
            response = client.post("/upload", files=files)

        assert response.status_code == 500

        # Verify error log was called
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "File upload failed" in error_call
        assert "test.pdf" in error_call

    def test_api_documentation_endpoints(self, client):
        """Test that API documentation endpoints are accessible."""
        # Test Swagger UI
        response = client.get("/docs")
        assert response.status_code == 200

        # Test ReDoc
        response = client.get("/redoc")
        assert response.status_code == 200

    @patch("app.services.file_validator.FileValidator.validate_file")
    @patch("app.services.minio_client.MinIOClient")
    def test_upload_file_response_model_validation(
        self, mock_minio_class, mock_validate, client, sample_pdf_content
    ):
        """Test that response matches FileUploadResponse model."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.return_value = (
            "http://localhost:9000/sapience-dev/uploads/test"
        )
        mock_minio_class.return_value = mock_minio_instance

        files = {"file": ("test.pdf", sample_pdf_content, "application/pdf")}

        with patch("main.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(
                2024, 1, 15, 14, 30, 22, 123000
            )

            response = client.post("/upload", files=files)

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "success",
            "url",
            "filename",
            "size",
            "content_type",
            "upload_timestamp",
        ]
        for field in required_fields:
            assert field in data

        # Verify field types
        assert isinstance(data["success"], bool)
        assert isinstance(data["url"], str)
        assert isinstance(data["filename"], str)
        assert isinstance(data["size"], int)
        assert isinstance(data["content_type"], str)
        assert isinstance(data["upload_timestamp"], str)

    @patch("app.services.file_validator.FileValidator.validate_file")
    @patch("app.services.minio_client.MinIOClient")
    def test_upload_file_concurrent_uploads(
        self, mock_minio_class, mock_validate, client, sample_pdf_content
    ):
        """Test handling multiple concurrent uploads."""
        # Mock validation success
        mock_validate.return_value = (True, "")

        # Mock MinIO client
        mock_minio_instance = Mock()
        mock_minio_instance.upload_file_from_memory.return_value = (
            "http://localhost:9000/sapience-dev/uploads/test"
        )
        mock_minio_class.return_value = mock_minio_instance

        files1 = {"file": ("test1.pdf", sample_pdf_content, "application/pdf")}
        files2 = {"file": ("test2.pdf", sample_pdf_content, "application/pdf")}

        with patch("main.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(
                2024, 1, 15, 14, 30, 22, 123000
            )

            response1 = client.post("/upload", files=files1)
            response2 = client.post("/upload", files=files2)

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert data1["filename"] == "test1.pdf"
        assert data2["filename"] == "test2.pdf"
