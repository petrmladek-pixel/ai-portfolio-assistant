# Master Template

## `.github/workflows/ai_review.yml`
```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    name: Gemini review
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      pull-requests: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          enable-cache: true

      - name: Install project dependencies
        run: uv sync --locked --dev

      - name: Run AI Review
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: uv run python scripts/ai_reviewer.py
```

## `.github/workflows/lint.yml`
```yaml
name: Code Quality

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: lint-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: Ruff
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Check out repository
        uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          enable-cache: true

      - name: Install project dependencies
        run: uv sync --locked --dev

      - name: Run Ruff
        run: uv run ruff check .
```

## `.github/workflows/tests.yml`
```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: tests-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  pytest:
    name: Pytest (Python 3.14)
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Check out repository
        uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          enable-cache: true

      - name: Install project dependencies
        run: uv sync --locked --dev

      - name: Run tests
        run: uv run pytest
```

## `pyproject.toml`
```toml
[project]
name = "{{ project_name }}"
version = "0.1.0"
description = "Python project generated from the master template"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "pydantic>=2.6.0",
    "python-dotenv>=1.0.0",
    "uvicorn>=0.28.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=1.4.0",
    "ruff>=0.3.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{{ project_name }}"]

[tool.pytest.ini_options]
testpaths = ["tests"]
filterwarnings = []

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.uv]
package = true
```

## `.env`
```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
DATABASE_URL=sqlite:///./{{ project_name }}.db
LOG_LEVEL=INFO
MAX_PDF_SIZE_BYTES=10485760
```

## `src/{{ project_name }}/config.py`
```python
"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the application."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-3.1-flash-lite")
    database_url: str = Field(default="sqlite:///./{{ project_name }}.db")
    max_pdf_size_bytes: int = Field(default=10 * 1024 * 1024)
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the lifetime of the process."""
    return Settings()
```

## `tests/conftest.py`
```python
import os
from collections.abc import Iterator

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from {{ project_name }}.database import engine
from {{ project_name }}.dependencies import get_analysis_service
from {{ project_name }}.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    SQLModel.metadata.drop_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def override_analysis_service():
    def override(service: object) -> None:
        app.dependency_overrides[get_analysis_service] = lambda: service

    return override
```

## `AGENTS.md`
```md
# Project Architecture Standards ({{ project_name }})

You are a senior Python architect. When generating code, refactoring, or creating
new modules in this project, you MUST strictly follow the rules below.

## 1. Project Structure (Src Layout)

The project strictly uses a modern src-layout with the uv package manager.

- Source code is located exclusively in src/{{ project_name }}/.
- Tests are located in tests/.
- Never create application logic directly in the root directory.

## 2. Separation of Concerns

- main.py: Serves only as the entrypoint. It initializes FastAPI, defines
  middleware and CORS, and registers routers. It must not contain any business
  logic or direct integrations.
- models.py: Contains only Pydantic models for input and output validation.
- api/: Contains endpoints defined with APIRouter. Endpoints only accept
  requests, call the appropriate services through FastAPI Depends, and return
  validated data.
- services/: Contains classes responsible for integrations. These services must
  not directly depend on FastAPI HTTP objects.
- config.py: Manages settings using load_dotenv or pydantic-settings.

## 3. Code and Testing Standards

- All imports must be absolute from src.
- Use pytest and synchronous/asynchronous TestClient for testing.
- Tests must cover both valid flows and error states, such as empty inputs.

## 4. Development Workflow

- Manage all dependencies with uv.
- Use Ruff for static analysis and formatting.

## Commit Standards (STRICT)

Whenever you generate a commit message or create a commit, you MUST write the
commit message in English and strictly follow the Conventional Commits format:

Format: <type>(<scope>): <lowercase description without a trailing period>

Types:
- feat: A new feature
- fix: A bug fix
- docs: Documentation changes
- chore: Maintenance, packages, or gitignore changes
- refactor: A code change that does not alter behavior

## Behavior Rules

1. Always ensure that sensitive keys, such as variables stored in .env, are
   never included in commits.
2. Before committing, verify that the code contains no syntax errors.
```
