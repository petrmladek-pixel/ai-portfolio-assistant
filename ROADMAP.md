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

### Phase 6: Caching, Real-Data Visuals & Client-Side Reactivity (Completed 🎉)
* **Sprint 9: Real-Time Cache Split & Stateless Engine**
  - [x] **Timezone-Aware UTC Datetimes (Issue #69):** Audit and enforce consistent, timezone-aware UTC datetime fields across all SQLite models, preventing timezone offset bugs.
  - [x] **Stateless Allocation Engine (Issue #70):** Implement isolated `AllocationService` and schema wrappers utilizing `decimal.Decimal` calculations.
  - [x] **YFinance Cache Separation (Issue #71):** Refactor yfinance operations into `PriceCacheService` (15-min TTL) and `MetadataCacheService` (30-day TTL) to decouple pricing from structural metadata.
* **Sprint 10: Unified Dashboard Reactive Refactoring**
  - [x] **Unified Frontend Fetching (Issue #77):** Integrate a single client-side Alpine.js controller to dynamically fetch asset allocations for the selected portfolio.
  - [x] **Non-Reactive Chart.js Mounting (Issue #78):** Render responsive Doughnut charts on a clean canvas wrapper, managing the layout and instance destruction outside Alpine's Proxy boundaries to preserve hover tooltips and prevent leaks.
  - [x] **Position-Based Calculation:** Refactor the calculation pipeline to compute aggregates and cash allocations directly from the `Position` table.
  - [x] **Global Portfolio Aggregations:** Implement the static `/api/portfolios/all/allocations` router endpoint for unified, multi-portfolio analytics.

### Phase 7: Real-Time AI Diagnostics & Stateful Chat (Current Focus 🎯)
* **Sprint 11: AI Portfolio Copilot & Stateful Analysis**
  - [ ] **Stateful AI Analysis Cache & Cooldown (Issue #63):** Implement an on-demand portfolio analysis endpoint, caching Gemini's structured Markdown evaluation in SQLite with a 7-day cooldown to prevent API cost spam.
  - [ ] **Stateful AI Chat (Issues #29 & #61):** Build a responsive backend service for follow-up chat interactions with Gemini, persisting conversation histories tied to individual portfolios.
  - [ ] **Client-Side Copilot Integration:** Populate the dashboard's "AI Portfolio Copilot" widget, supporting asynchronous streaming, loading indicators, and markdown formatting.
  - [ ] **Route Profiling Middleware (Issue #68):** Design and implement a reusable decorator or middleware to profile API endpoint latencies and log performance bottlenecks.
