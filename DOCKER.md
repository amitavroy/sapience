# Sapience - Docker Development Setup

This document explains how to run the Sapience application using Docker Compose for development.

## Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose

## Quick Start

### 1. Start the entire application
```bash
docker-compose up --build
```

### 2. Start in development mode (with additional dev features)
```bash
docker-compose -f docker-compose.dev.yml up --build
```

### 3. Start in background
```bash
docker-compose up -d --build
```

## Services

### Backend (FastAPI)
- **Port**: 8000
- **URL**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

### Frontend (Next.js)
- **Port**: 3000
- **URL**: http://localhost:3000
- **Hot Reload**: Enabled

## Development Features

### Hot Reload
Both services support hot reload:
- **Backend**: Automatically restarts when Python files change
- **Frontend**: Automatically refreshes when React/TypeScript files change

### Volume Mounts
- Source code is mounted as volumes for instant changes
- Dependencies are cached in Docker volumes for faster rebuilds

### Environment Variables
- `NEXT_PUBLIC_API_URL=http://localhost:8000` - Frontend API URL
- `PYTHONUNBUFFERED=1` - Python output buffering disabled

## Commands

### Start services
```bash
# Basic start
docker-compose up

# Start with build
docker-compose up --build

# Start in background
docker-compose up -d

# Start specific service
docker-compose up backend
docker-compose up frontend
```

### Stop services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Stop specific service
docker-compose stop backend
```

### View logs
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs backend
docker-compose logs frontend

# Follow logs
docker-compose logs -f
```

### Execute commands in containers
```bash
# Backend shell
docker-compose exec backend bash

# Frontend shell
docker-compose exec frontend sh

# Run specific commands
docker-compose exec backend uv run python -c "print('Hello')"
docker-compose exec frontend npm run build
```

### Rebuild services
```bash
# Rebuild all
docker-compose build

# Rebuild specific service
docker-compose build backend
docker-compose build frontend

# Force rebuild (no cache)
docker-compose build --no-cache
```

## Troubleshooting

### Port conflicts
If ports 3000 or 8000 are already in use:
```bash
# Check what's using the ports
lsof -i :3000
lsof -i :8000

# Stop conflicting services or change ports in docker-compose.yml
```

### Permission issues
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
```

### Clean rebuild
```bash
# Remove everything and rebuild
docker-compose down -v
docker system prune -f
docker-compose up --build
```

### View container status
```bash
docker-compose ps
```

## File Structure
```
sapience/
├── docker-compose.yml          # Main compose file
├── docker-compose.dev.yml      # Development compose file
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   └── ...
├── frontend/
│   ├── Dockerfile
│   ├── .dockerignore
│   └── ...
└── README.md
```

## Development Workflow

1. **Start the development environment**:
   ```bash
   docker-compose -f docker-compose.dev.yml up --build
   ```

2. **Make changes** to your code in the `backend/` or `frontend/` directories

3. **See changes instantly** - both services will automatically reload

4. **Access the applications**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

5. **Stop when done**:
   ```bash
   docker-compose down
   ```

## Production Considerations

This setup is optimized for development. For production:
- Use multi-stage builds
- Remove volume mounts
- Use production-optimized images
- Set up proper networking and security
- Use environment-specific configurations

