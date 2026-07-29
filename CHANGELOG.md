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
