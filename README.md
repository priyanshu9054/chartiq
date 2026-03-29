# ChartIQ

ChartIQ is a project that turns raw NSE market data into an AI-assisted stock intelligence dashboard. It combines technical pattern detection, historical backtesting, and a conversational analyst experience so users can quickly screen stocks, inspect trade signals, and ask follow-up questions in natural language.

## What It Does

- Scans a basket of NSE stocks and surfaces detected technical patterns
- Highlights the latest signal, confidence score, and dominant historical setup for each stock
- Shows stock-level detail pages with price context and backtest-style metrics
- Adds an AI chat layer that explains signals, answers market questions, and provides reasoning
- Stores market data, detected patterns, and chat history in a Postgres-compatible database

## Why It’s Useful

Retail investors and analysts often jump between charts, screeners, and research notes to understand one trading idea. ChartIQ brings those pieces together into one interface:

- Quant signals for fast discovery
- Historical evidence for trust
- AI explanations for accessibility

## Stack

### Frontend

- React
- Vite
- Tailwind CSS
- React Router
- Recharts
- Axios

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL / Supabase
- LangGraph + LangChain
- OpenAI
- yfinance
- pandas + pandas-ta

## Core Features

### 1. Stock Screener

The home screen lists tracked stocks with:

- latest signal (`BUY`, `SELL`, or `HOLD`)
- confidence score
- dominant pattern
- historical win rate

### 2. Stock Detail View

Each stock page shows:

- current price and change
- AI-generated reasoning / remarks
- backtest proof metrics across multiple holding periods
- simple trend visualization

### 3. AI Analyst Chat

Users can ask questions like:

- "What are the best stocks right now?"
- "Is RELIANCE a good buy?"
- "What is the dominant pattern for this stock?"

The backend routes the query, pulls relevant context, and generates a structured response using an LLM-powered workflow.

### 4. Data Pipeline

The project includes a market data pipeline that:

- pulls historical OHLCV data from Yahoo Finance
- computes indicators like RSI and EMA
- stores cleaned records in the database

## Project Structure

```text
chartiq/
├── backend/
│   ├── api/                # FastAPI app and endpoints
│   ├── agents/             # LLM agents and orchestration logic
│   ├── data/               # Data ingestion scripts and symbol lists
│   ├── patterns/           # Pattern scanning logic
│   ├── scripts/            # SQL / setup helpers
│   └── requirements.txt
├── frontend/
│   ├── src/components/     # Shared UI components
│   ├── src/pages/          # Screener and stock detail pages
│   ├── src/lib/            # API client
│   └── package.json
└── README.md
```

## How It Works

### High-level flow

1. Historical stock data is fetched and stored in the database.
2. Pattern detection / strategy logic evaluates stocks and records signals.
3. The frontend calls the FastAPI backend to load screener and detail data.
4. Chat requests are passed into a LangGraph-based workflow:
   - route user intent
   - run strategist logic when needed
   - synthesize a final response

## API Overview

The backend currently exposes:

- `GET /api/stocks` - screener data for all tracked symbols
- `GET /api/signals/{symbol}` - active and historical signals for a stock
- `GET /api/leaderboard` - aggregated pattern leaderboard
- `POST /api/chat` - AI analyst chat endpoint

## Local Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd chartiq
```

### 2. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/` with:

```env
DATABASE_URL=your_postgres_connection_string
OPENAI_API_KEY=your_openai_api_key
```

Notes:

- The backend expects `DATABASE_URL` or `SUPABASE_URL`
- A Supabase Postgres database should also work

Run the backend:

```bash
cd backend/api
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The frontend is configured to call the backend at:

```text
http://localhost:8000
```

and Vite runs by default on:

```text
http://localhost:5173
```

## Data Ingestion

To populate stock price data:

```bash
cd backend
python data/fetch_pipeline.py
```

This script fetches roughly 1 year of daily data for a NIFTY stock universe and computes basic indicators before writing to the database.

## What is project about?

ChartIQ helps users understand market opportunities faster by combining a technical screener, historical signal evidence, and an AI analyst in one product. Instead of forcing users to switch between charts, indicators, and research notes, it gives them a single workflow:

- discover high-interest NSE stocks through quantitative screening
- inspect the pattern and confidence behind each signal
- validate ideas with historical win-rate style evidence
- ask natural-language questions to understand why a signal matters

The value of the project is not just prediction, but explainability. It turns noisy market data into a more approachable decision-support experience for traders, learners, and retail investors.

## Demo Flow

1. Start on the screener and show how ChartIQ surfaces tracked NSE symbols with signal type, confidence, dominant pattern, and historical success rate.
2. Open a stock detail page to show the current price snapshot, AI-generated reasoning, and backtest-style proof metrics across multiple holding periods.
3. Launch the chat panel and ask a focused question like `Is RELIANCE a good buy?` or `What is the dominant pattern for this stock?`
4. Close by explaining the full pipeline: market data is ingested, indicators are computed, pattern logic and agent reasoning evaluate the setup, and the frontend turns that into an explainable trading intelligence experience.

## Current Limitations

- The project currently assumes a working Supabase setup and does not yet include a fully polished first-run onboarding flow.
- Some backend and data-layer pieces still reflect hackathon-stage implementation rather than production-grade reliability and cleanup.
- The frontend is currently wired to a local backend URL, so environment-based deployment configuration is still a next step.
- The intelligence layer depends on the current pattern logic, available historical data, and prompt orchestration, which can still be improved for consistency and depth.

## Future Improvements

- Add authentication, watchlists, and saved research sessions.
- Expand coverage beyond the current stock universe into more exchanges and asset classes.
- Improve reasoning transparency with stronger evidence trails, source-aware explanations, and richer pattern breakdowns.
- Add live or near-real-time data updates for a more active market view.



