from fastapi import FastAPI
from datetime import datetime
import platform
import sys
from app.http.responses.responses import HealthResponse

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
