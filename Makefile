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
