# AI Portfolio Assistant - Roadmap

Welcome to the official roadmap for the open-source **AI Portfolio Assistant**! This document outlines our phases, milestones, and progress towards a production-ready, AI-enhanced portfolio management application.

---

## 🚀 Vision
A lightweight, privacy-focused web application that parses broker exports (CSV/PDF), calculates real-time asset valuations in a target currency, and leverages Google Gemini to provide tailored risk analysis and aggregated news.

---

## 📌 High-Level Roadmap

### Phase 1: Core Engine & Local Pipeline (Completed 🎉)
* **Sprint 1: Base Infrastructure & Parsers**
  - [x] Set up strict python template, FastAPI, MyPy, Ruff, Pytest, and CI/CD pipelines.
  - [x] Implement Degiro CSV parser (`ImportedPortfolio`).
* **Sprint 2: Real-time Valuation Engine**
  - [x] Create `BaseMarketDataService` and `YFinanceMarketDataService` (async wrapper for `yfinance`).
  - [x] Build the `ValuationService` to calculate current portfolio values and weights in `target_currency` (e.g., CZK).

### Phase 2: Web Interface & Production Deployment (Current Focus 🎯)
* **Sprint 3: Web Dashboard (Tailwind UI)**
  - [ ] Implement simple FastAPI routes to allow CSV file upload.
  - [ ] Render a responsive dashboard using HTML templates (Jinja2) styled with Tailwind CSS (served via CDN/static).
  - [ ] Display portfolio metrics (Total value, Currency breakdown, Position table with weights).
  - [ ] Add a basic client-side chart (e.g., Chart.js via CDN) showing asset allocation.
* **Sprint 4: Deployment & Hosting**
  - [ ] Configure `Dockerfile` for the FastAPI application.
  - [ ] Set up CD (Continuous Delivery) via GitHub Actions.
  - [ ] Deploy the application to a cloud provider (e.g., Render, Fly.io, or Hugging Face Spaces).

### Phase 3: AI Insights & Advanced Features
* **Sprint 5: AI Advisor & News Aggregator**
  - [ ] Integrate Google Gemini API securely.
  - [ ] Build the AI Advisor service to analyze `ValuedPortfolio` for risk metrics and diversification.
  - [ ] Set up RSS/Financial News aggregation filtered by portfolio tickers.
  - [ ] Render "AI Insights" directly on the dashboard.
* **Sprint 6: Anonymized Workflows & Community Features**
  - [ ] Implement `AnonymizedPortfolioParser` (relative weights import) for maximum privacy.
  - [ ] Polish exporting capabilities (e.g., download anonymized PDF or shareable LinkedIn reports).

---

## 🛠️ Tech Stack Alignment
- **Backend:** Python 3.11+, FastAPI, Pydantic V2, Ruff, MyPy (strict=True)
- **Data:** `decimal.Decimal` (strictly used for all monetary calculations), `yfinance`
- **Frontend:** Jinja2 HTML Templates, Tailwind CSS, Chart.js
- **Hosting:** Docker, GitHub Actions (CI/CD)
