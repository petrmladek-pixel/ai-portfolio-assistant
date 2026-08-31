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

## [0.8.0](https://github.com/petrmladek-pixel/ai-portfolio-assistant/compare/v0.7.0...v0.8.0) (2026-08-31)


### Features

* **config:** add demo data configuration options for automatic seeding ([d8c308d](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/d8c308d71a300428d6e47e3514d8c56cb6d43921))
* **dashboard:** enhance guest user experience with dynamic context rendering ([c8daa22](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/c8daa2286e78cbca0a8b402bbc054be08dd78f85))
* **database:** enhance database seeding with demo user and prevent production seeding ([b3bbad3](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/b3bbad354b573290e082a91ae5749397141ea92b))
* **database:** seed database with default user and portfolios on startup ([52a909d](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/52a909d68a9f7fdee771cceed5a7b15066b58240))
* **issue-template:** assign feature request to specific user for better tracking ([17f3d6d](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/17f3d6d5ec82987bcd43d7949653b79c9223d53a))
* **portfolio:** implement portfolio import functionality and enhance user authentication pages ([2d4e11e](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/2d4e11eb5e68795b742e5ff70283a6db1c289240))
* **sidebar:** update CSV upload form to use POST method and enhance file selection feedback ([12b4533](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/12b45339b56610aaefbd1fcf3dc82d410db1e9f0))
* **templates:** add new components for charts, chat widget, positions table, sidebar, and stats cards ([59d7a3c](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/59d7a3cc5608e2ebf87559f104edb6c7ca0b84bc))

## [0.7.0](https://github.com/petrmladek-pixel/ai-portfolio-assistant/compare/v0.6.1...v0.7.0) (2026-08-24)


### Features

* **dashboard:** localize UI text to Czech and add portfolio management features ([997bb5b](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/997bb5b7f758eac9b7efd7e20ee48f1c31f101c2))
* **env:** update environment variables for portfolio assistant configuration ([49f82ab](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/49f82ab33b79081e3749ca35373860a223c7a7a4))
* **portfolio:** add broker field to portfolio model and update relationships ([4572cb9](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/4572cb9bc305f7cbda72fbf10f88fef34d157f03))
* **portfolio:** add support for importing broker portfolios and default portfolio creation ([02e13dd](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/02e13ddf12079350c36a0ddecada951b85aa180f))
* **portfolio:** implement portfolio creation and upload services with CRUD operations ([db92ab5](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/db92ab50ea1b5722bb12242969de634ebf14662a))


### Bug Fixes

* **isin_cache:** ensure parent directory exists before creating database tables ([311934a](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/311934a4e1fc01bf0a8053910dda2046f56d87cd))
* **user_service:** handle exceptions during user creation and ensure session rollback ([5831064](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/5831064249e73c3fbebaecb7c5ca731bc74b47d4))

## [0.6.1](https://github.com/petrmladek-pixel/ai-portfolio-assistant/compare/v0.6.0...v0.6.1) (2026-08-20)


### Bug Fixes

* **ci:** update deploy workflow to trigger on main branch and add release steps ([187de5d](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/187de5d01c18082064ce55f724fa17b9f30e6b54))
* **ci:** update deploy workflow to trigger on main branch and add release steps ([52e7d5e](https://github.com/petrmladek-pixel/ai-portfolio-assistant/commit/52e7d5ed1d1ef95e6ce0e2b3a50b55bfeb6d528c))

## v0.5.2 (2026-08-19)

### Fix

- **workflow**: correct Commitizen bump command to handle version increments properly

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
