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

### Phase 4: Persistence, User Identity & Multi-Portfolio (Completed 🎉)
* **Sprint 6: Database Storage & User Accounts**
  - [x] Refactor the upload endpoint to make individual broker files optional (allow uploading only Fio, only DEGIRO, or both).
  - [x] Set up a local SQLite database via **SQLAlchemy/SQLModel** with schemas for `users`, `portfolios`, and `positions`.
  - [x] Implement secure password hashing (`bcrypt`) and HttpOnly cookie-based session/JWT authentication.
  - [x] Persist parsed/merged positions into the database, allowing users to view their stored portfolio without re-uploading files.
* **Sprint 7: SRE Hardening, Migrations & Layered Architecture**
  - [x] **CD Keyless Deployment:** Configured secure, keyless GCP authentication via Workload Identity Federation (WIF) and optimized multi-tag Docker build caching.
  - [x] **Cost & Guardrails Hardening:** Configured automatic monthly budget alerts ($10), regional Compute Engine quota limits, and Cloud Run scaling caps (`--max-instances=3`).
  - [x] **Alembic Database Migrations:** Implemented the Alembic migration framework, established programmatic migrations on application startup, and secured SQLite locks.
  - [x] **Pragmatic Layered Architecture:** Refactored backend routers to strictly follow 3-tier layering (Routers -> Services -> CRUD) and introduced structured Domain Exception handling.
  - [x] **Multi-Portfolio DB Schema:** Implemented the `Portfolio` model in the database to support separate accounts/portfolios per broker per user.

### Phase 5: Premium Visual Facelift & DB Persistence Onboarding (Completed 🎉)
* **Sprint 8: Swiss-Style UI & Unified Persistence**
  - [x] **Swiss-Style Dashboard Facelift:** Refactor Jinja2 templates into clean, modular sub-components (< 150 lines) based on the premium minimalist layout.
  - [x] **Unified Upload Form:** Simplify the upload section to a single unified form with target portfolio selection, import type (DEGIRO/Fio), and a single file input.
  - [x] **Self-Healing DB & Startup Seeding:** Implement database self-healing seeder on startup that automatically populates a default portfolio and a guest demo portfolio (Warren Buffett portfolio) only in development environments.

### Phase 6: Real-Data Caching, Architectural Hardening & AI Copilot (Current Focus 🎯)
* **Sprint 9: Data Integration & Code Hygiene**
  - [ ] **YFinance Service Split (Issue #66):** Refactor `YFinanceService` to clearly separate real-time price fetching from metadata cache operations, preventing service coupling.
  - [ ] **Real-data Sector & Country Allocations (Issues #32, #57 & #60):** Fetch sector and country metadata from Yahoo Finance, cache them in `SQLiteISINCache`, and render separate Sector and Geographical Donut Charts on the dashboard.
  - [ ] **Stateful AI Chat (Issues #29 & #61):** Implement `/api/chat` to allow follow-up conversations with Gemini, persisting chat history in the SQLite database.
  - [ ] **Stateful AI Analysis & Cooldown (Issue #63):** Implement rate-limited, on-demand portfolio analysis cached in SQLite with a 7-day cooldown to prevent API cost spam.
  - [ ] **Architectural Session Decoupling (Issue #67):** Refactor the service and API layers to fully decouple them from raw SQLAlchemy sessions, ensuring clean transactional boundaries.
  - [ ] **Route Profiling Middleware (Issue #68):** Design and implement a reusable decorator or middleware to profile API endpoint latencies and log performance bottlenecks.
  - [ ] **Timezone-Aware UTC Datetimes (Issue #69):** Audit and enforce consistent, timezone-aware UTC datetime fields across all SQLite models, preventing timezone offset bugs.
  - [ ] **Automated SEC 13F Sync (Issue #62):** Implement a quarterly sync that fetches real-time elite holdings (Warren Buffett, Bridgewater, Scion) to dynamically update guest demo profiles.

### Phase 7: Historical Performance & Advanced Analytics (Upcoming 🚀)
* **Sprint 10: Historical Tracking & Benchmarking**
  - [ ] Implement database models (`PortfolioHistory`) to periodically store daily portfolio valuation snapshots.
  - [ ] Render a historical performance line chart on the dashboard.
  - [ ] Implement benchmarking to compare portfolio returns against major market indices (e.g., S&P 500, MSCI World).
* **Sprint 11: ETF Look-Through & Multi-Language**
  - [ ] **ETF Look-Through (Issue #33):** Support breaking down ETFs into their raw individual constituent holdings for deeper risk analysis.
  - [ ] **Localization (Issue #30):** Implement multi-language localization (EN, CS, FR, DE) for both the UI dashboard and the AI evaluation output.
