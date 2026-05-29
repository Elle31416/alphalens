# AlphaLens 🔍

**Alternative-data earnings signal platform** built with Bright Data + Grok (xAI).

Scrapes LinkedIn job postings, Amazon pricing, App Store ratings, and SEC filings
nightly — then runs each data stream through a Grok signal chain and produces a
composite earnings-surprise probability score for each ticker.

Budget: $250 Bright Data credits · ~$65–120 spend to run the full demo.

---

## Architecture

```
alphalens/
├── scrapers/
│   ├── linkedin_jobs.py      ← Bright Data Web Scraper API (hiring velocity)
│   ├── amazon_pricing.py     ← Bright Data Web Unlocker  (pricing delta)
│   ├── appstore_ratings.py   ← Bright Data Scraping Browser (JS rendering)
│   └── sec_edgar.py          ← Free SEC EDGAR public API
│
├── pipeline/
│   ├── scheduler.py          ← APScheduler nightly orchestrator
│   ├── db.py                 ← PostgreSQL helpers
│   └── schema.sql            ← DB schema (auto-applied by Docker)
│
├── ai/
│   ├── signal_chain.py       ← 4 Grok chains (one per data source)
│   └── langgraph_orchestrator.py ← LangGraph composite scoring
│
├── api/
│   └── main.py               ← FastAPI REST backend
│
└── frontend/                 ← Next.js 14 + Recharts dashboard
    ├── pages/index.tsx        → Watchlist table
    ├── pages/ticker/[symbol]  → Ticker detail (4 panels)
    ├── pages/backtest.tsx     → Historical backtest demo
    └── lib/api.ts             → API client + types
```

---

## Quick Start

### 1. Prerequisites

```bash
python --version   # 3.11+
node --version     # 20+
docker --version   # any recent
```

### 2. Clone & configure

```powershell
git clone <repo>
cd alphalens

# Copy environment template
copy .env.example .env

# Edit .env — add your Bright Data + xAI credentials
```

### 3. Start PostgreSQL

```powershell
# Ensure Docker Desktop is running
# If 'docker compose' fails, try 'docker-compose'
docker compose up db -d
```

### 4. Install Python dependencies

```powershell
# Create and activate virtual environment (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
playwright install chromium

# To exit the virtual environment
deactivate
```

### 5. Start the API

```powershell
# Run as a module to ensure the venv version is used
python -m uvicorn api.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### 6. Start the Next.js dashboard

```bash
```powershell
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### 7. Run the pipeline (mock mode for testing)

```bash
# Mock mode — no Bright Data credits spent
USE_MOCK_DATA=true python -m pipeline.scheduler --now
```powershell
# Mock mode — no Bright Data credits spent (PowerShell syntax)
$env:USE_MOCK_DATA="true"; python -m pipeline.scheduler --now

# Live mode — uses real scrapers
python -m pipeline.scheduler --now
$env:USE_MOCK_DATA="false"; python -m pipeline.scheduler --now
```

---

## Hosting on Render

### 1. Database
Create a **Render PostgreSQL** instance. Copy the **Internal Database URL** for the backend/worker.

### 2. Backend (FastAPI)
Create a **Web Service**:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables**: Add `DATABASE_URL`, `XAI_API_KEY`, and Bright Data credentials.

### 3. Scheduler (Background Worker)
Create a **Background Worker**:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python -m pipeline.scheduler`
- **Environment Variables**: Same as Backend.

### 4. Frontend (Next.js)
Create a **Web Service**:
- **Root Directory**: `frontend`
- **Build Command**: `npm install && npm run build`
- **Start Command**: `npm run start`
- **Environment Variables**: `NEXT_PUBLIC_API_URL` (points to your Backend URL).

---

## Bright Data Zone Setup

In your [Bright Data dashboard](https://brightdata.com):

| Zone name                 | Product             | Used by              |
|---------------------------|---------------------|----------------------|
| `alphalens-residential`   | Residential Proxies | App Store scraper    |
| `alphalens-unlocker`      | Web Unlocker        | Amazon pricing       |
| `alphalens-scraper-api`   | Web Scraper API     | LinkedIn jobs        |

Copy zone credentials to `.env`.

---

## API Endpoints

| Method | Path                      | Description                           |
|--------|---------------------------|---------------------------------------|
| GET    | `/signals`                | Latest composite signals (all tickers)|
| GET    | `/signals/{ticker}`       | Historical signals for one ticker     |
| GET    | `/signals/export/csv`     | Download signals as CSV               |
| GET    | `/tickers`                | Watchlist configuration               |
| POST   | `/tickers`                | Add a ticker                          |
| POST   | `/pipeline/run`           | Trigger pipeline manually             |
| GET    | `/backtest`               | Backtest results                      |
| GET    | `/health`                 | Health check                          |

---

## Budget Breakdown

| Item                              | Estimated Cost |
|-----------------------------------|----------------|
| Web Scraper API (LinkedIn)        | ~$35/mo        |
| Web Unlocker (Amazon)             | ~$25/mo        |
| Residential Proxies (App Store)   | ~$20/mo        |
| Scraping Browser (renders JS)     | ~$15/mo        |
| Grok API (grok-3-mini)            | ~$6/mo         |
| **Buffer remaining**              | **~$145**      |

---

## Disclaimer

For educational / hackathon use only. Not financial advice.
Always comply with the terms of service of any platform you scrape.
