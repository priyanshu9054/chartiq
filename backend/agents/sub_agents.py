import pandas as pd
import numpy as np


def _col(df, *names):
    """Return first column name that exists in df, or raise."""
    for n in names:
        if n in df.columns:
            return n
    raise KeyError(f"None of {names} found in DataFrame columns")


def get_signal_metadata(df, signal_type, pattern_name, base_confidence, remarks):
    """
    Helper to apply volume and trend boosts to confidence.
    Handles both pre-calc columns (ema20/ema50) and DB columns (ema_20/ema_50).
    """
    last_row = df.iloc[-1]
    vol_20_avg = df['volume'].tail(20).mean()

    confidence = base_confidence

    # Boost +0.1 if volume confirms (above 20-day avg)
    if last_row['volume'] > vol_20_avg:
        confidence += 0.1

    # Boost +0.1 if trend aligns (ema20 vs ema50 direction)
    ema20_col = _col(df, 'ema20', 'ema_20')
    ema50_col = _col(df, 'ema50', 'ema_50')
    is_bullish_trend = last_row[ema20_col] > last_row[ema50_col]
    if (signal_type == "BUY" and is_bullish_trend) or (signal_type == "SELL" and not is_bullish_trend):
        confidence += 0.1

    return {
        "pattern_name": pattern_name,
        "signal_type": signal_type,
        "confidence": min(1.0, round(confidence, 2)),
        "remarks": remarks
    }

# 1. RSI Agent
def rsi_agent(df):
    # Use pre-calc 'rsi' if available (from prepare_indicators), else fall back to DB column 'rsi_14'
    rsi_col = _col(df, 'rsi', 'rsi_14')
    last_rsi = df[rsi_col].iloc[-1]
    if pd.isna(last_rsi):
        return None
    if last_rsi < 30:
        return get_signal_metadata(df, "BUY", "RSI Oversold", 0.7, f"RSI is at {last_rsi:.2f} (Oversold)")
    elif last_rsi > 70:
        return get_signal_metadata(df, "SELL", "RSI Overbought", 0.7, f"RSI is at {last_rsi:.2f} (Overbought)")
    return None

# 2. EMA Cross Agent
def ema_cross_agent(df):
    if len(df) < 2: return None

    ema20_col = _col(df, 'ema20', 'ema_20')
    ema50_col = _col(df, 'ema50', 'ema_50')

    prev_ema20 = df[ema20_col].iloc[-2]
    prev_ema50 = df[ema50_col].iloc[-2]
    curr_ema20 = df[ema20_col].iloc[-1]
    curr_ema50 = df[ema50_col].iloc[-1]
    if any(pd.isna(v) for v in [prev_ema20, prev_ema50, curr_ema20, curr_ema50]):
        return None

    # Golden Cross: 20 crosses above 50
    if prev_ema20 <= prev_ema50 and curr_ema20 > curr_ema50:
        return get_signal_metadata(df, "BUY", "EMA Golden Cross", 0.8, "EMA 20 crossed above EMA 50")

    # Death Cross: 20 crosses below 50
    if prev_ema20 >= prev_ema50 and curr_ema20 < curr_ema50:
        return get_signal_metadata(df, "SELL", "EMA Death Cross", 0.8, "EMA 20 crossed below EMA 50")

    return None

