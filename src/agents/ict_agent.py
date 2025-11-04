"""
ICT Trading Agent

Uses Inner Circle Trader methodology with TradingView data
to generate trading signals based on institutional order flow
"""

import json
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from typing_extensions import Literal

from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress
from src.strategies.ict_strategy import ICTStrategy
from src.integrations.tradingview import TradingViewClient


class ICTSignal(BaseModel):
    """ICT trading signal output"""
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(description="Confidence level 0-100")
    entry_price: float = Field(description="Recommended entry price")
    stop_loss: float = Field(description="Stop loss level")
    take_profit: float = Field(description="Take profit level")
    reasoning: dict = Field(description="Detailed reasoning for the signal")


def ict_trading_agent(state: AgentState):
    """
    ICT Trading Agent

    Analyzes price action using ICT concepts:
    - Order blocks
    - Fair value gaps
    - Liquidity pools
    - Market structure
    - Kill zones

    Uses TradingView for real-time data
    """
    data = state["data"]
    tickers = data.get("tickers", [])
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    # Initialize clients
    tv_client = TradingViewClient()
    ict_strategy = ICTStrategy()

    # Analyze each ticker
    signals = {}

    for ticker in tickers:
        progress.update_status("ict_agent", ticker, "Fetching TradingView data")

        try:
            # Fetch data from TradingView (via Yahoo Finance)
            df = tv_client.get_historical_data(
                ticker=ticker,
                interval="1h",  # 1-hour candles for ICT analysis
                start_date=start_date,
                end_date=end_date
            )

            if df.empty:
                progress.update_status("ict_agent", ticker, "No data available")
                signals[ticker] = {
                    "signal": "neutral",
                    "confidence": 0,
                    "reasoning": "No data available from TradingView"
                }
                continue

            # Add technical indicators
            df = tv_client.calculate_indicators(df)

            progress.update_status("ict_agent", ticker, "Analyzing ICT concepts")

            # Run ICT analysis
            analysis = ict_strategy.analyze(df)

            # Extract current price and ATR for stop loss calculation
            current_price = float(df['close'].iloc[-1])
            atr = float(df['atr'].iloc[-1]) if 'atr' in df.columns else current_price * 0.02

            # Build signal
            signal = {
                "signal": analysis["signal"],
                "confidence": analysis["confidence"],
                "entry_price": analysis.get("entry_price", current_price),
                "stop_loss": analysis.get("stop_loss", current_price * 0.98),
                "take_profit": analysis.get("take_profit", current_price * 1.04),
                "reasoning": {
                    "market_structure": analysis["market_structure"],
                    "in_kill_zone": analysis["in_kill_zone"],
                    "order_blocks": analysis["order_blocks_count"],
                    "fair_value_gaps": analysis["fvg_count"],
                    "liquidity_pools": analysis["liquidity_pools_count"],
                    "reasons": analysis["reasons"],
                    "current_price": current_price,
                    "atr": atr
                }
            }

            signals[ticker] = signal
            progress.update_status("ict_agent", ticker, f"Signal: {signal['signal']}")

        except Exception as e:
            progress.update_status("ict_agent", ticker, f"Error: {str(e)}")
            signals[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": f"Error analyzing ticker: {str(e)}"
            }

    # Create message
    message = HumanMessage(
        content=json.dumps(signals),
        name="ict_agent"
    )

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(signals, "ICT Trading Agent")

    # Add signals to state
    state["data"]["analyst_signals"]["ict_agent"] = signals

    progress.update_status("ict_agent", None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": data
    }
