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

## Hackathon Pitch

ChartIQ is built for fast, explainable market intelligence. Instead of showing only indicators or only AI text, it combines both:

- screen the market quantitatively
- validate ideas with historical context
- explain results conversationally

That makes it easier for users to move from "What should I look at?" to "Why does this signal matter?"

## Demo Flow

For a live demo, you can show:

1. The screener loading live tracked stocks
2. A stock detail page with confidence and backtest metrics
3. The chat panel answering a question about a specific symbol
4. The end-to-end story of data -> signal -> explanation

## Current Limitations

- Local setup assumes a working Postgres-compatible database
- The repo does not yet include a polished root-level environment template
- Some scripts and schema/setup pieces may still need cleanup for production readiness
- The frontend currently points to a local backend URL directly

## Future Improvements

- Add authentication and watchlists
- Support more exchanges and asset classes
- Improve signal explainability with richer source citations
- Add live market data streaming
- Deploy as a hosted demo with managed database setup

