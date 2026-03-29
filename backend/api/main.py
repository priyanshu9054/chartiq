import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, TypedDict, Annotated, Sequence, Literal
import operator

import openai
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from agents.strategist import StrategistAgent
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    create_engine,
    select,
    func,
    desc
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as SQLUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Use DATABASE_URL from .env as the primary source, allowing fallback to SUPABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DATABASE_URL:
    raise ValueError("Environment variable DATABASE_URL or SUPABASE_URL must be set")

# SQLAlchemy setup with NullPool for Supabase connection limits
engine = create_engine(DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- AGENTIC STATE DEFINITION ---

class ChatState(TypedDict):
    """
    Tracks the state of the agentic workflow.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    symbol_context: str
    retrieved_data: Optional[str]
    raw_data: Optional[dict]
    next_step: Optional[str]

# --- TASK 1: DATABASE MODELS ---

class StockPrice(Base):
    __tablename__ = "stock_prices"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    trading_date = Column(DateTime)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Float)
    rsi_14 = Column(Float)
    ema_20 = Column(Float)
    ema_50 = Column(Float)

class DetectedPattern(Base):
    __tablename__ = "detected_patterns"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    pattern_name = Column(String)
    signal_type = Column(String)  # BUY / SELL / HOLD
    confidence = Column(Float)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    current_price = Column(Float)
    remarks = Column(Text)
    is_active = Column(Boolean, default=True)
    exit_price = Column(Float, nullable=True)
    outcome = Column(String, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    lookback_days = Column(Integer)
    win_rate = Column(Float)
    avg_return = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    hold_days = Column(Integer)
    occurrence_count = Column(Integer)
    is_dominant = Column(Boolean, default=False)
    agent_source = Column(String)

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_context = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(SQLUUID(as_uuid=True), ForeignKey("chat_sessions.id"))
    role = Column(String)  # user / assistant
    content = Column(Text)
    message_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Create tables on startup
Base.metadata.create_all(bind=engine)

# --- LANGGRAPH NODES ---

llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)
strategist_agent = StrategistAgent()

def router_node(state: ChatState):
    """
    Node A: Intent Router.
    Determines if the user query is about the market/stocks or a backtest explanation.
    """
    messages = state["messages"]
    last_message = messages[-1].content
    
    prompt = f"""
    Analyze the user's query and determine the intent.
    Possible intents:
    1. 'market_query': Asking about stocks, market conditions, best picks, or specific tickers.
    2. 'backtest_explanation': Asking about how backtesting or pattern detection works.
    3. 'general_chat': Greetings, small talk, or unrelated questions.
    
    User Query: "{last_message}"
    
    Respond with ONLY the intent name.
    """
    
    response = llm.invoke([SystemMessage(content=prompt)])
    intent = response.content.strip().lower()
    
    if 'market' in intent or 'stock' in intent:
        intent = 'market_query'
    elif 'backtest' in intent:
        intent = 'backtest_explanation'
    else:
        intent = 'general_chat'
        
    return {"next_step": intent}

def strategist_node(state: ChatState):
    """
    Node B: Strategist Agent.
    Dynamically decides which tool to call and executes it.
    """
    messages = state["messages"]
    last_message = messages[-1].content
    
    # 1. Generate Strategy
    strategy = strategist_agent.generate_strategy(last_message)
    print(f"🧠 [Strategist] Thought: {strategy.get('thought')}")
    
    # 2. Execute Tool if needed
    retrieved_data = strategist_agent.execute_strategy(strategy)
    
    return {
        "retrieved_data": retrieved_data,
        "raw_data": {"strategy": strategy}
    }

def reasoning_engine_node(state: ChatState):
    """
    Node C: Reasoning Engine.
    Synthesizes the final response based on intent.
    """
    intent = state.get("next_step", "market_general")
    retrieved_data = state.get("retrieved_data")
    symbol = state.get("symbol_context")
    messages = state["messages"]

    if intent == "market_query" and retrieved_data:
        system_prompt = f"""
        You are a Senior NSE Strategist & Quant Analyst. 
        Use the following retrieved data and chat history to provide a professional synthesis.
        
        RETRIEVED DATA:
        {retrieved_data}
        
        YOUR RESPONSE MUST FOLLOW THIS STRUCTURE:
        [Market Intelligence Summary]
        (A brief overview of the scan results. Do NOT use overly cautious language like "lack of conviction". Instead, summarize the dominant directional bias.)
        
        [Strategic Verdict]
        (Provide specific BUY or SELL recommendations for stocks found in the scan. 
        ALWAYS mention the stock name and its Success Probability (mapped from conviction/win rate).
        Even if the market is weak, identify the best relative opportunities or high-conviction shorts.)
        
        [Evidence & Data]
        (Explain the technical signals or historical win rates that support your verdict)
        
        [Risk Disclosure]
        (Final concluding thoughts and professional cautionary notes)
        """
    elif intent == "backtest_explanation":
        system_prompt = """
        You are a Quant Education Specialist.
        Explain how the NSE Pattern Intel system works:
        - We use 10 specialized sub-agents (RSI, MACD, Candlesticks, etc.)
        - We backtest these patterns over 1 year of historical data.
        - We assign higher weight (Dominant Patterns) to those with the best win rates and Sharpe ratios.
        - The Chief Agent evaluates all active signals today to give a final verdict.
        """
    else:
        system_prompt = """
        You are a helpful and professional NSE Market Assistant. 
        - If the user is greeting you, respond warmly and briefly explain how you can help (analyzing NSE stocks, patterns, and dynamic market scans).
        - If the user asks general market questions, provide concise, professional insights.
        - Encourage the user to ask questions like "What are the best stocks right now?" or "Is RELIANCE a good buy?" to trigger the Strategist Agent.
        """
    
    response = llm.invoke([SystemMessage(content=system_prompt)] + list(messages))
    return {"messages": [AIMessage(content=response.content)]}

# --- DEFINE THE GRAPH ---

builder = StateGraph(ChatState)
builder.add_node("router", router_node)
builder.add_node("strategist", strategist_node)
builder.add_node("reasoner", reasoning_engine_node)

builder.add_edge(START, "router")

def route_after_intent(state: ChatState):
    if state["next_step"] == "market_query":
        return "strategist"
    return "reasoner"

builder.add_conditional_edges(
    "router",
    route_after_intent,
    {
        "strategist": "strategist",
        "reasoner": "reasoner"
    }
)

builder.add_edge("strategist", "reasoner")
builder.add_edge("reasoner", END)

graph = builder.compile()

# --- PYDANTIC SCHEMAS ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[uuid.UUID] = None
    symbol_context: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: uuid.UUID
    raw_data: Optional[dict] = None

# --- FASTAPI APP ---

app = FastAPI(title="NSE Stock Pattern Intelligence API")

# TASK 3: TECHNICAL REQUIREMENTS - CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- TASK 2: API ENDPOINTS ---

@app.get("/api/stocks")
def get_stocks(db: Session = Depends(get_db)):
    """
    Retrieve all unique symbols.
    For each symbol, include its 'is_dominant' pattern stats (win_rate, pattern_name)
    AND any 'is_active' signal (falling back to most recent if none from today).
    """
    # Get all unique symbols from StockPrice
    symbols = db.query(StockPrice.symbol).distinct().all()
    symbols = [s[0] for s in symbols]
    
    result = []
    
    for symbol in symbols:
        # Get dominant pattern
        dominant = db.query(DetectedPattern).filter(
            DetectedPattern.symbol == symbol,
            DetectedPattern.is_dominant == True
        ).first()
        
        # Get MOST RECENT signal (even if inactive/historical)
        active_signal = db.query(DetectedPattern).filter(
            DetectedPattern.symbol == symbol
        ).order_by(desc(DetectedPattern.detected_at)).first()
        
        result.append({
            "symbol": symbol,
            "dominant_pattern": {
                "pattern_name": dominant.pattern_name if dominant else None,
                "win_rate": (dominant.win_rate * 100) if dominant and dominant.win_rate else 0
            },
            "active_signal": {
                "pattern_name": active_signal.pattern_name if active_signal else None,
                "signal_type": active_signal.signal_type if active_signal else None,
                "confidence": (active_signal.confidence * 100) if active_signal and active_signal.confidence else 0,
                "detected_at": active_signal.detected_at.isoformat() if active_signal.detected_at else None
            } if active_signal else None
        })
        
    return result

@app.get("/api/signals/{symbol}")
def get_signals_by_symbol(symbol: str, db: Session = Depends(get_db)):
    """
    Return the active signal for this stock (if any).
    Return a list of all historical patterns (is_active=False) for this stock,
    sorted by win_rate, for the detail view.
    """
    active_signal = db.query(DetectedPattern).filter(
        DetectedPattern.symbol == symbol,
        DetectedPattern.is_active == True
    ).order_by(desc(DetectedPattern.detected_at)).first()
    
    historical_patterns = db.query(DetectedPattern).filter(
        DetectedPattern.symbol == symbol,
        DetectedPattern.is_active == False
    ).order_by(desc(DetectedPattern.win_rate)).all()
    
    return {
        "symbol": symbol,
        "active_signal": active_signal,
        "historical_patterns": historical_patterns
    }

@app.get("/api/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)):
    """
    Group all patterns by pattern_name.
    Calculate average win_rate and sharpe_ratio across the entire 49-stock universe.
    """
    # Using group_by and func.avg
    stats = db.query(
        DetectedPattern.pattern_name,
        func.avg(DetectedPattern.win_rate).label("avg_win_rate"),
        func.avg(DetectedPattern.sharpe_ratio).label("avg_sharpe_ratio"),
        func.count(DetectedPattern.id).label("count")
    ).group_by(DetectedPattern.pattern_name).all()
    
    return [
        {
            "pattern_name": s.pattern_name,
            "avg_win_rate": round(s.avg_win_rate, 4) if s.avg_win_rate else 0,
            "avg_sharpe_ratio": round(s.avg_sharpe_ratio, 4) if s.avg_sharpe_ratio else 0,
            "occurrence_count": s.count
        } for s in stats
    ]

@app.post("/api/chat", response_model=ChatResponse)
def post_chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Refactored Chat implementation using LangGraph Agentic Workflow.
    """
    # 1. Session Management
    session_id = request.session_id
    if not session_id:
        new_session = ChatSession(symbol_context=request.symbol_context)
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        session_id = new_session.id
    
    # 2. Memory: Retrieve the last 5 messages from ChatMessage for history.
    history_records = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(desc(ChatMessage.created_at)).limit(5).all()
    history_records = history_records[::-1] # Chronological order
    
    # Convert DB records to LangChain messages
    langchain_history = []
    for rec in history_records:
        if rec.role == "user":
            langchain_history.append(HumanMessage(content=rec.content))
        elif rec.role == "assistant":
            langchain_history.append(AIMessage(content=rec.content))
            
    # Add the current user message
    current_message = HumanMessage(content=request.message)
    
    # 3. Execution: Run the LangGraph
    initial_state = {
        "messages": langchain_history + [current_message],
        "symbol_context": request.symbol_context,
        "retrieved_data": None,
        "raw_data": None,
        "next_step": None
    }
    
    try:
        final_state = graph.invoke(initial_state)
        ai_response_message = final_state["messages"][-1]
        ai_response_text = ai_response_message.content
        retrieved_data = final_state.get("retrieved_data")
        raw_data = final_state.get("raw_data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Workflow Error: {str(e)}")
        
    # 4. Persistence: Save both User and Assistant messages to ChatMessage table.
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.message
    )
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=ai_response_text,
        message_metadata={"retrieved_data": retrieved_data} # Store what was used for reasoning
    )
    db.add(user_msg)
    db.add(assistant_msg)
    db.commit()
    
    # 5. Return { "response": text, "session_id": UUID, "raw_data": dict }.
    return ChatResponse(response=ai_response_text, session_id=session_id, raw_data=raw_data)

# Basic Error Handling for DB connection on startup
@app.on_event("startup")
def startup_db_check():
    try:
        with engine.connect() as connection:
            pass
    except Exception as e:
        print(f"CRITICAL: Database connection failed! Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
