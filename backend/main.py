from fastapi import FastAPI, UploadFile, File, HTTPException
from datetime import datetime
import platform
import sys
import logging
import time
from app.http.responses.responses import HealthResponse, FileUploadResponse
from app.services.minio_client import MinIOClient
from app.services.file_validator import FileValidator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sapience API",
    description="Backend API for Sapience application",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/")
async def root():
    return {"message": "Welcome to Sapience API", "version": "0.1.0"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint to verify the API is running properly.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="0.1.0",
        python_version=sys.version,
        platform=platform.platform(),
    )


@app.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file to MinIO storage.

    Supports: PDF, Word, Excel, Images, HTML, CSV, JSON, XML
    Maximum file size: 50MB
    """
    start_time = time.time()

    try:
        logger.info(f"File upload started: '{file.filename}'")

        # Validate file
        is_valid, error_message = FileValidator.validate_file(file)
        if not is_valid:
            logger.warning(
                f"File validation failed for '{file.filename}': {error_message}"
            )
            raise HTTPException(status_code=415, detail=error_message)

        logger.info(f"File validation passed for '{file.filename}', starting upload...")

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Generate unique filename with timestamp prefix
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[
            :-3
        ]  # Include milliseconds
        file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
        unique_filename = f"{timestamp}_{file.filename}"

        # Generate object path with date structure
        now = datetime.utcnow()
        object_path = (
            f"uploads/{now.year:04d}/{now.month:02d}/{now.day:02d}/{unique_filename}"
        )

        # Initialize MinIO client and upload
        minio_client = MinIOClient()

        # Upload file
        upload_start_time = time.time()
        file_url = minio_client.upload_file_from_memory(
            file_data=file_content,
            object_name=object_path,
            content_type=file.content_type or "application/octet-stream",
        )
        upload_duration = (
            time.time() - upload_start_time
        ) * 1000  # Convert to milliseconds

        logger.info(
            f"File '{file.filename}' ({file_size / (1024*1024):.2f}MB) uploaded to bucket 'sapience-dev' in {upload_duration:.0f}ms"
        )

        total_duration = (time.time() - start_time) * 1000
        logger.info(
            f"File upload completed: '{file.filename}' -> {file_url} (Total time: {total_duration:.0f}ms)"
        )

        return FileUploadResponse(
            success=True,
            url=file_url,
            filename=file.filename,
            size=file_size,
            content_type=file.content_type or "application/octet-stream",
            upload_timestamp=datetime.utcnow(),
        )

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        logger.error(f"File upload failed for '{file.filename}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
