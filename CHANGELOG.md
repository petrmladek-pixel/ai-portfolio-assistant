# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


### Added
- Pydantic V2 domain models (`StockPosition`, `ImportedPortfolio`).
- Privacy feature supporting normalized, weight-based portfolio tracking (`AnonymizedPortfolio`).
- Concrete `DegiroPortfolioParser` handling localized CSV exports (Czech, English, Dutch headers).
- Full suite of pytest unit tests for models and parsers.
- Local developer workflow environment via `Makefile` and `pre-commit` (Ruff, Mypy, Codespell).
- Centralized configurations in `pyproject.toml`.
- GitHub Actions CI pipeline with automated linting, typing, and testing.

## v0.5.1 (2026-08-19)

### Fix

- **ci**: remove --force from git fetch command and update push behavior to follow tags
- **ci**: correct typo in git fetch command in CI workflow

## v0.5.0 (2026-08-19)

### Feat

- **portfolio**: add portfolio retrieval API and associated tests
- **auth**: implement JWT authentication with user registration and login routes
- **db**: implement database layer and user models using sqlmodel
- **upload**: enforce portfolio file upload validation and improve error handling

### Fix

- **config**: update default secret key and improve production validation logic
- **user**: enforce password length validation in UserCreate model
- **portfolio**: enhance error handling for database operations in portfolio routes
- **web**: improve error handling for dashboard and portfolio upload processes

## v0.4.0 (2026-08-12)

### Feat

- **parser**: refactor portfolio parsers to unify async parsing methods and enhance ISIN resolution handling
- **portfolio-merger**: implement portfolio merging functionality with weighted averages

### Refactor

- **parser**: improve safe_decode method to use automatic encoding detection
- **portfolio**: enhance validation for StockPosition and clean up ISIN resolver

## v0.3.0 (2026-07-31)

### Feat

- **gemini**: enhance Gemini AI service with environment variable fallback for API key and configurable model name
- **ai**: integrate Google Gemini AI service for portfolio analysis
- **auth**: implement basic authentication logic in a separate dependencies module
- **auth**: enforce explicit configuration of basic auth credentials in production
- **auth**: add basic authentication for web dashboard with configurable credentials
- **web**: add logging for portfolio upload errors
- **pre-commit**: add Commitizen for enforcing commit message conventions
- **web**: add web routes for portfolio dashboard with upload functionality and chart display

### Fix

- **ai**: improve error handling in Gemini AI service analysis

### Refactor

- **gemini**: enhance GeminiAIService with connection pooling and improved API key handling
- **gemini**: improve API key handling and logging in GeminiAIService
- **yfinance**: simplify price extraction logic and improve error handling

## v0.2.0 (2026-07-29)

### Feat

- **yfinance**: add logging for missing tickers and enhance tests for error handling
- add pull request template for consistent contributions
- **market_data**: implement base market data service and Yahoo Finance integration
- **mypy**: add mypy configuration for strict type checking
- **parser**: add DegiroPortfolioParser for CSV parsing and anonymization
- **models**: add Pydantic models for portfolio stock positions and imported portfolios feat(parser): implement base portfolio parser interface for different brokers test(parser): add tests for base portfolio parser functionality test(models): add tests for portfolio Pydantic models validation chore: remove unused MASTER_TEMPLATE.md and unpack.py files
- initialize portfolio assistant with FastAPI and configuration management

### Fix

- add .md extension to issue templates

### Refactor

- **parser**: improve docstrings and comments for BasePortfolioParser
