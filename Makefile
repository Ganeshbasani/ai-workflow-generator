.PHONY: help dev install-hooks run-ui run-api test coverage lint typecheck audit eval check docker docker-ui clean

ifeq ($(OS),Windows_NT)
  VENV_PY := .venv/Scripts/python.exe
else
  VENV_PY := .venv/bin/python
endif

PYTHON_BOOTSTRAP ?= python
VENV := .venv
IMAGE := ai-workflow-generator:local

help: ## Show available targets
	@echo "AI Workflow Generator — developer commands"
	@echo "  make dev         Create .venv and install pinned dev dependencies + hooks"
	@echo "  make run-ui      Start React/Vite at http://localhost:5173"
	@echo "  make run-api     Start FastAPI at http://localhost:8000/docs"
	@echo "  make test        Run the full pytest suite"
	@echo "  make coverage    Run pytest with the 85% coverage gate"
	@echo "  make lint        ruff check ."
	@echo "  make typecheck   mypy --strict"
	@echo "  make audit       pip-audit on pinned dependencies"
	@echo "  make eval        Regenerate EVAL_SCORECARD.md"
	@echo "  make check       lint + typecheck + coverage + audit"
	@echo "  make docker      Build the production image"
	@echo "  make docker-ui   Run both containers with docker compose"
	@echo "  make clean       Remove caches, coverage files and local databases"

dev: ## One-command setup
	$(PYTHON_BOOTSTRAP) -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade "pip==25.0.1"
	$(VENV_PY) -m pip install -r requirements-dev.txt
	$(VENV_PY) -m pre_commit install

install-hooks: ## Reinstall git hooks
	$(VENV_PY) -m pre_commit install

run-ui: ## Start the React/Vite development UI (start run-api in another terminal)
	npm --prefix web run dev

run-api: ## Start the versioned API
	$(VENV_PY) -m uvicorn api:app --reload --port 8000

test: ## Run tests
	$(VENV_PY) -m pytest -q

coverage: ## Enforce the coverage gate
	$(VENV_PY) -m pytest -q --cov=workflow_ai --cov=app --cov-report=term-missing --cov-fail-under=85 -W error::DeprecationWarning

lint: ## Lint
	$(VENV_PY) -m ruff check .

typecheck: ## Type-check
	$(VENV_PY) -m mypy src app.py workflow.py api.py

audit: ## Audit pinned dependencies
	$(VENV_PY) -m pip_audit -r requirements-dev.txt

eval: ## Regenerate the evaluation scorecard
	$(VENV_PY) -m tests.eval.run_eval

check: lint typecheck coverage audit ## Full local quality gate

docker: ## Build the production image
	docker build -t $(IMAGE) .

docker-ui: ## Start the full-stack React + FastAPI app
	docker compose up --build

clean: ## Remove generated artifacts
	$(PYTHON_BOOTSTRAP) -c "import shutil; from pathlib import Path; [shutil.rmtree(p) for p in Path('.').rglob('__pycache__')]; [shutil.rmtree(Path(n)) for n in ('.pytest_cache','.mypy_cache','.ruff_cache','htmlcov') if Path(n).exists()]; [p.unlink() for p in list(Path('.').glob('.coverage*')) + list(Path('.').glob('*.db'))]"
