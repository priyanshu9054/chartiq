"""
Historical Backtest Script
==========================
Runs all 10 sub-agents across the FULL historical dataset, saves every detected
signal with the correct trading_date, calculates forward returns at 5/10/30-day
tiers, aggregates pattern stats, and flags dominant patterns.

Usage:
    cd /path/to/chartiq
    source backend/venv/bin/activate
    python -m backend.agents.historical_backtest
"""

import os
import sys
import time
import logging
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

from .sub_agents import run_all_agents
from .chief_agent import evaluate_signals

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backtest")

# ── Config ──────────────────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DEV_MODE = False  # set False for full run
DEV_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]

SCAN_FROM_INDEX = 60       # skip indicator warm-up rows
LOOKBACK_TIERS = [5, 10, 30]
DEDUP_WINDOW = 5           # skip same (symbol, pattern) within N trading days

DB_URL = os.getenv("DATABASE_URL")
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DB_URL, poolclass=NullPool)

# ── Counters ────────────────────────────────────────────────────────────
llm_calls = 0


# ═══════════════════════════════════════════════════════════════════════
# STEP 1 — Vectorized Indicator Pre-Calculation
# ═══════════════════════════════════════════════════════════════════════
def prepare_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pre-calculate ALL technical indicators on the complete dataset for one
    symbol.  Called ONCE per symbol.  Uses pandas_ta for accuracy.
    """
    df = df.sort_values("trading_date").reset_index(drop=True)

    # Core indicators (recalculate on full series for accuracy)
    df["rsi"] = ta.rsi(df["close_price"], length=14)
    df["ema20"] = ta.ema(df["close_price"], length=20)
    df["ema50"] = ta.ema(df["close_price"], length=50)

    # MACD
    macd_df = ta.macd(df["close_price"], fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        macd_cols = [c for c in macd_df.columns if c.startswith("MACD_")]
        sig_cols = [c for c in macd_df.columns if c.startswith("MACDs_")]
        if macd_cols and sig_cols:
            df["macd"] = macd_df[macd_cols[0]]
            df["macd_signal"] = macd_df[sig_cols[0]]

    # Bollinger Bands
    bb = ta.bbands(df["close_price"], length=20)
    if bb is not None and not bb.empty:
        upper_cols = [c for c in bb.columns if c.startswith("BBU_")]
        lower_cols = [c for c in bb.columns if c.startswith("BBL_")]
        if upper_cols and lower_cols:
            df["bb_upper"] = bb[upper_cols[0]]
            df["bb_lower"] = bb[lower_cols[0]]

    # Volume MA
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    # Drop warm-up rows where any key indicator is NaN
    df = df.dropna(subset=["ema50", "macd", "bb_upper"]).reset_index(drop=True)

    return df


# ═══════════════════════════════════════════════════════════════════════
# STEP 5 — Market Regime Filter
# ═══════════════════════════════════════════════════════════════════════
def build_benchmark_series(all_stock_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Build a daily benchmark from the median close_price across all symbols.
    Returns a DataFrame with columns ['trading_date', 'bench_close', 'bench_ema200'].
    """
    frames = []
    for sym, df in all_stock_data.items():
        sub = df[["trading_date", "close_price"]].copy()
        sub = sub.rename(columns={"close_price": sym})
        frames.append(sub.set_index("trading_date"))

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, axis=1)
    bench = pd.DataFrame()
    bench["trading_date"] = combined.index
    bench["bench_close"] = combined.median(axis=1).values
    bench["bench_ema200"] = ta.ema(bench["bench_close"], length=200)
    bench = bench.dropna(subset=["bench_ema200"]).reset_index(drop=True)
    return bench


def get_market_regime(bench_df: pd.DataFrame, current_date) -> str:
    """
    Returns 'BULLISH' or 'BEARISH' based on whether the benchmark median
    close is above/below its 200-day EMA on the given date.
    """
    if bench_df.empty:
        return "BULLISH"

    row = bench_df.loc[bench_df["trading_date"] == current_date]
    if row.empty:
        # Fall back: find nearest date ≤ current_date
        mask = bench_df["trading_date"] <= current_date
        if not mask.any():
            return "BULLISH"
        row = bench_df.loc[mask].iloc[-1:]

    close_val = float(row["bench_close"].iloc[0])
    ema_val = float(row["bench_ema200"].iloc[0])
    return "BEARISH" if close_val < ema_val else "BULLISH"


