UV ?= $(HOME)/.local/bin/uv

.PHONY: install backend frontend test test-backend test-frontend test-e2e lint

install:
	cd backend && $(UV) sync
	cd frontend && npm install

backend:
	cd backend && $(UV) run nexus-api

frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && $(UV) run pytest -q

test-frontend:
	cd frontend && npm test

test-e2e:
	cd frontend && npm run test:e2e

lint:
	cd backend && $(UV) run ruff check .
	cd frontend && npm run typecheck && npm run lint
