PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup dev-api dev-web test e2e seed build-web up

setup:            ## Install everything for local development
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q -r server/requirements.txt -e ./cli pytest
	cd web && npm ci

dev-api:          ## API on :8000 with SQLite (tables created automatically)
	cd server && ../$(BIN)/uvicorn app.main:app --reload --port 8000

dev-web:          ## Dashboard on :4200, proxies /api to :8000
	cd web && npx ng serve

test:             ## Unit + API tests
	cd cli && ../$(BIN)/pytest -q
	cd server && ../$(BIN)/pytest -q -p no:warnings

e2e:              ## Real CLI against a running API (start dev-api first)
	PYTHON=$(abspath $(BIN)/python) scripts/e2e.sh http://localhost:8000

seed:             ## Demo team: demo@mcpledger.dev / demo-password-123
	$(BIN)/python server/scripts/seed_demo.py http://localhost:8000

build-web:
	cd web && npx ng build

up:               ## Production image + Postgres via Docker
	docker compose up --build