# ═══════════════════════════════════════════════════════════════════════
# STEP 2 — Historical Scanner Loop
# ═══════════════════════════════════════════════════════════════════════
def scan_symbol_history(symbol: str, df: pd.DataFrame) -> list[dict]:
    """
    For each trading day (after warm-up), run all 10 sub-agents and collect
    qualified signals.  Applies pre-filtering and in-memory deduplication.
    """
    signals = []
    recent_patterns: dict[str, int] = {}  # (pattern_name) → last row index

    for i in range(SCAN_FROM_INDEX, len(df)):
        window = df.iloc[: i + 1]  # full history up to row i
        current_row = df.iloc[i]
        trading_date = current_row["trading_date"]

        try:
            raw_signals = run_all_agents(window)
        except Exception:
            continue

        if not raw_signals:
            continue

        # ── Pre-filter: 2+ agreeing agents OR single confidence > 0.8 ──
        buy_signals = [s for s in raw_signals if s["signal_type"] == "BUY"]
        sell_signals = [s for s in raw_signals if s["signal_type"] == "SELL"]
        high_conf = [s for s in raw_signals if s["confidence"] > 0.8]

        qualified = (
            len(buy_signals) >= 2
            or len(sell_signals) >= 2
            or len(high_conf) >= 1
        )
        if not qualified:
            continue

        # ── Deduplication: skip if same pattern within DEDUP_WINDOW ──
        deduped_signals = []
        for s in raw_signals:
            key = s["pattern_name"]
            last_idx = recent_patterns.get(key)
            if last_idx is not None and (i - last_idx) < DEDUP_WINDOW:
                continue
            deduped_signals.append(s)
            recent_patterns[key] = i

        if not deduped_signals:
            continue

        signals.append(
            {
                "trading_date": trading_date,
                "raw_signals": deduped_signals,
                "current_price": float(current_row["close_price"]),
                "row_index": i,
            }
        )

    return signals


# ═══════════════════════════════════════════════════════════════════════
# STEP 3 — Tiered Lookback Backtest
# ═══════════════════════════════════════════════════════════════════════
LOOKBACK_TIERS = [5, 10, 30]


def calculate_forward_returns(
    df: pd.DataFrame, signal_row_index: int, signal_type: str
) -> list[dict]:
    """
    For a given signal, look forward 5, 10 and 30 days and compute pnl.
    Returns up to 3 dicts (one per tier).
    """
    results = []
    entry_price = float(df.iloc[signal_row_index]["close_price"])

    for days in LOOKBACK_TIERS:
        exit_index = signal_row_index + days
        if exit_index >= len(df):
            continue  # not enough future data

        exit_price = float(df.iloc[exit_index]["close_price"])
        pnl_pct = (exit_price - entry_price) / entry_price * 100

        if signal_type == "BUY":
            outcome = "WIN" if pnl_pct > 1.0 else "LOSS"
        elif signal_type == "SELL":
            outcome = "WIN" if pnl_pct < -1.0 else "LOSS"
        else:
            outcome = "NEUTRAL"

        results.append(
            {
                "exit_price": round(exit_price, 2),
                "pnl_pct": round(pnl_pct, 4),
                "outcome": outcome,
                "lookback_days": days,
            }
        )

    return results


# ═══════════════════════════════════════════════════════════════════════
# DB HELPERS — save & deduplicate
# ═══════════════════════════════════════════════════════════════════════
INSERT_QUERY = text("""
    INSERT INTO detected_patterns
        (symbol, pattern_name, signal_type, confidence, detected_at,
         current_price, remarks, is_active, exit_price, outcome,
         pnl_pct, lookback_days, agent_source, hold_days)
    VALUES
        (:symbol, :pattern_name, :signal_type, :confidence, :detected_at,
         :current_price, :remarks, :is_active, :exit_price, :outcome,
         :pnl_pct, :lookback_days, :agent_source, :hold_days)
""")


def load_existing_keys(conn) -> set[tuple]:
    """Load existing (symbol, pattern_name, detected_at) tuples for dedup."""
    rows = conn.execute(
        text("SELECT symbol, pattern_name, detected_at FROM detected_patterns")
    ).fetchall()
    return {(r[0], r[1], str(r[2])) for r in rows}


def save_signal_batch(conn, rows: list[dict], existing_keys: set[tuple]) -> int:
    """Insert rows that don't already exist. Returns count of rows inserted."""
    inserted = 0
    for row in rows:
        key = (row["symbol"], row["pattern_name"], str(row["detected_at"]))
        if key in existing_keys:
            continue
        conn.execute(INSERT_QUERY, row)
        existing_keys.add(key)
        inserted += 1
    return inserted


