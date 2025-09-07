# Sapience Docker Development Makefile

.PHONY: help build up down logs clean dev prod

# Default target
help:
	@echo "Available commands:"
	@echo "  make dev     - Start development environment"
	@echo "  make prod    - Start production environment"
	@echo "  make build   - Build all services"
	@echo "  make up      - Start services"
	@echo "  make down    - Stop services"
	@echo "  make logs    - Show logs"
	@echo "  make clean   - Clean up containers and volumes"
	@echo "  make shell-backend  - Open shell in backend container"
	@echo "  make shell-frontend - Open shell in frontend container"
	@echo "  make setup-minio - Setup MinIO bucket and policies"
	@echo "  make minio-console - Open MinIO web console"
	@echo "  make test - Run all tests"
	@echo "  make test-unit - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make install-dev - Install development dependencies"
	@echo "  make install-prod - Install production dependencies only"
	@echo "  make lint - Run code linting"

# Development environment
dev:
	docker compose -f docker-compose.dev.yml up --build

# Production environment
prod:
	docker compose up --build

# Build all services
build:
	docker compose build

# Start services
up:
	docker compose up -d

# Stop services
down:
	docker compose down

# Show logs
logs:
	docker compose logs -f

# Clean up
clean:
	docker compose down -v
	docker system prune -f

# Shell access
shell-backend:
	docker compose exec backend bash

shell-frontend:
	docker compose exec frontend sh

# Restart specific service
restart-backend:
	docker compose restart backend

restart-frontend:
	docker compose restart frontend

# MinIO management
setup-minio:
	@echo "🚀 Setting up MinIO..."
	@./scripts/setup-minio.sh

minio-console:
	@echo "🌐 Opening MinIO Console..."
	@echo "URL: http://localhost:9001"
	@echo "Username: minioadmin"
	@echo "Password: minioadmin123"
	@xdg-open http://localhost:9001 || open http://localhost:9001 || echo "Please open http://localhost:9001 in your browser"

# Testing commands
test:
	@echo "🧪 Running all tests..."
	@echo "📋 Make sure backend container is running with: make dev"
	docker compose -f docker-compose.dev.yml exec backend uv run pytest tests/ -v

test-unit:
	@echo "🧪 Running unit tests..."
	@echo "📋 Make sure backend container is running with: make dev"
	docker compose -f docker-compose.dev.yml exec backend uv run pytest tests/test_file_validator.py tests/test_minio_client.py -v

test-integration:
	@echo "🧪 Running integration tests..."
	@echo "📋 Make sure backend container is running with: make dev"
	docker compose -f docker-compose.dev.yml exec backend uv run pytest tests/test_main.py -v

test-coverage:
	@echo "🧪 Running tests with coverage..."
	@echo "📋 Make sure backend container is running with: make dev"
	docker compose -f docker-compose.dev.yml exec backend uv run pytest tests/ --cov=app --cov-report=html --cov-report=term-missing -v

test-watch:
	@echo "🧪 Running tests in watch mode..."
	@echo "📋 Make sure backend container is running with: make dev"
	docker compose -f docker-compose.dev.yml exec backend uv run pytest tests/ -v --tb=short -x

# Dependency management commands
install-dev:
	@echo "📦 Installing development dependencies..."
	cd backend && uv sync --group dev

install-prod:
	@echo "📦 Installing production dependencies only..."
	cd backend && uv sync --no-dev

install-all:
	@echo "📦 Installing all dependencies (prod + dev)..."
	cd backend && uv sync --group dev

lint:
	@echo "🔍 Running linting..."
	@echo "📋 Make sure backend container is running with: make dev"
	docker compose -f docker-compose.dev.yml exec backend uv run black .
	docker compose -f docker-compose.dev.yml exec backend uv run isort .
	docker compose -f docker-compose.dev.yml exec backend uv run flake8 .
	docker compose -f docker-compose.dev.yml exec backend uv run mypy .

