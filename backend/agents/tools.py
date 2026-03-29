import os
import pandas as pd
from sqlalchemy import create_engine, desc
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
from .sub_agents import run_all_agents
from .chief_agent import evaluate_signals

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, poolclass=NullPool)

def resolve_symbol(symbol: str, engine):
    """
    Resolves a symbol to its database equivalent:
    1. Exact match.
    2. Try suffixing .NS (for NSE stocks).
    3. Fuzzy match using difflib.
    4. If not in DB, fetch from yfinance.
    """
    import difflib
    from sqlalchemy import text
    
    # Normalize input
    symbol = symbol.strip().upper()
    
    # 1. Check exact match & .NS extension
    options_to_check = [symbol, f"{symbol}.NS"]
    with engine.connect() as conn:
        for opt in options_to_check:
            exists = conn.execute(
                text("SELECT 1 FROM stock_prices WHERE symbol = :s LIMIT 1"), {"s": opt}
            ).fetchone()
            if exists:
                return opt, "Direct/Suffix Match"
        
        # 2. Fuzzy match against all symbols in DB
        all_symbols = [r[0] for r in conn.execute(text("SELECT DISTINCT symbol FROM stock_prices")).fetchall()]
        matches = difflib.get_close_matches(symbol, all_symbols, n=1, cutoff=0.6)
        if matches:
            return matches[0], "Fuzzy Match"
            
    # 3. Last Resort: Try yfinance to see if it even exists on NSE
    # We only auto-fetch for .NS stocks for now
    yf_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    try:
        import yfinance as yf
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="5d")
        if not hist.empty:
            print(f"📦 [Resolver] {yf_symbol} not in DB, but found on Yahoo Finance. Triggering on-the-fly sync...")
            fetch_and_save_ohlcv(yf_symbol, engine)
            return yf_symbol, "New Fetch"
    except Exception as e:
        print(f"⚠️ [Resolver] Failed yfinance lookup for {yf_symbol}: {e}")
        
    return None, None

def fetch_and_save_ohlcv(symbol, engine):
    """Fetch 1 year of data from yfinance, calculate indicators, and save to DB."""
    import yfinance as yf
    from .historical_backtest import prepare_indicators
    from sqlalchemy import text
    
    print(f"⬇️ [AutoSync] Fetching 1yr of data for {symbol}...")
    df = yf.download(symbol, period="1y")
    if df.empty:
        return False
        
    # Standardize columns
    df = df.reset_index()
    # Handle multi-index if necessary (yf 1.2.0 sometimes does this)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df = df.rename(columns={
        "Date": "trading_date",
        "Open": "open_price",
        "High": "high_price",
        "Low": "low_price",
        "Close": "close_price",
        "Volume": "volume"
    })
    
    # Calculate indicators using existing logic from backtester
    df_with_inds = prepare_indicators(df)
    
    # Upsert into DB
    insert_sql = text("""
        INSERT INTO stock_prices (symbol, trading_date, open_price, high_price, low_price, close_price, volume, rsi_14, ema_20, ema_50)
        VALUES (:symbol, :trading_date, :open, :high, :low, :close, :volume, :rsi, :ema20, :ema50)
        ON CONFLICT DO NOTHING
    """)
    
    with engine.connect() as conn:
        for _, row in df_with_inds.iterrows():
            conn.execute(insert_sql, {
                "symbol": symbol,
                "trading_date": row["trading_date"],
                "open": float(row["open_price"]),
                "high": float(row["high_price"]),
                "low": float(row["low_price"]),
                "close": float(row["close_price"]),
                "volume": float(row["volume"]),
                "rsi": float(row["rsi"]) if not pd.isna(row["rsi"]) else None,
                "ema20": float(row["ema20"]) if not pd.isna(row["ema20"]) else None,
                "ema50": float(row["ema50"]) if not pd.isna(row["ema50"]) else None,
            })
        conn.commit()
    print(f"✅ [AutoSync] Saved {len(df_with_inds)} rows for {symbol} to DB.")
    return True

def market_scanner_tool():
    """
    Scans the market for the best stocks to buy right now.
    Returns a list of top 5 stocks with BUY signals and high conviction.
    """
    print("🔍 [Market Scanner] Loading stock data...")
    query = "SELECT * FROM stock_prices ORDER BY symbol, trading_date"
    df_all = pd.read_sql(query, engine)
    stock_data = {symbol: group.reset_index(drop=True) for symbol, group in df_all.groupby("symbol")}
    
    results = []
    for symbol, df in stock_data.items():
        if len(df) < 50:
            continue
            
        signals = run_all_agents(df)
        if not signals:
            continue
            
        latest_bar = df.iloc[-1].to_dict()
        evaluation = evaluate_signals(symbol, signals, latest_bar)
        
        if evaluation["final_signal"] in ["BUY", "SELL"]:
            results.append({
                "symbol": symbol,
                "confidence": evaluation["conviction"],
                "pattern": evaluation["dominant_pattern"],
                "reasoning": evaluation["reasoning"],
                "price": latest_bar["close_price"],
                "signal": evaluation["final_signal"]
            })
            
    # Sort by confidence (absolute strength of signal)
    results = sorted(results, key=lambda x: x["confidence"], reverse=True)
    return results[:8] # Return top 8 most actionable signals

def stock_deep_dive_tool(symbol: str):
    """
    Provides a deep dive for a specific stock ticker.
    Returns technical signals and historical pattern performance.
    """
    resolved_symbol, method = resolve_symbol(symbol, engine)
    
    if not resolved_symbol:
        return {"error": f"Symbol '{symbol}' could not be resolved or found online."}
    
    if method != "Direct/Suffix Match":
        print(f"✨ [Resolver] Resolved '{symbol}' to '{resolved_symbol}' via {method}")
    
    print(f"🔍 [Deep Dive] Analyzing {resolved_symbol}...")
    query = f"SELECT * FROM stock_prices WHERE symbol = '{resolved_symbol}' ORDER BY trading_date"
    df = pd.read_sql(query, engine)
    
    if df.empty:
        # This shouldn't happen if resolve_symbol/fetch_and_save_ohlcv worked, but safety first
        return {"error": f"Could not retrieve price history for {resolved_symbol}."}
        
    signals = run_all_agents(df)
    latest_bar = df.iloc[-1].to_dict()
    evaluation = evaluate_signals(resolved_symbol, signals, latest_bar)
    
    # Also fetch historical pattern info from DB if available
    # (Checking detected_patterns table)
    from sqlalchemy import text
    with engine.connect() as conn:
        pattern_query = text(f"SELECT * FROM detected_patterns WHERE symbol = :symbol AND is_dominant = True LIMIT 1")
        dominant = conn.execute(pattern_query, {"symbol": resolved_symbol}).fetchone()
        
    return {
        "symbol": resolved_symbol,
        "evaluation": evaluation,
        "current_price": latest_bar["close_price"],
        "signals_detected": signals,
        "historical_dominant_pattern": {
            "name": dominant.pattern_name if dominant else "Unknown",
            "win_rate": dominant.win_rate if dominant else 0,
            "sharpe": dominant.sharpe_ratio if dominant else 0
        } if dominant else None
    }
