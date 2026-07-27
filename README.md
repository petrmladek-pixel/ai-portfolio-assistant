# Universal Python Project Template (FastAPI / uv / Ruff)

A modern, production-ready project template for building asynchronous Python backend applications with **FastAPI**, **Pydantic V2**, **uv**, and **Ruff**, adhering to modern `src-layout` standards.

## 🚀 Features

- **FastAPI**: High-performance web framework for building APIs.
- **Pydantic V2**: Data validation and settings management.
- **uv**: Fast Python package installer and resolver.
- **Ruff**: Integrated linting and formatting.
- **Pytest**: Comprehensive testing framework with `pytest-asyncio`.
- **GitHub Actions**: CI/CD pipelines for linting, formatting, and testing.
- **Src-layout**: Modern project structure.

## 🛠️ Tech Stack & Tooling

- **Language**: Python 3.11+
- **Framework**: FastAPI & Uvicorn
- **Package Manager**: `uv`
- **Validation & Settings**: Pydantic V2 & `pydantic-settings`
- **Linting & Formatting**: Ruff
- **Testing**: `pytest` & `pytest-asyncio`
- **CI/CD**: GitHub Actions

## 📁 Repository Structure

```text
.
├── .env.example              # Sample environment variables configuration
├── .github/
│   └── workflows/            # GitHub Actions CI pipelines
│       ├── ai_review.yml
│       ├── lint.yml
│       └── tests.yml
├── src/                      # Application source code (src-layout)
│   └── {{ project_name }}/
│       ├── __init__.py
│       └── config.py         # Pydantic Settings configuration
├── tests/                    # Test suite and fixtures
│   └── conftest.py
├── AGENTS.md                 # AI coding agent instructions & guidelines
├── pyproject.toml            # Project configuration & dependencies (uv, ruff, pytest)
└── README.md
```

## 🚀 Quick Start

### 1. Prerequisites

Ensure you have `uv` installed on your system:

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Installation

Clone the repository and install dependencies using `uv`:

```bash
git clone https://github.com/YourUsername/python-template-uv.git
cd python-template-uv

# Sync virtual environment and dependencies
uv sync
```

### 3. Environment Setup

Copy the sample environment file and configure your local settings:

```bash
cp .env.example .env
```

## 🧪 Development Commands

### Run Code Linter & Formatter (Ruff)

```bash
# Check for lint issues
uv run ruff check .

# Format code
uv run ruff format .
```

### Run Test Suite (Pytest)

```bash
uv run pytest
```

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
