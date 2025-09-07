"""
Comprehensive tests for MinIOClient service.

Tests cover:
- File upload from memory
- File upload from path
- File download
- File deletion
- File listing
- Error handling
- Bucket operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from minio.error import S3Error
from app.services.minio_client import MinIOClient


class TestMinIOClient:
    """Test cases for MinIOClient class."""

    @patch.dict(
        "os.environ",
        {
            "MINIO_ENDPOINT": "test-minio:9000",
            "MINIO_ACCESS_KEY": "test-key",
            "MINIO_SECRET_KEY": "test-secret",
            "MINIO_BUCKET_NAME": "test-bucket",
        },
    )
    @patch("app.services.minio_client.Minio")
    def test_init_with_environment_variables(self, mock_minio_class):
        """Test MinIOClient initialization with environment variables."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        assert client.endpoint == "test-minio:9000"
        assert client.access_key == "test-key"
        assert client.secret_key == "test-secret"
        assert client.bucket_name == "test-bucket"
        mock_minio_class.assert_called_once_with(
            endpoint="test-minio:9000",
            access_key="test-key",
            secret_key="test-secret",
            secure=False,
        )

    @patch("app.services.minio_client.Minio")
    def test_init_with_default_values(self, mock_minio_class):
        """Test MinIOClient initialization with default values."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        with patch.dict("os.environ", {}, clear=True):
            client = MinIOClient()

        assert client.endpoint == "localhost:9000"
        assert client.access_key == "minioadmin"
        assert client.secret_key == "minioadmin123"
        assert client.bucket_name == "sapience-dev"

    @patch("app.services.minio_client.Minio")
    def test_ensure_bucket_exists_bucket_does_not_exist(self, mock_minio_class):
        """Test bucket creation when bucket doesn't exist."""
        mock_minio_instance = Mock()
        mock_minio_instance.bucket_exists.return_value = False
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        mock_minio_instance.bucket_exists.assert_called_once_with("sapience-dev")
        mock_minio_instance.make_bucket.assert_called_once_with("sapience-dev")

    @patch("app.services.minio_client.Minio")
    def test_ensure_bucket_exists_bucket_already_exists(self, mock_minio_class):
        """Test when bucket already exists."""
        mock_minio_instance = Mock()
        mock_minio_instance.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        mock_minio_instance.bucket_exists.assert_called_once_with("sapience-dev")
        mock_minio_instance.make_bucket.assert_not_called()

    @patch("app.services.minio_client.Minio")
    def test_ensure_bucket_exists_error(self, mock_minio_class):
        """Test error handling during bucket creation."""
        mock_minio_instance = Mock()
        mock_minio_instance.bucket_exists.side_effect = S3Error(
            "Bucket error", "test", "test", "request_id", "host_id", "response"
        )
        mock_minio_class.return_value = mock_minio_instance

        with patch("builtins.print") as mock_print:
            client = MinIOClient()

        mock_print.assert_called_with(
            "❌ Error creating bucket: S3 operation failed; code: Bucket error, message: test, resource: test, request_id: request_id, host_id: host_id"
        )

    @patch("app.services.minio_client.Minio")
    def test_upload_file_from_memory_success(
        self, mock_minio_class, sample_pdf_content
    ):
        """Test successful file upload from memory."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            url = client.upload_file_from_memory(
                file_data=sample_pdf_content,
                object_name="test/file.pdf",
                content_type="application/pdf",
            )

        expected_url = "minio:9000/sapience-dev/test/file.pdf"
        assert url == expected_url

        mock_minio_instance.put_object.assert_called_once()
        call_args = mock_minio_instance.put_object.call_args
        assert call_args[1]["bucket_name"] == "sapience-dev"
        assert call_args[1]["object_name"] == "test/file.pdf"
        assert call_args[1]["length"] == len(sample_pdf_content)
        assert call_args[1]["content_type"] == "application/pdf"

        mock_print.assert_called_with(f"✅ Uploaded from memory: {expected_url}")

    @patch("app.services.minio_client.Minio")
    def test_upload_file_from_memory_error(self, mock_minio_class, sample_pdf_content):
        """Test error handling during file upload from memory."""
        mock_minio_instance = Mock()
        mock_minio_instance.put_object.side_effect = S3Error(
            "Upload error", "test", "test", "request_id", "host_id", "response"
        )
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            with pytest.raises(S3Error):
                client.upload_file_from_memory(
                    file_data=sample_pdf_content, object_name="test/file.pdf"
                )

        mock_print.assert_called_with(
            "❌ Upload from memory error: S3 operation failed; code: Upload error, message: test, resource: test, request_id: request_id, host_id: host_id"
        )

    @patch("app.services.minio_client.Minio")
    def test_upload_file_success(self, mock_minio_class):
        """Test successful file upload from path."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            url = client.upload_file("test/file.pdf")

        expected_url = "minio:9000/sapience-dev/file.pdf"
        assert url == expected_url

        mock_minio_instance.fput_object.assert_called_once_with(
            "sapience-dev", "file.pdf", "test/file.pdf"
        )
        mock_print.assert_called_with(f"✅ Uploaded: {expected_url}")

    @patch("app.services.minio_client.Minio")
    def test_upload_file_with_custom_object_name(self, mock_minio_class):
        """Test file upload with custom object name."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            url = client.upload_file("test/file.pdf", "custom/path/document.pdf")

        expected_url = "minio:9000/sapience-dev/custom/path/document.pdf"
        assert url == expected_url

        mock_minio_instance.fput_object.assert_called_once_with(
            "sapience-dev", "custom/path/document.pdf", "test/file.pdf"
        )

    @patch("app.services.minio_client.Minio")
    def test_upload_file_error(self, mock_minio_class):
        """Test error handling during file upload from path."""
        mock_minio_instance = Mock()
        mock_minio_instance.fput_object.side_effect = S3Error(
            "Upload error", "test", "test", "request_id", "host_id", "response"
        )
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            with pytest.raises(S3Error):
                client.upload_file("test/file.pdf")

        mock_print.assert_called_with(
            "❌ Upload error: S3 operation failed; code: Upload error, message: test, resource: test, request_id: request_id, host_id: host_id"
        )

    @patch("app.services.minio_client.Minio")
    def test_download_file_success(self, mock_minio_class):
        """Test successful file download."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            client.download_file("test/file.pdf", "local/file.pdf")

        mock_minio_instance.fget_object.assert_called_once_with(
            "sapience-dev", "test/file.pdf", "local/file.pdf"
        )
        mock_print.assert_called_with("✅ Downloaded: test/file.pdf -> local/file.pdf")

    @patch("app.services.minio_client.Minio")
    def test_download_file_error(self, mock_minio_class):
        """Test error handling during file download."""
        mock_minio_instance = Mock()
        mock_minio_instance.fget_object.side_effect = S3Error(
            "Download error", "test", "test", "request_id", "host_id", "response"
        )
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            with pytest.raises(S3Error):
                client.download_file("test/file.pdf", "local/file.pdf")

        mock_print.assert_called_with(
            "❌ Download error: S3 operation failed; code: Download error, message: test, resource: test, request_id: request_id, host_id: host_id"
        )

    @patch("app.services.minio_client.Minio")
    def test_delete_file_success(self, mock_minio_class):
        """Test successful file deletion."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            client.delete_file("test/file.pdf")

        mock_minio_instance.remove_object.assert_called_once_with(
            "sapience-dev", "test/file.pdf"
        )
        mock_print.assert_called_with("✅ Deleted: test/file.pdf")

    @patch("app.services.minio_client.Minio")
    def test_delete_file_error(self, mock_minio_class):
        """Test error handling during file deletion."""
        mock_minio_instance = Mock()
        mock_minio_instance.remove_object.side_effect = S3Error(
            "Delete error", "test", "test", "request_id", "host_id", "response"
        )
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            with pytest.raises(S3Error):
                client.delete_file("test/file.pdf")

        mock_print.assert_called_with(
            "❌ Delete error: S3 operation failed; code: Delete error, message: test, resource: test, request_id: request_id, host_id: host_id"
        )

    @patch("app.services.minio_client.Minio")
    def test_list_files_success(self, mock_minio_class):
        """Test successful file listing."""
        mock_minio_instance = Mock()
        mock_object1 = Mock()
        mock_object1.object_name = "test/file1.pdf"
        mock_object2 = Mock()
        mock_object2.object_name = "test/file2.jpg"
        mock_minio_instance.list_objects.return_value = [mock_object1, mock_object2]
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        files = client.list_files("test/")

        assert files == ["test/file1.pdf", "test/file2.jpg"]
        mock_minio_instance.list_objects.assert_called_once_with(
            "sapience-dev", prefix="test/"
        )

    @patch("app.services.minio_client.Minio")
    def test_list_files_no_prefix(self, mock_minio_class):
        """Test file listing without prefix."""
        mock_minio_instance = Mock()
        mock_object = Mock()
        mock_object.object_name = "file.pdf"
        mock_minio_instance.list_objects.return_value = [mock_object]
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        files = client.list_files()

        assert files == ["file.pdf"]
        mock_minio_instance.list_objects.assert_called_once_with(
            "sapience-dev", prefix=""
        )

    @patch("app.services.minio_client.Minio")
    def test_list_files_error(self, mock_minio_class):
        """Test error handling during file listing."""
        mock_minio_instance = Mock()
        mock_minio_instance.list_objects.side_effect = S3Error(
            "List error", "test", "test", "request_id", "host_id", "response"
        )
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        with patch("builtins.print") as mock_print:
            files = client.list_files()

        assert files == []
        mock_print.assert_called_with(
            "❌ List error: S3 operation failed; code: List error, message: test, resource: test, request_id: request_id, host_id: host_id"
        )

    @patch("app.services.minio_client.Minio")
    def test_get_file_url(self, mock_minio_class):
        """Test getting file URL."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        url = client.get_file_url("test/file.pdf")

        expected_url = "minio:9000/sapience-dev/test/file.pdf"
        assert url == expected_url

    @patch("app.services.minio_client.Minio")
    def test_get_file_url_with_special_characters(self, mock_minio_class):
        """Test getting file URL with special characters."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        url = client.get_file_url("test/file with spaces.pdf")

        expected_url = "minio:9000/sapience-dev/test/file with spaces.pdf"
        assert url == expected_url

    @patch("app.services.minio_client.Minio")
    def test_upload_file_from_memory_with_default_content_type(
        self, mock_minio_class, sample_pdf_content
    ):
        """Test file upload from memory with default content type."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        client.upload_file_from_memory(
            file_data=sample_pdf_content, object_name="test/file.pdf"
        )

        call_args = mock_minio_instance.put_object.call_args
        assert call_args[1]["content_type"] == "application/octet-stream"

    @patch("app.services.minio_client.Minio")
    def test_upload_file_from_memory_with_empty_data(self, mock_minio_class):
        """Test file upload from memory with empty data."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        client.upload_file_from_memory(
            file_data=b"", object_name="test/empty.txt", content_type="text/plain"
        )

        call_args = mock_minio_instance.put_object.call_args
        assert call_args[1]["length"] == 0

    @patch("app.services.minio_client.Minio")
    def test_upload_file_from_memory_with_large_data(self, mock_minio_class):
        """Test file upload from memory with large data."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        large_data = b"X" * (10 * 1024 * 1024)  # 10MB

        client.upload_file_from_memory(
            file_data=large_data, object_name="test/large.bin"
        )

        call_args = mock_minio_instance.put_object.call_args
        assert call_args[1]["length"] == len(large_data)

    @patch("app.services.minio_client.Minio")
    def test_multiple_operations_same_client(
        self, mock_minio_class, sample_pdf_content
    ):
        """Test multiple operations using the same client instance."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        client = MinIOClient()

        # Upload file
        client.upload_file_from_memory(sample_pdf_content, "test/file.pdf")

        # List files
        mock_object = Mock()
        mock_object.object_name = "test/file.pdf"
        mock_minio_instance.list_objects.return_value = [mock_object]
        client.list_files("test/")

        # Get file URL
        client.get_file_url("test/file.pdf")

        # Delete file
        client.delete_file("test/file.pdf")

        # Verify all methods were called
        mock_minio_instance.put_object.assert_called_once()
        mock_minio_instance.list_objects.assert_called_once()
        mock_minio_instance.remove_object.assert_called_once()

    @patch("app.services.minio_client.Minio")
    def test_client_with_different_endpoints(self, mock_minio_class):
        """Test client initialization with different endpoint formats."""
        mock_minio_instance = Mock()
        mock_minio_class.return_value = mock_minio_instance

        # Test with different endpoint formats
        test_cases = ["localhost:9000", "minio.example.com:9000", "192.168.1.100:9000"]

        for endpoint in test_cases:
            with patch.dict("os.environ", {"MINIO_ENDPOINT": endpoint}):
                client = MinIOClient()
                assert client.endpoint == endpoint
                mock_minio_class.assert_called_with(
                    endpoint=endpoint,
                    access_key="minioadmin",
                    secret_key="minioadmin123",
                    secure=False,
                )
