# AI Portfolio Assistant - Roadmap

Welcome to the official roadmap for the open-source **AI Portfolio Assistant**! This document outlines our phases, milestones, and progress towards a production-ready, AI-enhanced portfolio management application.

---

## 🚀 Vision
A lightweight, privacy-focused web application that parses broker exports (CSV/PDF), calculates real-time asset valuations in a target currency, and leverages Google Gemini to provide tailored risk analysis and aggregated news.

---

## 📌 High-Level Roadmap

### Phase 1: Core Engine & Local Pipeline (Completed 🎉)
* **Sprint 1: Base Infrastructure & Parsers**
  - [x] Set up strict Python template, FastAPI, MyPy, Ruff, Pytest, and CI/CD pipelines.
  - [x] Implement Degiro CSV parser (`ImportedPortfolio`).
* **Sprint 2: Real-time Valuation Engine**
  - [x] Create `BaseMarketDataService` and `YFinanceMarketDataService` (async wrapper for `yfinance`).
  - [x] Build the `ValuationService` to calculate current portfolio values and weights in `target_currency` (e.g., CZK).

### Phase 2: Web Interface, Security & Production Deployment (Completed 🎉)
* **Sprint 3: Web Dashboard (Tailwind UI)**
  - [x] Implement simple FastAPI routes to allow CSV file upload.
  - [x] Render a responsive dashboard using HTML templates (Jinja2) styled with Tailwind CSS (served via CDN/static).
  - [x] Display portfolio metrics (Total value, Currency breakdown, Position table with weights).
  - [x] Add a client-side chart (Chart.js via CDN) showing asset allocation.
* **Sprint 4: Production Deployment & GCP Hosting**
  - [x] Configure `Dockerfile` and automated CD (Continuous Delivery) via GitHub Actions.
  - [x] Deploy the application to **Google Cloud Run** using Cloud Build triggers reacting to Git tags.
  - [x] Secure the dashboard using Basic Authentication with protection against timing attacks (`secrets.compare_digest`) and Pydantic fail-closed validation.
  - [x] Safely parse and sanitize Gemini's Markdown analysis on the client side using `marked.js` and `DOMPurify`.

### Phase 3: Secure Ingestion, Multi-Broker & Code Hygiene (Completed 🎉)
* **Sprint 5: Dynamic Resolution & Fio e-Broker Support**
  - [x] Eliminate static `ISIN_TO_TICKER` dictionaries.
  - [x] Implement asynchronous `YahooISINResolver` with a local `SQLiteISINCache` using non-blocking `asyncio.to_thread`.
  - [x] Implement strict exact-match round-trip validation and US exchange/suffix prioritization on Yahoo Search API to prevent fuzzy valuation mismatches.
  - [x] Establish a clean abstract parser base class `BasePortfolioParser` with automatic file encoding detection (`charset-normalizer`) and Czech decimal formatting.
  - [x] Implement `FioBrokerPortfolioParser` and a mathematical `PortfolioMerger` to average prices and recalculate combined portfolio weights.
  - [x] Create an automated code hygiene Pytest checking for accidental Czech diacritics in Python source files.
  - [x] Translate the system prompt in `gemini.py` to English for optimal reasoning, forcing Czech only for the final output.

### Phase 4: Persistence, User Identity & Interactive AI (Current Focus 🎯)
* **Sprint 6: Database Storage & User Accounts**
  - [ ] Refactor the upload endpoint to make individual broker files optional (allow uploading only Fio, only DEGIRO, or both).
  - [ ] Set up a local SQLite database via **SQLAlchemy/SQLModel** with schemas for `users`, `portfolios`, and `positions`.
  - [ ] Implement secure password hashing (`bcrypt`/`argon2`) and HttpOnly cookie-based session/JWT authentication.
  - [ ] Persist parsed/merged positions into the database, allowing users to view their stored portfolio without re-uploading files.
* **Sprint 7: Stateful Chat, Custom Prompts & Localization**
  - [ ] Implement a stateful `/api/chat` endpoint to allow follow-up conversations with Gemini about the stored database portfolio.
  - [ ] Add an interactive chat interface to the dashboard.
  - [ ] Save customizable system prompts in the database per-user and expose an "AI Settings" editing area in the UI.
  - [ ] Implement multi-language localization (EN, CS, FR, DE) for both the UI dashboard (using JSON translation bundles) and the AI analysis output.
