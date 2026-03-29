import json
from .llm_config import get_llm_client
from .tools import market_scanner_tool, stock_deep_dive_tool

class StrategistAgent:
    def __init__(self):
        self.client = get_llm_client()
        self.tools = {
            "market_scanner_tool": market_scanner_tool,
            "stock_deep_dive_tool": stock_deep_dive_tool
        }

    def generate_strategy(self, query: str, history: list = None) -> dict:
        """
        Given a query, determine the tool calling strategy.
        """
        system_prompt = """
        You are the 'Strategist Agent' for a Nifty 50 Quant Platform.
        Your job is to decompose a user's question into a tool-calling strategy.
        
        AVAILABLE TOOLS:
        1. market_scanner_tool(): Scans all 50 stocks for BUY signals. Use this for "best stock", "what to buy", "market scan".
        2. stock_deep_dive_tool(symbol): Gets technicals and historical performance for ONE stock. Use for specific tickers like "Is RELIANCE good?", "Tell me about TCS".
        
        RESPONSE FORMAT:
        You must respond with a JSON object:
        {
            "thought": "Your reasoning about why you chose this tool",
            "tool_call": "market_scanner_tool" | "stock_deep_dive_tool" | "none",
            "tool_input": "symbol_name" (if applicable)
        }
        
        If no tool is needed (e.g., just a greeting), set tool_call to "none".
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"❌ Strategist Error: {e}")
            return {"thought": "Error in strategy", "tool_call": "none", "tool_input": None}

    def execute_strategy(self, strategy: dict) -> str:
        """
        Execute the tool and return a summary string.
        """
        tool_name = strategy.get("tool_call")
        tool_input = strategy.get("tool_input")
        
        if tool_name == "market_scanner_tool":
            data = market_scanner_tool()
            if not data:
                return "The market scanner currently shows no strong directional edge, but here are the stocks with the highest relative momentum/fluctuation for your radar."
            
            output = "Market Scan Analysis (High Probability Directions):\n"
            for item in data:
                sig_type = item.get('signal', 'BUY')
                output += f"- {item['symbol']}: {sig_type} (Success Prob: {item['confidence']*100:.1f}%), Price: {item['price']}, Pattern: {item['pattern']}\n"
                output += f"  Reasoning: {item['reasoning']}\n"
            return output
            
        elif tool_name == "stock_deep_dive_tool" and tool_input:
            data = stock_deep_dive_tool(tool_input)
            if "error" in data:
                return data["error"]
                
            eval = data["evaluation"]
            hist = data["historical_dominant_pattern"]
            output = f"Deep Dive for {tool_input}:\n"
            output += f"- Signal: {eval['final_signal']} (Conviction: {eval['conviction']*100:.1f}%)\n"
            output += f"- Pattern: {eval['dominant_pattern']}\n"
            output += f"- Reasoning: {eval['reasoning']}\n"
            output += f"- Historical Win Rate for this pattern: {hist['win_rate']*100:.2f}%\n"
            return output
            
        return "No specific data retrieved."
