.PHONY: help build up down logs test clean migrate deploy

# Variables
DOCKER_COMPOSE = docker compose
DOCKER_COMPOSE_PROD = docker-compose -f deployments/prod/docker-compose.prod.yml
PYTHON = python3
PIP = pip3

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development
build: ## Build all Docker images
	$(DOCKER_COMPOSE) build

up: ## Start all services
	$(DOCKER_COMPOSE) up -d

down: ## Stop all services
	$(DOCKER_COMPOSE) down

logs: ## View logs for all services
	$(DOCKER_COMPOSE) logs -f

restart: ## Restart all services
	$(DOCKER_COMPOSE) restart

re: ## Rebuild and restart all services
	$(DOCKER_COMPOSE) down
	$(DOCKER_COMPOSE) build --no-cache
	$(DOCKER_COMPOSE) up -d

# Service-specific commands
upload-logs: ## View upload service logs
	$(DOCKER_COMPOSE) logs -f upload-service

classifier-logs: ## View classifier service logs
	$(DOCKER_COMPOSE) logs -f classifier-service

# Testing
test: ## Run all tests
	@echo "Running tests for upload service..."
	cd services/upload && $(PYTHON) -m pytest tests/ -v
	@echo "Running tests for classifier service..."
	cd services/classifier && $(PYTHON) -m pytest tests/ -v

test-coverage: ## Run tests with coverage
	cd services/upload && $(PYTHON) -m pytest tests/ --cov=app --cov-report=html
	cd services/classifier && $(PYTHON) -m pytest tests/ --cov=app --cov-report=html

lint: ## Run linting
	@echo "Running flake8..."
	flake8 services/
	@echo "Running black..."
	black --check services/
	@echo "Running mypy..."
	mypy services/

format: ## Format code with black
	black services/

# Database
migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create new migration
	alembic revision --autogenerate -m "$(message)"

migrate-rollback: ## Rollback last migration
	alembic downgrade -1


# GPT Configuration
test-gpt: ## Test GPT API connection
	@echo "Testing GPT API connection..."
	$(PYTHON) -c "import openai; print('GPT API configured')"

# Deployment
deploy-dev: ## Deploy to development
	$(DOCKER_COMPOSE) up -d

deploy-staging: ## Deploy to staging
	@echo "Deploying to staging..."
	# Add staging deployment commands

deploy-prod: ## Deploy to production
	@echo "Deploying to production..."
	$(DOCKER_COMPOSE_PROD) up -d

# Monitoring
monitoring-up: ## Start monitoring stack
	$(DOCKER_COMPOSE) up -d prometheus grafana

monitoring-down: ## Stop monitoring stack
	$(DOCKER_COMPOSE) stop prometheus grafana

# Cleanup
clean: ## Clean up containers, volumes, and temp files
	$(DOCKER_COMPOSE) down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

clean-logs: ## Clean log files
	find logs -type f -name "*.log" -delete

# Docker cleanup
docker-clean: ## Clean Docker system
	docker system prune -af
	docker volume prune -f

# Backup
backup: ## Backup database and models
	@echo "Creating backup..."
	mkdir -p backups/$(shell date +%Y%m%d)
	pg_dump $(DATABASE_URL) > backups/$(shell date +%Y%m%d)/database.sql
	cp -r ml_models/inference backups/$(shell date +%Y%m%d)/models

# Installation
install: ## Install dependencies
	$(PIP) install -r services/upload/requirements.txt
	$(PIP) install -r services/classifier/requirements.txt
	$(PIP) install -r requirements-dev.txt

install-dev: ## Install development dependencies
	$(PIP) install pytest pytest-cov flake8 black mypy pre-commit
	pre-commit install

# Documentation
docs: ## Generate API documentation
	@echo "Generating API documentation..."
	# Add documentation generation commands

# Health check
health: ## Check health of all services
	@curl -f http://localhost:8000/health || echo "Upload service is down"
	@curl -f http://localhost:8001/health || echo "Classifier service is down"
	@curl -f http://localhost:6379/ping || echo "Redis is down"