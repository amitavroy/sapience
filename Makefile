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