# ═══════════════════════════════════════════════════════════════════════
# STEP 4 — Aggregation & is_dominant Flag
# ═══════════════════════════════════════════════════════════════════════
AGGREGATE_SQL = text("""
    WITH stats AS (
        SELECT
            symbol,
            pattern_name,
            lookback_days,
            COUNT(*)                                               AS occ_count,
            COUNT(*) FILTER (WHERE outcome = 'WIN')                AS win_count,
            AVG(pnl_pct)                                           AS avg_ret,
            CASE WHEN STDDEV(pnl_pct) > 0
                 THEN AVG(pnl_pct) / STDDEV(pnl_pct)
                 ELSE 0 END                                        AS sharpe,
            MIN(pnl_pct)                                           AS max_dd
        FROM detected_patterns
        WHERE symbol = :symbol
        GROUP BY symbol, pattern_name, lookback_days
    )
    UPDATE detected_patterns dp
    SET
        win_rate         = ROUND((s.win_count::numeric / NULLIF(s.occ_count, 0)), 4),
        avg_return       = ROUND(s.avg_ret::numeric, 4),
        sharpe_ratio     = ROUND(s.sharpe::numeric, 4),
        max_drawdown     = ROUND(s.max_dd::numeric, 4),
        occurrence_count = s.occ_count
    FROM stats s
    WHERE dp.symbol = s.symbol
      AND dp.pattern_name = s.pattern_name
      AND dp.lookback_days = s.lookback_days
""")

RESET_DOMINANT_SQL = text("""
    UPDATE detected_patterns
    SET is_dominant = FALSE
    WHERE symbol = :symbol
""")

SET_DOMINANT_SQL = text("""
    WITH best AS (
        SELECT DISTINCT ON (symbol)
            symbol, pattern_name, lookback_days
        FROM detected_patterns
        WHERE symbol = :symbol
          AND sharpe_ratio IS NOT NULL
        ORDER BY symbol, sharpe_ratio DESC
    )
    UPDATE detected_patterns dp
    SET is_dominant = TRUE
    FROM best b
    WHERE dp.symbol = b.symbol
      AND dp.pattern_name = b.pattern_name
      AND dp.lookback_days = b.lookback_days
""")


def aggregate_pattern_stats(conn, symbol: str):
    """Compute aggregate stats and set is_dominant per symbol."""
    conn.execute(AGGREGATE_SQL, {"symbol": symbol})
    conn.execute(RESET_DOMINANT_SQL, {"symbol": symbol})
    conn.execute(SET_DOMINANT_SQL, {"symbol": symbol})


