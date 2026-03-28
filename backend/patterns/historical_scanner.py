import os
import sys
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
from tqdm import tqdm

# Allow imports from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents.sub_agents import run_all_agents

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"), poolclass=NullPool)

# Minimum lookback in trading days. 75 ≈ 3.5 months.
# It gives MACD (26d EMA), Bollinger (20d SMA), EMA-50 enough history to stabilize.
LOOKBACK_DAYS = 75

# Columns that sub_agents.py expects to exist in the dataframe slice
REQUIRED_COLS = ["open_price", "high_price", "low_price", "close_price",
                 "volume", "rsi_14", "ema_20", "ema_50"]


def scan_stock(df: pd.DataFrame, symbol: str) -> list[dict]:
    """
    Slide a LOOKBACK_DAYS window across the full historical dataframe for
    one stock and collect all sub-agent signals.

    Parameters
    ----------
    df      : full sorted history for the stock (must contain REQUIRED_COLS)
    symbol  : ticker string

    Returns
    -------
    list of signal dicts ready to insert into detected_patterns
    """
    signals = []

    # We need at least LOOKBACK_DAYS+1 rows to produce any signal
    if len(df) < LOOKBACK_DAYS + 1:
        return signals

    # Iterate from the first fully-formed window onward
    for i in range(LOOKBACK_DAYS, len(df)):
        window = df.iloc[i - LOOKBACK_DAYS: i + 1].reset_index(drop=True)
        current_row = window.iloc[-1]

        try:
            agent_signals = run_all_agents(window)
        except Exception as e:
            # Don't let a single bad candle blow up the whole scan
            continue

        for sig in agent_signals:
            signals.append({
                # Core identifiers
                "symbol": symbol,
                "pattern_name": sig["pattern_name"],
                "signal_type": sig["signal_type"],
                "confidence": sig["confidence"],
                "detected_at": current_row["trading_date"],
                "current_price": current_row["close_price"],
                "remarks": sig.get("remarks", ""),

                # Tracking metadata
                "lookback_days": LOOKBACK_DAYS,
                "agent_source": "SubAgents",
                "is_active": True,

                # Outcome fields – populated later by evaluation scripts
                "exit_price": None,
                "outcome": None,
                "pnl_pct": None,
                "win_rate": None,
                "avg_return": None,
                "sharpe_ratio": None,
                "max_drawdown": None,
                "hold_days": None,
                "occurrence_count": None,
                "is_dominant": None,
            })

    return signals


def run_historical_scan():
    symbols = pd.read_sql(
        "SELECT DISTINCT symbol FROM stock_prices ORDER BY symbol", engine
    )["symbol"].tolist()

    print(f"\n🔍 Scanning {len(symbols)} stocks with a {LOOKBACK_DAYS}-day "
          f"(~{LOOKBACK_DAYS // 21} month) lookback via all sub-agents...\n")

    all_signals = []

    for symbol in tqdm(symbols):
        df = pd.read_sql(
            f"SELECT * FROM stock_prices WHERE symbol = %s ORDER BY trading_date ASC",
            engine,
            params=(symbol,),
        )

        if df.empty or not all(c in df.columns for c in REQUIRED_COLS):
            tqdm.write(f"⚠  Skipping {symbol}: missing required columns.")
            continue

        stock_signals = scan_stock(df, symbol)
        all_signals.extend(stock_signals)

    if all_signals:
        signals_df = pd.DataFrame(all_signals)
        signals_df.to_sql("detected_patterns", engine, if_exists="append", index=False)
        print(f"\n✅ Inserted {len(all_signals)} historical pattern signals into detected_patterns.")
    else:
        print("\n⚠  No signals detected. Check data quality or lookback window size.")


if __name__ == "__main__":
    run_historical_scan()