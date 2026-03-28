import json
from .llm_config import get_llm_client

SYSTEM_PROMPT = """
You are a senior quant analyst at a high-frequency trading desk on the National Stock Exchange (NSE). 
Your task is to evaluate multiple technical signals for a given stock and provide a final trading decision.

You will receive:
1. Stock symbol
2. Current price and key indicator values
3. A list of signals detected by various sub-agents (RSI, EMA, MACD, Candlestick patterns, etc.)

Your goal is to synthesize these signals, weighing their confidence and remarks, to determine if the stock is a BUY, SELL, or HOLD.
Be conservative. If signals are conflicting or low confidence, default to HOLD.

Response MUST be in JSON format only with the following keys:
{
  "final_signal": "BUY" | "SELL" | "HOLD",
  "conviction": float (0.0 - 1.0),
  "dominant_pattern": str,
  "reasoning": str (2-3 sentences max)
}
"""

def evaluate_signals(symbol: str, signals: list[dict], latest_bar: dict, market_regime: str = "BULLISH") -> dict:
    client = get_llm_client()
    
    # Prepare the context for the LLM
    signals_str = "\n".join([
        f"- {s['pattern_name']} ({s['signal_type']}): Confidence {s['confidence']}, Remarks: {s['remarks']}"
        for s in signals
    ])
    
    # Support both pre-calc column names (ema20/ema50/rsi) and DB column names (ema_20/ema_50/rsi_14)
    ema20 = latest_bar.get('ema20', latest_bar.get('ema_20', 0))
    ema50 = latest_bar.get('ema50', latest_bar.get('ema_50', 0))
    rsi_val = latest_bar.get('rsi', latest_bar.get('rsi_14', 0))
    trend = "BULLISH" if ema20 > ema50 else "BEARISH"
    
    # Regime-aware instructions
    regime_instruction = ""
    if market_regime == "BEARISH":
        regime_instruction = "\n⚠️ MARKET REGIME: BEARISH. Be extra conservative on BUY signals. Require conviction > 0.75 for any BUY recommendation.\n"
    
    user_prompt = f"""
    Stock: {symbol}
    Current Price: {latest_bar['close_price']}
    RSI (14): {rsi_val:.2f}
    EMA 20: {ema20:.2f}
    EMA 50: {ema50:.2f}
    Trend: {trend}
    Market Regime: {market_regime}
    {regime_instruction}
    Detected Signals:
    {signals_str}
    
    Evaluate and provide the final signal.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"❌ Error in Chief Agent evaluation for {symbol}: {e}")
        return {
            "final_signal": "HOLD",
            "conviction": 0.0,
            "dominant_pattern": "Error/None",
            "reasoning": "Failed to evaluate signals due to a system error."
        }
