# Sapience

A full-stack application with Next.js frontend and FastAPI backend, featuring S3-compatible file storage with MinIO for development.

## 🚀 **Quick Start**

### **1. Prerequisites**
- Docker and Docker Compose
- Make (optional, for convenience commands)

### **2. Environment Setup**
```bash
# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# Edit configuration as needed
nano backend/.env
nano frontend/.env.local
```

### **3. Start Development Environment**
```bash
# Install make (if not already installed)
sudo apt update && sudo apt install make

# Start all services
make dev

# Setup MinIO (first time only)
make setup-minio
```

### **4. Access Your Applications**
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001

## 📁 **Project Structure**

```
sapience/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── http/
│   │   │   └── responses/   # API response models
│   │   └── services/        # Business logic services
│   ├── .env.example         # Backend environment template
│   ├── .env                 # Backend environment (create from example)
│   ├── main.py              # FastAPI application entry point
│   ├── requirements.txt     # Python dependencies
│   └── pyproject.toml       # Project configuration
├── frontend/                # Next.js frontend
│   ├── src/
│   │   ├── app/             # Next.js app router
│   │   ├── components/      # React components
│   │   └── lib/             # Utility functions
│   ├── .env.example         # Frontend environment template
│   └── .env.local           # Frontend environment (create from example)
├── scripts/
│   └── setup-minio.sh       # MinIO setup script
├── docker-compose.yml       # Production Docker Compose
├── docker-compose.dev.yml   # Development Docker Compose
├── Makefile                 # Convenience commands
└── README.md                # This file
```

## 🛠️ **Development Commands**

### **Make Commands**
```bash
make dev              # Start development environment
make prod             # Start production environment
make build            # Build all services
make up               # Start services in background
make down             # Stop services
make logs             # Show logs
make clean            # Clean up containers and volumes
make setup-minio      # Setup MinIO bucket and policies
make minio-console    # Open MinIO web console
make shell-backend    # Open shell in backend container
make shell-frontend   # Open shell in frontend container
make restart-backend  # Restart backend service
make restart-frontend # Restart frontend service
```

### **Docker Compose Commands**
```bash
# Development
docker compose -f docker-compose.dev.yml up --build
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f
docker compose -f docker-compose.dev.yml down

# Production
docker compose up --build
docker compose up -d
docker compose logs -f
docker compose down
```

## 🔧 **Environment Configuration**

### **Backend Environment (`backend/.env`)**
```bash
# MinIO Server Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET_NAME=sapience-dev

# MinIO Root User (for MinIO service itself)
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123

# Additional backend environment variables
# DATABASE_URL=postgresql://user:password@localhost:5432/sapience
# REDIS_URL=redis://localhost:6379
# JWT_SECRET_KEY=your-secret-key-here
```

### **Frontend Environment (`frontend/.env.local`)**
```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000

# MinIO Configuration (for client-side access)
NEXT_PUBLIC_MINIO_URL=http://localhost:9000

# Additional frontend environment variables
# NEXT_PUBLIC_APP_NAME=Sapience
# NEXT_PUBLIC_VERSION=1.0.0
# NEXT_PUBLIC_DEBUG=true
```

## 🗄️ **MinIO File Storage**

### **Overview**
MinIO provides S3-compatible object storage for development. It's perfect for testing file uploads locally before deploying to production S3 services.

### **Access Points**
| Service | URL | Credentials |
|---------|-----|-------------|
| **MinIO API** | http://localhost:9000 | `minioadmin` / `minioadmin123` |
| **MinIO Console** | http://localhost:9001 | `minioadmin` / `minioadmin123` |

### **Default Configuration**
- **Bucket Name**: `sapience-dev`
- **Access Key**: `minioadmin`
- **Secret Key**: `minioadmin123`
- **Endpoint**: `http://localhost:9000`

### **Python Integration**
```python
from app.services.minio_client import MinIOClient

# Initialize client
minio_client = MinIOClient()

# Upload a file
file_url = minio_client.upload_file("path/to/file.jpg", "uploads/image.jpg")

# Download a file
minio_client.download_file("uploads/image.jpg", "downloaded/image.jpg")

# Delete a file
minio_client.delete_file("uploads/image.jpg")

# List files
files = minio_client.list_files("uploads/")

# Get file URL
url = minio_client.get_file_url("uploads/image.jpg")
```

