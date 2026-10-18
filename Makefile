.DEFAULT_GOAL := help
.PHONY: help dev worker migrate seed reset test format

help: ## Show available commands
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

dev: ## Start the dev server with reload
	uv run uvicorn app.main:app --reload

worker: ## Start the Celery worker
	uv run celery -A app.core.celery_app worker -l info --pool=solo

migrate: ## Run migrations
	uv run alembic upgrade head

seed: ## Run the seeder
	uv run cli seed-user

reset: ## Roll back all migrations, re-run them, then seed
	uv run alembic downgrade base
	uv run alembic upgrade head
	$(MAKE) seed

test: ## Run the tests
	uv run pytest

format: ## Run the formatter
	uv run ruff format . && uv run ruff check --fix .
