# AI Portfolio Assistant - Roadmap

Welcome to the official roadmap for the open-source **AI Portfolio Assistant**! This document outlines our phases, milestones, and progress towards a production-ready, AI-enhanced portfolio management application.

---

## 🚀 Vision
A lightweight, privacy-focused, and broker-agnostic web application that parses multiple broker exports (CSV), aggregates them into a unified dashboard with real-time valuations, and leverages Google Gemini to provide interactive financial analysis, market catalyst news, and Czech tax-reporting assistance.

---

## 📌 High-Level Roadmap

### Phase 1: Core Engine & Local Pipeline (Completed 🎉)
* **Sprint 1: Base Infrastructure & Parsers**
  - [x] Set up strict python template, FastAPI, MyPy, Ruff, Pytest, and CI/CD pipelines.
  - [x] Implement Degiro CSV parser (`ImportedPortfolio`).
* **Sprint 2: Real-time Valuation Engine**
  - [x] Create `BaseMarketDataService` and `YFinanceMarketDataService` (async wrapper for `yfinance`).
  - [x] Build the `ValuationService` to calculate current portfolio values and weights in `target_currency` (e.g., CZK).

### Phase 2: Web Dashboard & Secure Cloud Deployment (Completed 🎉)
* **Sprint 3: Web Dashboard (Tailwind UI & Chart.js)**
  - [x] Implement secure FastAPI upload routes and HTML dashboard using Jinja2 styled with Tailwind.
  - [x] Integrate Chart.js via secure CDN (HTML5 data attributes, avoiding unsafe filters) to render asset allocation.
* **Sprint 4: Production Deployment & Hardened Security**
  - [x] Create optimized multi-stage Dockerfile and configure automated, tag-based CI/CD pipelines in GitHub Actions.
  - [x] Deploy the application live to Google Cloud Run utilizing secure environments.
  - [x] Implement Basic Authentication with timing-attack mitigation (`secrets.compare_digest`) and Pydantic-based "fail-closed" production validation.

### Phase 3: AI Integration & Broker Aggregation (Current Focus 🎯)
* **Sprint 5: Gemini AI Portfolio Analysis (v0.4.0)**
  - [x] Integrate official unified `google-genai` SDK asynchronously.
  - [x] Build Gemini AI Advisor service adhering to privacy-by-design (transmitting only anonymized tickers and weights).
  - [x] Secure LLM prompt inputs with Pydantic-level regex validation for ticker symbols.
  - [x] Ensure safe client-side Markdown rendering via CDNs for `marked.js` and `DOMPurify` to mitigate XSS vectors.
* **Sprint 6: Dynamic Data Resolution & Multi-Broker Support (Next!)**
  - [ ] Implement `ISINResolver` using Yahoo Finance Search API to dynamically map European ISINs to tickers, utilizing a local persistent disk cache (SQLite/JSON) to eliminate the hardcoded map.
  - [ ] Create parsers for additional popular brokers (e.g., `XtbPortfolioParser`, `Trading212PortfolioParser`, `PortuPortfolioParser`).
  - [ ] Develop a "Portfolio Merging Engine" to aggregate and average multiple broker CSVs into a single consolidated view on the dashboard.

### Phase 4: Interactive Interactions & Financial Analytics
* **Sprint 7: Interactive Portfolio Chat**
  - [ ] Add an interactive chat interface allowing users to discuss their portfolio contextually with the Gemini Assistant.
  - [ ] Maintain secure, stateless session context or lightweight, ephemeral chat history.
* **Sprint 8: Historical Transactions & Czech Tax Reporting**
  - [ ] Implement transaction-level parsers (tracking buy, sell, and dividend transactions over time).
  - [ ] Develop a Czech Tax Statement Generator utilizing FIFO methodologies, official Czech National Bank (ČNB) exchange rates on transaction dates, and 3-year time-test validation.
* **Sprint 9: Real-time News Synthesis (Catalyst Analysis)**
  - [ ] Integrate `yfinance` real-time news feed fetcher.
  - [ ] Train Gemini to synthesize these recent articles into a "News Catalyst" summary, highlighting recent events impacting specific portfolio holdings.

---

## 🛠️ Tech Stack Alignment
- **Backend:** Python 3.11+, FastAPI, Pydantic V2, Ruff, MyPy (strict=True)
- **Data:** `decimal.Decimal` (strictly used for all monetary calculations), `yfinance`, SQLite (for metadata caching)
- **Frontend:** Jinja2 HTML Templates, Tailwind CSS, Chart.js, Marked.js, DOMPurify
- **Hosting:** Docker, GitHub Actions (CI/CD), Google Cloud Run & Cloud Build