### **Example API Endpoint**
```python
from fastapi import FastAPI, UploadFile, File
from app.services.minio_client import MinIOClient

app = FastAPI()
minio_client = MinIOClient()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Save uploaded file temporarily
    temp_path = f"temp/{file.filename}"
    with open(temp_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Upload to MinIO
    file_url = minio_client.upload_file(temp_path, f"uploads/{file.filename}")
    
    # Clean up temp file
    os.remove(temp_path)
    
    return {"url": file_url, "filename": file.filename}
```

## 🌐 **API Endpoints**

### **Backend API**
- **Root**: `GET /` - Welcome message
- **Health Check**: `GET /health` - Detailed health status
- **API Documentation**: `GET /docs` - Interactive Swagger UI
- **ReDoc**: `GET /redoc` - Alternative API documentation

### **Health Check Response**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00",
  "version": "0.1.0",
  "python_version": "3.13.6",
  "platform": "Linux-6.14.0-29-generic-x86_64-with-glibc2.39"
}
```

## 🎨 **Frontend Features**

### **Technologies**
- **Next.js 14** with App Router
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **Shadcn UI** for components
- **Lato Font** from Google Fonts

### **Components**
- **Sidebar-07** from Shadcn UI
- **Responsive design** by default
- **Modern UI** with dark mode support

## 🐳 **Docker Services**

### **Development Services**
- **Backend**: FastAPI with hot reload
- **Frontend**: Next.js with hot reload
- **MinIO**: S3-compatible object storage

### **Service Dependencies**
- Frontend depends on Backend
- Backend depends on MinIO
- All services use shared network

### **Health Checks**
- **Backend**: HTTP health check on `/health`
- **MinIO**: HTTP health check on `/minio/health/live`

## 🔒 **Security Notes**

### **Development**
- Default credentials are for development only
- MinIO runs on HTTP (not HTTPS)
- Bucket is set to public access

### **Production**
- Use strong, unique credentials
- Enable HTTPS
- Set appropriate access policies
- Use IAM roles when possible

## 🚀 **Production Deployment**

### **Environment Variables**
When moving to production, update environment variables:

```bash
# Production backend environment
MINIO_ENDPOINT=your-s3-endpoint.amazonaws.com:443
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
MINIO_BUCKET_NAME=your-production-bucket

# Production frontend environment
NEXT_PUBLIC_API_URL=https://your-api-domain.com
NEXT_PUBLIC_MINIO_URL=https://your-s3-endpoint.amazonaws.com
```

### **S3 Compatibility**
The MinIO client is S3-compatible and works with:
- AWS S3
- Google Cloud Storage
- Azure Blob Storage
- Any S3-compatible service

## 🐛 **Troubleshooting**

### **Common Issues**

#### **Port Conflicts**
```bash
# Check if ports are in use
lsof -i :3000
lsof -i :8000
lsof -i :9000
lsof -i :9001

# Kill conflicting processes
sudo kill -9 <PID>
```

#### **MinIO Not Starting**
```bash
# Check MinIO health
curl http://localhost:9000/minio/health/live

# Check container status
docker compose -f docker-compose.dev.yml ps

# View MinIO logs
docker compose -f docker-compose.dev.yml logs minio
```

#### **Bucket Not Found**
```bash
# Run setup script
make setup-minio
```

#### **Environment Variables Not Loading**
```bash
# Check if .env files exist
ls -la backend/.env
ls -la frontend/.env.local

# Copy example files if missing
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

### **Reset Everything**
```bash
# Stop all services
make down

# Clean up volumes
make clean

# Start fresh
make dev
make setup-minio
```

## 📚 **Additional Resources**

- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [MinIO Documentation](https://docs.min.io/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Shadcn UI Components](https://ui.shadcn.com/)

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 **License**

This project is licensed under the MIT License.

---

**Happy coding!** 🎉
