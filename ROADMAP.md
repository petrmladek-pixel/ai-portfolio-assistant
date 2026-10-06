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
  - [x] Render a responsive dashboard using HTML templates (Jinja2) styled with Tailwind CSS.
  - [x] Display portfolio metrics (Total value, Currency breakdown, Position table with weights).
  - [x] Add a client-side chart (Chart.js) showing asset allocation.
* **Sprint 4: Production Deployment & GCP Hosting**
  - [x] Configure `Dockerfile` and automated CD via GitHub Actions.
  - [x] Deploy application to **Google Cloud Run** using Cloud Build triggers.
  - [x] Secure dashboard with Basic Authentication and Pydantic fail-closed validation.
  - [x] Safely parse and sanitize Gemini's Markdown analysis using `marked.js` and `DOMPurify`.

### Phase 3: Secure Ingestion, Multi-Broker & Code Hygiene (Completed 🎉)
* **Sprint 5: Dynamic Resolution & Fio e-Broker Support**
  - [x] Eliminate static `ISIN_TO_TICKER` dictionaries.
  - [x] Implement asynchronous `YahooISINResolver` with local `SQLiteISINCache`.
  - [x] Implement exact-match round-trip validation on Yahoo Search API.
  - [x] Establish abstract parser base class `BasePortfolioParser` with automatic file encoding detection.
  - [x] Implement `FioBrokerPortfolioParser` and mathematical `PortfolioMerger`.
  - [x] Create automated code hygiene Pytest checking for accidental Czech diacritics in Python files.

### Phase 4: Persistence, User Identity & Multi-Portfolio (Completed 🎉)
* **Sprint 6: Database Storage & User Accounts**
  - [x] Refactor upload endpoint to make individual broker files optional.
  - [x] Set up local SQLite database via **SQLAlchemy/SQLModel**.
  - [x] Implement secure password hashing (`bcrypt`) and HttpOnly cookie-based JWT authentication.
  - [x] Persist parsed/merged positions into database.
* **Sprint 7: SRE Hardening, Migrations & Layered Architecture**
  - [x] **CD Keyless Deployment:** WIF authentication on GCP and optimized Docker build caching.
  - [x] **Cost Guardrails:** Budget alerts ($10) and Cloud Run scaling caps.
  - [x] **Alembic Migrations:** Programmatic DB migrations on application startup.
  - [x] **Pragmatic Layered Architecture:** Strict 3-tier layering (Routers -> Services -> CRUD).
  - [x] **Multi-Portfolio DB Schema:** Support separate accounts per broker/user.

### Phase 5: Premium Visual Facelift & DB Persistence Onboarding (Completed 🎉)
* **Sprint 8: Swiss-Style UI & Unified Persistence**
  - [x] **Swiss-Style Dashboard Facelift:** Modular Jinja2 sub-components with minimalist layout.
  - [x] **Unified Upload Form:** Target portfolio selection and simplified import type.
  - [x] **Self-Healing DB & Startup Seeding:** Automatic DB seeder on startup for demo portfolios.

### Phase 6: Caching, Real-Data Visuals & Client-Side Reactivity (Completed 🎉)
* **Sprint 9: Real-Time Cache Split & Stateless Engine**
  - [x] **Timezone-Aware UTC Datetimes (Issue #69):** Audit and enforce consistent UTC datetimes.
  - [x] **Stateless Allocation Engine (Issue #70):** Isolated `AllocationService` using `decimal.Decimal`.
  - [x] **YFinance Cache Separation (Issue #71):** Split pricing cache (15-min TTL) and metadata cache (30-day TTL).
* **Sprint 10: Unified Dashboard Reactive Refactoring**
  - [x] **Unified Frontend Fetching (Issue #77):** Single Alpine.js controller for asset allocations.
  - [x] **Non-Reactive Chart.js Mounting (Issue #78):** Render responsive charts outside Alpine Proxy boundaries.

### Phase 7: Strategic AI Analysis & Investment Personas (Completed 🎉)
* **Sprint 11: Configurable Investment Personas & Full Canvas (Issues #63, #61, #29)**
  - [x] **Investment Personas:** Support for Warren Buffett / Value, Growth, and Custom personas.
  - [x] **User Context Injection:** Allow user qualitative notes (`user_context`) to guide AI reasoning.
  - [x] **Full-Width Strategic Canvas:** Dedicated full-width Swiss-style Markdown reading canvas with Tailwind `.prose`.
  - [x] **Stateful Caching & Cooldown:** 7-day SQLite cache with SHA256 portfolio hash invalidation.
  - [x] **Persistent AI Chat:** Stateful conversation history tied to individual portfolios.

### Phase 8: Production Launch, Demo Seed & Portfolio Showcase (Current Focus 🎯)
* **Sprint 12: Production Readiness & Pre-Launch Prep**
  - [ ] **Instant Demo Portfolio Seeder (Issue #62):** One-click Warren Buffett / Berkshire Hathaway demo portfolio seeding for instant recruiter preview without uploading files.
  - [ ] **Production Hosting Config:** Render.com / Fly.io Docker deployment setup with persistent SQLite storage volume.
  - [ ] **Automated Integration Tests:** Comprehensive Pytest coverage for AI payload edge cases and UI payloads.
  - [ ] **Showcase Documentation & Architecture Diagram:** LinkedIn-ready `README.md` with Mermaid.js architecture chart and technical highlights.

---

## 💡 Future Backlog (Post-Launch)
- **Issue #68:** Reusable Route Profiling Decorator / Latency Middleware
- **Issue #45:** Double-Submit Cookie CSRF Protection
- **Issue #33:** ETF Look-Through Holdings Breakdown