# 3. MACD Agent
def macd_agent(df):
    # Use pre-calc columns if available (from prepare_indicators), else recalculate inline
    if 'macd' in df.columns and 'macd_signal' in df.columns:
        macd = df['macd']
        signal = df['macd_signal']
    else:
        ema12 = df['close_price'].ewm(span=12, adjust=False).mean()
        ema26 = df['close_price'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()

    if len(macd) < 2: return None

    prev_macd = macd.iloc[-2]
    prev_signal = signal.iloc[-2]
    curr_macd = macd.iloc[-1]
    curr_signal = signal.iloc[-1]

    if any(pd.isna(v) for v in [prev_macd, prev_signal, curr_macd, curr_signal]):
        return None

    if prev_macd <= prev_signal and curr_macd > curr_signal:
        return get_signal_metadata(df, "BUY", "MACD Bullish Cross", 0.75, "MACD line crossed above Signal line")

    if prev_macd >= prev_signal and curr_macd < curr_signal:
        return get_signal_metadata(df, "SELL", "MACD Bearish Cross", 0.75, "MACD line crossed below Signal line")

    return None

# 4. Bollinger Bands Agent
def bollinger_agent(df):
    # Use pre-calc columns if available (from prepare_indicators), else recalculate inline
    if 'bb_upper' in df.columns and 'bb_lower' in df.columns:
        last_close = df['close_price'].iloc[-1]
        last_lower = df['bb_lower'].iloc[-1]
        last_upper = df['bb_upper'].iloc[-1]
    else:
        sma20 = df['close_price'].rolling(window=20).mean()
        std20 = df['close_price'].rolling(window=20).std()
        last_close = df['close_price'].iloc[-1]
        last_lower = (sma20 - 2 * std20).iloc[-1]
        last_upper = (sma20 + 2 * std20).iloc[-1]

    if any(pd.isna(v) for v in [last_close, last_lower, last_upper]):
        return None

    if last_close <= last_lower:
        return get_signal_metadata(df, "BUY", "Bollinger Lower Touch", 0.7, "Price touched/broke lower Bollinger Band")

    if last_close >= last_upper:
        return get_signal_metadata(df, "SELL", "Bollinger Upper Touch", 0.7, "Price touched/broke upper Bollinger Band")

    return None

# 5. Volume Spike Agent
def volume_spike_agent(df):
    if len(df) < 20: return None
    
    last_row = df.iloc[-1]
    vol_20_avg = df['volume'].tail(20).mean()
    
    # Volume > 2x 20-day avg volume on an up day = BUY confirmation
    if last_row['volume'] > (2 * vol_20_avg) and last_row['close_price'] > last_row['open_price']:
        return get_signal_metadata(df, "BUY", "Volume Spike", 0.6, "Significant volume spike on a bullish day")
    
    return None

# 6. Hammer Agent
def hammer_agent(df):
    # Hammer: small body at top, lower wick >= 2x body, appears after downtrend
    if len(df) < 2: return None

    last_row = df.iloc[-1]
    body = abs(last_row['close_price'] - last_row['open_price'])
    lower_wick = min(last_row['open_price'], last_row['close_price']) - last_row['low_price']
    upper_wick = last_row['high_price'] - max(last_row['open_price'], last_row['close_price'])

    # Trend context: ema20 sloping down
    ema20_col = _col(df, 'ema20', 'ema_20')
    ema_curr, ema_prev = df[ema20_col].iloc[-1], df[ema20_col].iloc[-2]
    if pd.isna(ema_curr) or pd.isna(ema_prev): return None
    trend_down = ema_curr < ema_prev

    if body > 0 and lower_wick >= 2 * body and upper_wick < body and trend_down:
        return get_signal_metadata(df, "BUY", "Hammer", 0.7, "Hammer candle detected in a downtrend")

    return None

# 7. Shooting Star Agent
def shooting_star_agent(df):
    # Shooting Star: Inverse of hammer. Upper wick >= 2x body, appears after uptrend
    if len(df) < 2: return None

    last_row = df.iloc[-1]
    body = abs(last_row['close_price'] - last_row['open_price'])
    lower_wick = min(last_row['open_price'], last_row['close_price']) - last_row['low_price']
    upper_wick = last_row['high_price'] - max(last_row['open_price'], last_row['close_price'])

    # Trend context: ema20 sloping up
    ema20_col = _col(df, 'ema20', 'ema_20')
    ema_curr, ema_prev = df[ema20_col].iloc[-1], df[ema20_col].iloc[-2]
    if pd.isna(ema_curr) or pd.isna(ema_prev): return None
    trend_up = ema_curr > ema_prev

    if body > 0 and upper_wick >= 2 * body and lower_wick < body and trend_up:
        return get_signal_metadata(df, "SELL", "Shooting Star", 0.7, "Shooting Star candle detected in an uptrend")

    return None

# 8. Engulfing Agent
def engulfing_agent(df):
    if len(df) < 2: return None
    
    prev_row = df.iloc[-2]
    curr_row = df.iloc[-1]
    
    vol_20_avg = df['volume'].tail(20).mean()
    vol_confirm = curr_row['volume'] > vol_20_avg
    
    # Bullish Engulfing
    if (prev_row['close_price'] < prev_row['open_price'] and 
        curr_row['close_price'] > curr_row['open_price'] and
        curr_row['open_price'] <= prev_row['close_price'] and
        curr_row['close_price'] >= prev_row['open_price'] and vol_confirm):
        return get_signal_metadata(df, "BUY", "Bullish Engulfing", 0.8, "Current candle fully engulfs previous bearish candle")
    
    # Bearish Engulfing
    if (prev_row['close_price'] > prev_row['open_price'] and 
        curr_row['close_price'] < curr_row['open_price'] and
        curr_row['open_price'] >= prev_row['close_price'] and
        curr_row['close_price'] <= prev_row['open_price'] and vol_confirm):
        return get_signal_metadata(df, "SELL", "Bearish Engulfing", 0.8, "Current candle fully engulfs previous bullish candle")
    
    return None

# 9. Morning Star Agent
def morning_star_agent(df):
    # Three candles: big red, small doji/body, big green
    if len(df) < 3: return None
    
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    
    # C1: Big red
    is_c1_bearish = c1['close_price'] < c1['open_price']
    
    # C2: Small body (gap down preferred but not strictly required here for simplification)
    c2_body = abs(c2['close_price'] - c2['open_price'])
    c2_range = c2['high_price'] - c2['low_price']
    is_c2_small = c2_body < (0.3 * abs(c1['open_price'] - c1['close_price']))
    
    # C3: Big green
    is_c3_bullish = c3['close_price'] > c3['open_price']
    c3_closes_well_into_c1 = c3['close_price'] > (c1['open_price'] + c1['close_price']) / 2
    
    if is_c1_bearish and is_c2_small and is_c3_bullish and c3_closes_well_into_c1:
        return get_signal_metadata(df, "BUY", "Morning Star", 0.85, "Bullish three-candle reversal pattern")
    
    return None

# 10. Doji Agent
def doji_agent(df):
    # Body < 5% of total range
    last_row = df.iloc[-1]
    body = abs(last_row['close_price'] - last_row['open_price'])
    total_range = last_row['high_price'] - last_row['low_price']

    if total_range == 0: return None

    ema20_col = _col(df, 'ema20', 'ema_20')
    if pd.isna(last_row[ema20_col]): return None

    if body < (0.05 * total_range):
        # Above ema20 = potential SELL, below = potential BUY
        if last_row['close_price'] > last_row[ema20_col]:
            return get_signal_metadata(df, "SELL", "Doji (Top)", 0.4, "Doji candle above EMA 20, potential reversal")
        else:
            return get_signal_metadata(df, "BUY", "Doji (Bottom)", 0.4, "Doji candle below EMA 20, potential reversal")

    return None

def run_all_agents(df):
    agents = [
        rsi_agent, ema_cross_agent, macd_agent, bollinger_agent, 
        volume_spike_agent, hammer_agent, shooting_star_agent, 
        engulfing_agent, morning_star_agent, doji_agent
    ]
    signals = []
    for agent in agents:
        res = agent(df)
        if res:
            signals.append(res)
    return signals
