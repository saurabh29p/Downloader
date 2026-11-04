# AnyGet — common commands. Run `make help` for the list.
SHELL := /bin/bash
API := apps/api
UV := uv run --project $(API)

.DEFAULT_GOAL := help
.PHONY: help setup dev dev-api dev-web gen gen-check lint format typecheck test check e2e build up down logs ps up-public

help: ## Show this help
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install all dependencies (uv + pnpm)
	uv sync --project $(API)
	pnpm install
	@test -f .env || cp .env.example .env

dev: ## Run api (:8000) and web (:3000) with reload
	@trap 'kill 0' EXIT; $(MAKE) dev-api & $(MAKE) dev-web & wait

dev-api:
	cd $(API) && uv run uvicorn anyget.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	pnpm --filter @anyget/web dev

gen: ## Regenerate packages/shared from the API OpenAPI schema
	pnpm gen

gen-check: gen ## Fail if the generated client is out of date
	git diff --exit-code -- packages/shared

lint: ## ruff + eslint + prettier
	cd $(API) && uv run ruff check . && uv run ruff format --check .
	pnpm lint
	pnpm format:check

format: ## Auto-format Python and TypeScript
	cd $(API) && uv run ruff format . && uv run ruff check --fix .
	pnpm format

typecheck: ## mypy strict + tsc
	cd $(API) && uv run mypy anyget tests
	pnpm typecheck

test: ## pytest + vitest
	cd $(API) && uv run pytest
	pnpm test

check: lint typecheck test ## lint + typecheck + test

e2e: ## Playwright + axe (starts api and web itself)
	pnpm e2e

build: ## Build Docker images
	docker compose build

up: ## Start api + web with Docker Compose
	@mkdir -p downloads data
	docker compose up -d --build
	@echo "AnyGet is starting at http://127.0.0.1:3000"

down: ## Stop containers
	docker compose down

logs: ## Follow container logs
	docker compose logs -f

ps: ## Show container status and health
	docker compose ps

up-public: ## Start with Cloudflare Tunnel (needs TUNNEL_TOKEN in .env)
	@mkdir -p downloads data
	docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d --build
