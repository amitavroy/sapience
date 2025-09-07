"""
Comprehensive tests for FileValidator service.

Tests cover:
- Valid file type validation
- Invalid file type rejection
- File size validation
- Content type validation
- Edge cases and error handling
"""

import pytest
from unittest.mock import Mock, patch
from app.services.file_validator import (
    FileValidator,
    FileValidationError,
    ALLOWED_FILE_TYPES,
    MAX_FILE_SIZE,
)


class TestFileValidator:
    """Test cases for FileValidator class."""

    def test_validate_pdf_file_success(self, mock_upload_file, sample_pdf_content):
        """Test successful validation of PDF file."""
        upload_file = mock_upload_file(
            "test.pdf", sample_pdf_content, "application/pdf"
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_image_file_success(self, mock_upload_file, sample_image_content):
        """Test successful validation of image file."""
        upload_file = mock_upload_file("test.png", sample_image_content, "image/png")

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_json_file_success(self, mock_upload_file, sample_json_content):
        """Test successful validation of JSON file."""
        upload_file = mock_upload_file(
            "test.json", sample_json_content, "application/json"
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_csv_file_success(self, mock_upload_file, sample_csv_content):
        """Test successful validation of CSV file."""
        upload_file = mock_upload_file("test.csv", sample_csv_content, "text/csv")

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_xml_file_success(self, mock_upload_file, sample_xml_content):
        """Test successful validation of XML file."""
        upload_file = mock_upload_file(
            "test.xml", sample_xml_content, "application/xml"
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_html_file_success(self, mock_upload_file, sample_html_content):
        """Test successful validation of HTML file."""
        upload_file = mock_upload_file("test.html", sample_html_content, "text/html")

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_excel_file_success(self, mock_upload_file, sample_excel_content):
        """Test successful validation of Excel file."""
        upload_file = mock_upload_file(
            "test.xlsx",
            sample_excel_content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_word_file_success(self, mock_upload_file, sample_word_content):
        """Test successful validation of Word file."""
        upload_file = mock_upload_file(
            "test.docx",
            sample_word_content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_file_no_filename(self, mock_upload_file, sample_pdf_content):
        """Test validation failure when no filename is provided."""
        upload_file = mock_upload_file("", sample_pdf_content, "application/pdf")

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is False
        assert "No file provided" in error_message

    def test_validate_file_no_extension(self, mock_upload_file, sample_pdf_content):
        """Test validation failure when file has no extension."""
        upload_file = mock_upload_file(
            "testfile", sample_pdf_content, "application/pdf"
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is False
        assert "has no extension" in error_message

    def test_validate_unsupported_file_type(self, mock_upload_file, sample_pdf_content):
        """Test validation failure for unsupported file type."""
        upload_file = mock_upload_file("test.txt", sample_pdf_content, "text/plain")

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is False
        assert "File type '.txt' is not allowed" in error_message
        assert "Allowed types:" in error_message

    def test_validate_file_too_large(self, mock_upload_file, large_file_content):
        """Test validation failure when file exceeds size limit."""
        upload_file = mock_upload_file(
            "large.pdf", large_file_content, "application/pdf"
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is False
        assert "exceeds maximum allowed size" in error_message
        assert "60.00MB" in error_message
        assert "50.0MB" in error_message

    def test_validate_file_wrong_content_type(
        self, mock_upload_file, sample_pdf_content
    ):
        """Test validation failure when content type doesn't match extension."""
        upload_file = mock_upload_file("test.pdf", sample_pdf_content, "text/plain")

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is False
        assert (
            "Content type 'text/plain' does not match file extension '.pdf'"
            in error_message
        )

    def test_validate_file_no_content_type(self, mock_upload_file, sample_pdf_content):
        """Test validation success when no content type is provided."""
        upload_file = mock_upload_file("test.pdf", sample_pdf_content, None)

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_file_case_insensitive_extension(
        self, mock_upload_file, sample_pdf_content
    ):
        """Test validation with different case extensions."""
        upload_file = mock_upload_file(
            "test.PDF", sample_pdf_content, "application/pdf"
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_file_multiple_extensions(
        self, mock_upload_file, sample_pdf_content
    ):
        """Test validation with multiple dots in filename."""
        upload_file = mock_upload_file(
            "test.backup.pdf", sample_pdf_content, "application/pdf"
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    def test_validate_file_exception_handling(self, mock_upload_file):
        """Test exception handling during validation."""
        upload_file = Mock()
        upload_file.filename = "test.pdf"
        upload_file.file.seek.side_effect = Exception("File read error")

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is False
        assert "File validation error: File read error" in error_message

    def test_get_file_extension_valid(self):
        """Test getting file extension from valid filename."""
        extension = FileValidator._get_file_extension("test.pdf")
        assert extension == "pdf"

    def test_get_file_extension_case_insensitive(self):
        """Test getting file extension with different cases."""
        extension = FileValidator._get_file_extension("test.PDF")
        assert extension == "pdf"

    def test_get_file_extension_multiple_dots(self):
        """Test getting file extension with multiple dots."""
        extension = FileValidator._get_file_extension("test.backup.pdf")
        assert extension == "pdf"

    def test_get_file_extension_no_extension(self):
        """Test getting file extension when none exists."""
        extension = FileValidator._get_file_extension("testfile")
        assert extension == ""

    def test_get_file_extension_empty_filename(self):
        """Test getting file extension from empty filename."""
        extension = FileValidator._get_file_extension("")
        assert extension == ""

    def test_get_file_size(self, mock_upload_file, sample_pdf_content):
        """Test getting file size from UploadFile."""
        upload_file = mock_upload_file(
            "test.pdf", sample_pdf_content, "application/pdf"
        )

        size = FileValidator._get_file_size(upload_file)

        assert size == len(sample_pdf_content)

    def test_get_allowed_file_types(self):
        """Test getting list of allowed file types."""
        allowed_types = FileValidator.get_allowed_file_types()

        assert isinstance(allowed_types, list)
        assert "pdf" in allowed_types
        assert "jpg" in allowed_types
        assert "json" in allowed_types
        assert "csv" in allowed_types
        assert "xml" in allowed_types
        assert "html" in allowed_types
        assert "docx" in allowed_types
        assert "xlsx" in allowed_types

    def test_get_max_file_size_mb(self):
        """Test getting maximum file size in MB."""
        max_size_mb = FileValidator.get_max_file_size_mb()

        assert max_size_mb == 50.0

    def test_allowed_file_types_structure(self):
        """Test that ALLOWED_FILE_TYPES has correct structure."""
        assert isinstance(ALLOWED_FILE_TYPES, dict)

        # Check that all values are lists
        for file_type, mime_types in ALLOWED_FILE_TYPES.items():
            assert isinstance(mime_types, list)
            assert len(mime_types) > 0

        # Check specific file types
        assert "pdf" in ALLOWED_FILE_TYPES
        assert "application/pdf" in ALLOWED_FILE_TYPES["pdf"]

        assert "jpg" in ALLOWED_FILE_TYPES
        assert "image/jpeg" in ALLOWED_FILE_TYPES["jpg"]

        assert "json" in ALLOWED_FILE_TYPES
        assert "application/json" in ALLOWED_FILE_TYPES["json"]

    def test_max_file_size_constant(self):
        """Test that MAX_FILE_SIZE constant is correct."""
        assert MAX_FILE_SIZE == 50 * 1024 * 1024  # 50MB in bytes

    @pytest.mark.parametrize(
        "file_type,content_type",
        [
            ("pdf", "application/pdf"),
            ("jpg", "image/jpeg"),
            ("png", "image/png"),
            ("json", "application/json"),
            ("csv", "text/csv"),
            ("xml", "application/xml"),
            ("html", "text/html"),
            (
                "docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            (
                "xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        ],
    )
    def test_validate_all_supported_file_types(
        self, mock_upload_file, file_type, content_type
    ):
        """Test validation for all supported file types."""
        content = b"test content"
        upload_file = mock_upload_file(f"test.{file_type}", content, content_type)

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is True
        assert error_message == ""

    @pytest.mark.parametrize(
        "unsupported_type",
        ["txt", "exe", "zip", "rar", "mp3", "mp4", "avi", "mov", "py", "js", "css"],
    )
    def test_validate_unsupported_file_types(self, mock_upload_file, unsupported_type):
        """Test validation failure for various unsupported file types."""
        content = b"test content"
        upload_file = mock_upload_file(
            f"test.{unsupported_type}", content, "application/octet-stream"
        )

        is_valid, error_message = FileValidator.validate_file(upload_file)

        assert is_valid is False
        assert f"File type '.{unsupported_type}' is not allowed" in error_message
