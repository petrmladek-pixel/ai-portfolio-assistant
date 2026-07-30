# Makefile
.PHONY: install test lint typecheck run-hooks clean

# Installs dependencies, sets up virtual environment, and installs git pre-commit hooks
install:
	uv sync
	uv run pre-commit install

# Runs the pytest suite
test:
	uv run pytest

# Formats and lints the code via Ruff
lint:
	uv run ruff check . --fix
	uv run ruff format .

# Runs mypy static type checking
typecheck:
	uv run mypy src

# Runs all pre-commit hooks on all files manually
run-hooks:
	uv run pre-commit run --all-files

# Cleans up temporary caches
clean:
	rm -rf .mypy_cache .pytest_cache .ruff_cache .venv

release:
	uv run cz bump --yes

.PHONY: run
run:
	uv run uvicorn portfolio_assistant.main:app --reload --app-dir src

.PHONY: docker-build
docker-build:
	docker build -t portfolio-assistant:latest .

.PHONY: docker-run
docker-run:
	docker run -p 8000:8000 portfolio-assistant:latest
