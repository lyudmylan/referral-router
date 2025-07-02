.PHONY: help install test lint format clean build up down logs load-data process-sample

help: ## Show this help message
	@echo "Referral Router MVP - Development Commands"
	@echo "=========================================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies with Poetry
	poetry install --with dev

test: ## Run unit tests
	poetry run pytest tests/ -v

test-e2e: ## Run end-to-end tests
	poetry run pytest tests/e2e/ -v

lint: ## Run linting checks
	poetry run flake8 agent_app/ pdf_service/ empi_mock/ tests/
	poetry run black --check agent_app/ pdf_service/ empi_mock/ tests/

format: ## Format code with black
	poetry run black agent_app/ pdf_service/ empi_mock/ tests/

clean: ## Clean up build artifacts and temporary files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/

build: ## Build Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

logs: ## Show service logs
	docker-compose logs -f

load-data: ## Load synthetic patient data
	./scripts/load_synthea.sh 50

process-sample: ## Process sample referral (requires services to be running)
	python router.py data/sample_referral.txt john.doe@email.com

dev-setup: ## Complete development setup
	@echo "Setting up development environment..."
	$(MAKE) install
	$(MAKE) build
	$(MAKE) up
	@echo "Waiting for services to start..."
	@sleep 10
	$(MAKE) load-data
	@echo "Development environment ready!"

status: ## Check service status
	@echo "Checking service status..."
	@curl -s http://localhost:8080/fhir/metadata > /dev/null && echo "✅ HAPI FHIR: Running" || echo "❌ HAPI FHIR: Not responding"
	@curl -s http://localhost:7000/health > /dev/null && echo "✅ PDF Service: Running" || echo "❌ PDF Service: Not responding"
	@curl -s http://localhost:7001/health > /dev/null && echo "✅ EMPI Service: Running" || echo "❌ EMPI Service: Not responding"

reset: ## Reset everything and start fresh
	$(MAKE) down
	$(MAKE) clean
	$(MAKE) dev-setup 