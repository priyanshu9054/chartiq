import os
import time
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(DB_URL, poolclass=NullPool)

# THE NIFTY 50 UNIVERSE
SYMBOLS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
    "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LTIM.NS",
    "LT.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS",
    "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS",
    "TECHM.NS", "TITAN.NS", "UPL.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

def fetch_and_insert(symbol):
    try:
        # 1. Download 1 year of daily data
        df = yf.download(symbol, period="1y", interval="1d", progress=False)
        if df.empty: return False

        # 2. Fix yfinance 1.2.0 MultiIndex issue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 3. Calculate Technical Indicators
        df['rsi_14'] = ta.rsi(df['Close'], length=14)
        df['ema_20'] = ta.ema(df['Close'], length=20)
        df['ema_50'] = ta.ema(df['Close'], length=50)

        # 4. Clean and Format for SQL
        df = df.reset_index().rename(columns={
            'Date': 'trading_date', 'Open': 'open_price', 'High': 'high_price',
            'Low': 'low_price', 'Close': 'close_price', 'Volume': 'volume'
        })
        df['symbol'] = symbol
        final_df = df[['symbol', 'trading_date', 'open_price', 'high_price', 
                       'low_price', 'close_price', 'volume', 'rsi_14', 'ema_20', 'ema_50']].dropna()

        # 5. Insert into Supabase with duplicate skipping
        try:
            final_df.to_sql('stock_prices', engine, if_exists='append', index=False, method='multi')
            return True
        except IntegrityError:
            # This handles the case where data already exists
            return "skipped"

    except Exception as e:
        print(f"❌ Error with {symbol}: {e}")
        return False

if __name__ == "__main__":
    print(f"🚀 Re-creating Data for {len(SYMBOLS)} stocks...")
    
    for sym in tqdm(SYMBOLS):
        result = fetch_and_insert(sym)
        if result == "skipped":
            pass # Silent skip
        time.sleep(1) # Be nice to Yahoo Finance

    print(f"\n✅ Finished! Your Nifty 50 Universe is ready in Supabase.")