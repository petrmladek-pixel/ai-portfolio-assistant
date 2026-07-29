# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Planning for Sprint 2 (Market Data Subsystem).

## [0.1.0] - 2026-07-29

### Added
- Pydantic V2 domain models (`StockPosition`, `ImportedPortfolio`).
- Privacy feature supporting normalized, weight-based portfolio tracking (`AnonymizedPortfolio`).
- Concrete `DegiroPortfolioParser` handling localized CSV exports (Czech, English, Dutch headers).
- Full suite of pytest unit tests for models and parsers.
- Local developer workflow environment via `Makefile` and `pre-commit` (Ruff, Mypy, Codespell).
- Centralized configurations in `pyproject.toml`.
- GitHub Actions CI pipeline with automated linting, typing, and testing.
