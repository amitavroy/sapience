# Sapience Backend

FastAPI backend for the Sapience application.

## Setup

### Prerequisites
- Python 3.11+
- uv package manager

### Installation

1. Install dependencies:
```bash
uv sync
```

2. Run the development server:
```bash
uv run python main.py
```

Or use the startup script:
```bash
./start.sh
```

## API Endpoints

### Health Check
- `GET /api/v1/health` - Detailed health check with system info
- `GET /api/v1/ping` - Simple ping endpoint

### Documentation
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Development

The application uses:
- **FastAPI** for the web framework
- **Pydantic** for data validation
- **Uvicorn** as the ASGI server
- **uv** for dependency management

## Project Structure

```
backend/
├── main.py              # Application entry point
├── pyproject.toml       # Project configuration and dependencies
├── start.sh             # Startup script
├── app/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       └── health.py    # Health check routes
└── README.md
```

## Running the Server

### Simple Method
```bash
uv run python main.py
```

### Using Startup Script
```bash
./start.sh
```

Both methods will:
- Install dependencies automatically
- Start the server with hot reload
- Make the API available at http://localhost:8000
- Provide interactive documentation at http://localhost:8000/docs