# ═══════════════════════════════════════════════════════════════════════
# STEP 6 — Main Orchestration
# ═══════════════════════════════════════════════════════════════════════
def main():
    global llm_calls
    start_time = time.time()

    log.info("=" * 60)
    log.info("🚀 Historical Backtest — Multi-Agent Pattern Detection")
    log.info("=" * 60)

    # 1. Load all stock_prices from Supabase grouped by symbol
    log.info("📊 Loading stock data from Supabase...")
    query = "SELECT * FROM stock_prices ORDER BY symbol, trading_date"
    all_df = pd.read_sql(query, engine)
    stock_data: dict[str, pd.DataFrame] = {
        sym: grp.reset_index(drop=True) for sym, grp in all_df.groupby("symbol")
    }
    symbols = list(stock_data.keys())

    if DEV_MODE:
        symbols = [s for s in symbols if s in DEV_SYMBOLS]
        if not symbols:
            symbols = list(stock_data.keys())[:3]
        log.info(f"⚡ DEV_MODE: limiting to {symbols}")

    log.info(f"📈 Symbols to scan: {len(symbols)} | Total rows loaded: {len(all_df)}")

    # 2. Build benchmark proxy for regime detection
    log.info("📉 Building market regime benchmark (median-of-all-stocks proxy)...")
    bench_df = build_benchmark_series(stock_data)
    log.info(f"   Benchmark rows: {len(bench_df)}")

    # 3. Process each symbol
    total_signals_found = 0
    total_rows_written = 0

    try:
        with engine.connect() as conn:
            existing_keys = load_existing_keys(conn)
            log.info(f"   Existing detected_patterns rows: {len(existing_keys)}")

            for sym_idx, symbol in enumerate(symbols, 1):
                df_raw = stock_data[symbol]
                if len(df_raw) < 80:
                    log.warning(f"  ⏭  {symbol}: only {len(df_raw)} rows, skipping")
                    continue

                # a. prepare_indicators once per symbol
                df = prepare_indicators(df_raw.copy())
                log.info(
                    f"[{sym_idx}/{len(symbols)}] {symbol}: "
                    f"{len(df_raw)} raw → {len(df)} usable rows"
                )

                # b. scan history
                qualified_signals = scan_symbol_history(symbol, df)
                log.info(f"   ↳ {len(qualified_signals)} qualified signal dates found")
                total_signals_found += len(qualified_signals)

                if not qualified_signals:
                    continue

                # c. For each qualified signal date
                rows_to_insert: list[dict] = []

                for sig_info in qualified_signals:
                    trading_date = sig_info["trading_date"]
                    row_index = sig_info["row_index"]

                    # Get regime
                    regime = get_market_regime(bench_df, trading_date)

                    # Call chief agent (LLM)
                    latest_bar = df.iloc[row_index].to_dict()
                    evaluation = evaluate_signals(
                        symbol, sig_info["raw_signals"], latest_bar, market_regime=regime
                    )
                    llm_calls += 1

                    final_signal = evaluation.get("final_signal", "HOLD")
                    if final_signal == "HOLD":
                        continue  # skip HOLD results

                    conviction = evaluation.get("conviction", 0.0)
                    dominant = evaluation.get("dominant_pattern", "Unknown")
                    reasoning = evaluation.get("reasoning", "")

                    # Calculate forward returns — 3 tiers
                    fwd_results = calculate_forward_returns(df, row_index, final_signal)
                    if not fwd_results:
                        continue

                    for fwd in fwd_results:
                        rows_to_insert.append(
                            {
                                "symbol": symbol,
                                "pattern_name": dominant,
                                "signal_type": final_signal,
                                "confidence": conviction,
                                "detected_at": trading_date,
                                "current_price": sig_info["current_price"],
                                "remarks": reasoning,
                                "is_active": False,
                                "exit_price": fwd["exit_price"],
                                "outcome": fwd["outcome"],
                                "pnl_pct": fwd["pnl_pct"],
                                "lookback_days": fwd["lookback_days"],
                                "agent_source": "HistoricalBacktest",
                                "hold_days": fwd["lookback_days"],
                            }
                        )

                # d. Batch insert for this symbol
                inserted = save_signal_batch(conn, rows_to_insert, existing_keys)
                total_rows_written += inserted
                log.info(f"   ↳ {inserted} rows written to detected_patterns")

                # e. Aggregate stats for this symbol
                if inserted > 0:
                    aggregate_pattern_stats(conn, symbol)
                    log.info(f"   ↳ Aggregation + is_dominant updated")

                conn.commit()

    except Exception as e:
        log.exception(f"❌ Fatal error during backtest: {e}")
        raise
    finally:
        engine.dispose()

    # 4. Final summary
    elapsed = time.time() - start_time
    log.info("")
    log.info("=" * 60)
    log.info("📋 BACKTEST SUMMARY")
    log.info(f"   Symbols scanned     : {len(symbols)}")
    log.info(f"   Qualified signals   : {total_signals_found}")
    log.info(f"   Rows written to DB  : {total_rows_written}")
    log.info(f"   LLM calls made      : {llm_calls}")
    log.info(f"   Elapsed time        : {elapsed:.1f}s")
    log.info("=" * 60)

    # Top 5 dominant patterns
    try:
        with engine.connect() as conn:
            top5 = conn.execute(
                text("""
                    SELECT symbol, pattern_name, lookback_days, sharpe_ratio,
                           win_rate, avg_return, occurrence_count
                    FROM detected_patterns
                    WHERE is_dominant = TRUE
                      AND agent_source = 'HistoricalBacktest'
                    ORDER BY sharpe_ratio DESC NULLS LAST
                    LIMIT 5
                """)
            ).fetchall()
            if top5:
                log.info("")
                log.info("🏆 Top 5 Dominant Patterns:")
                for r in top5:
                    log.info(
                        f"   {r[0]:>15s} │ {r[1]:<25s} │ "
                        f"{r[2]}d │ sharpe={r[3]:.2f} │ "
                        f"WR={r[4]:.1%} │ avg={r[5]:.2f}% │ n={r[6]}"
                    )
    except Exception:
        pass


if __name__ == "__main__":
    main()
