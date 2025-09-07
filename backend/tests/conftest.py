# Pytest configuration file

import pytest
import os
import sys
from unittest.mock import Mock, MagicMock, patch
from io import BytesIO
from datetime import datetime
from fastapi.testclient import TestClient

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app
from app.services.minio_client import MinIOClient
from app.services.file_validator import FileValidator


@pytest.fixture
def client():
    """FastAPI test client fixture."""
    return TestClient(app)


@pytest.fixture
def mock_minio_client():
    """Mock MinIO client fixture."""
    mock_client = Mock(spec=MinIOClient)
    mock_client.bucket_name = "test-bucket"
    mock_client.endpoint = "http://test-minio:9000"
    return mock_client


@pytest.fixture
def mock_minio_put_object():
    """Mock MinIO put_object method."""
    with pytest.Mock() as mock:
        yield mock


@pytest.fixture
def sample_pdf_content():
    """Generate sample PDF content for testing."""
    # Minimal PDF header - just enough to be recognized as PDF
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n174\n%%EOF"


@pytest.fixture
def sample_image_content():
    """Generate sample PNG image content for testing."""
    # Minimal PNG header
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.fixture
def sample_json_content():
    """Generate sample JSON content for testing."""
    return b'{"test": "data", "number": 123, "boolean": true}'


@pytest.fixture
def sample_csv_content():
    """Generate sample CSV content for testing."""
    return b"name,age,city\nJohn,25,New York\nJane,30,London\nBob,35,Paris"


@pytest.fixture
def sample_xml_content():
    """Generate sample XML content for testing."""
    return b'<?xml version="1.0" encoding="UTF-8"?>\n<root>\n    <item>test</item>\n</root>'


@pytest.fixture
def sample_html_content():
    """Generate sample HTML content for testing."""
    return b"<!DOCTYPE html>\n<html>\n<head><title>Test</title></head>\n<body><h1>Hello World</h1></body>\n</html>"


@pytest.fixture
def sample_excel_content():
    """Generate sample Excel content for testing."""
    # Minimal Excel file header
    return b"PK\x03\x04\x14\x00\x00\x00\x08\x00\x00\x00!\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00[Content_Types].xml"


@pytest.fixture
def sample_word_content():
    """Generate sample Word content for testing."""
    # Minimal Word file header
    return b"PK\x03\x04\x14\x00\x00\x00\x08\x00\x00\x00!\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00[Content_Types].xml"


@pytest.fixture
def large_file_content():
    """Generate large file content for testing size limits."""
    # Generate 60MB of data (exceeds 50MB limit)
    return b"X" * (60 * 1024 * 1024)


@pytest.fixture
def mock_upload_file():
    """Create a mock UploadFile for testing."""

    def _create_upload_file(filename: str, content: bytes, content_type: str = None):
        mock_file = Mock()
        mock_file.filename = filename
        mock_file.content_type = content_type
        mock_file.file = BytesIO(content)
        mock_file.read = Mock(return_value=content)
        return mock_file

    return _create_upload_file


@pytest.fixture
def frozen_time():
    """Freeze time for consistent testing."""
    with patch("datetime.datetime") as mock_datetime:
        mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 14, 30, 22, 123000)
        yield mock_datetime


@pytest.fixture(autouse=True)
def mock_logging():
    """Mock logging to prevent actual log output during tests."""
    with patch("logging.getLogger") as mock_logger:
        yield mock_logger


# Test data generators
class TestDataGenerator:
    """Utility class for generating test data."""

    @staticmethod
    def generate_file_content(size_bytes: int) -> bytes:
        """Generate file content of specified size."""
        return b"A" * size_bytes

    @staticmethod
    def generate_filename(extension: str) -> str:
        """Generate a test filename with given extension."""
        return f"test_file.{extension}"

    @staticmethod
    def generate_unique_filename(extension: str) -> str:
        """Generate a unique test filename with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        return f"{timestamp}_test_file.{extension}"


@pytest.fixture
def test_data_generator():
    """Test data generator fixture."""
    return TestDataGenerator
