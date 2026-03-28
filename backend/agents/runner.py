import os
import pandas as pd
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

from .sub_agents import run_all_agents
from .chief_agent import evaluate_signals

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────
DEV_MODE = True  # Set to False to scan all symbols

DB_URL = os.getenv("DATABASE_URL")
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DB_URL, poolclass=NullPool)


def load_stock_data():
    """Load all stock_prices from Supabase, return dict of {symbol: DataFrame}."""
    query = "SELECT * FROM stock_prices ORDER BY symbol, trading_date"
    df = pd.read_sql(query, engine)
    return {symbol: group.reset_index(drop=True) for symbol, group in df.groupby("symbol")}


def save_detected_pattern(symbol, evaluation, latest_close):
    """Write one final row to detected_patterns table."""
    insert_query = text("""
        INSERT INTO detected_patterns 
            (symbol, pattern_name, signal_type, confidence, detected_at, current_price, remarks, is_active)
        VALUES 
            (:symbol, :pattern_name, :signal_type, :confidence, :detected_at, :current_price, :remarks, :is_active)
    """)
    with engine.connect() as conn:
        conn.execute(insert_query, {
            "symbol": symbol,
            "pattern_name": evaluation["dominant_pattern"],
            "signal_type": evaluation["final_signal"],
            "confidence": evaluation["conviction"],
            "detected_at": date.today().isoformat(),
            "current_price": float(latest_close),
            "remarks": evaluation["reasoning"],
            "is_active": True,
        })
        conn.commit()


def run():
    print("=" * 60)
    print("🚀 Multi-Agent Pattern Detection System")
    print("=" * 60)

    # 1. Load all stock data
    print("\n📊 Loading stock data from Supabase...")
    stock_data = load_stock_data()
    symbols = list(stock_data.keys())

    if DEV_MODE:
        symbols = symbols[:5]
        print(f"⚡ DEV_MODE: Limiting to {len(symbols)} symbols: {symbols}")
    else:
        print(f"📈 Scanning {len(symbols)} symbols")

    # 2. Process each symbol
    total_signals_written = 0
    breakdown = {"BUY": 0, "SELL": 0, "HOLD": 0}

    for symbol in symbols:
        df = stock_data[symbol]
        if len(df) < 50:
            print(f"  ⏭  {symbol}: Not enough data ({len(df)} rows), skipping")
            continue

        # a. Run all 10 sub-agents
        signals = run_all_agents(df)

        # b. If no signals, skip
        if not signals:
            print(f"  ⬚  {symbol}: No signals detected")
            continue

        print(f"  🔍 {symbol}: {len(signals)} signal(s) detected → ", end="")

        # c. Call Chief Agent
        latest_bar = df.iloc[-1].to_dict()
        evaluation = evaluate_signals(symbol, signals, latest_bar)

        final_signal = evaluation.get("final_signal", "HOLD")
        conviction = evaluation.get("conviction", 0.0)
        dominant = evaluation.get("dominant_pattern", "Unknown")

        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(final_signal, "⚪")
        print(f"{emoji} {final_signal} (conviction: {conviction:.2f}, pattern: {dominant})")

        # d. Save to detected_patterns
        try:
            save_detected_pattern(symbol, evaluation, latest_bar["close_price"])
            total_signals_written += 1
            breakdown[final_signal] = breakdown.get(final_signal, 0) + 1
        except Exception as e:
            print(f"    ❌ Failed to save: {e}")

    # 3. Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print(f"   Symbols scanned : {len(symbols)}")
    print(f"   Signals written : {total_signals_written}")
    print(f"   🟢 BUY          : {breakdown['BUY']}")
    print(f"   🔴 SELL         : {breakdown['SELL']}")
    print(f"   🟡 HOLD         : {breakdown['HOLD']}")
    print("=" * 60)


if __name__ == "__main__":
    run()
