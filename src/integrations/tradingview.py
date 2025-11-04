"""
TradingView Integration

Provides:
1. Real-time data fetching from TradingView
2. Webhook receiver for TradingView alerts
3. Chart data conversion to pandas DataFrame
"""

import requests
import pandas as pd
import json
from typing import Optional, Literal
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
import asyncio
from dataclasses import dataclass


@dataclass
class TradingViewAlert:
    """Represents a TradingView alert webhook"""
    ticker: str
    interval: str
    time: str
    signal: Literal["buy", "sell", "neutral"]
    price: float
    indicator: Optional[str] = None
    metadata: Optional[dict] = None


class TradingViewClient:
    """
    Client for fetching data from TradingView

    Note: TradingView doesn't have an official public API.
    This implementation uses alternative methods:
    1. Yahoo Finance as a proxy (free, reliable)
    2. TradingView webhooks for real-time alerts
    3. WebSocket for tick data (requires paid service like Polygon/Alpaca)
    """

    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
        self.alert_callbacks = []

    def get_historical_data(
        self,
        ticker: str,
        interval: Literal["1m", "5m", "15m", "1h", "1d"] = "1h",
        period: str = "7d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data

        Args:
            ticker: Stock symbol (e.g., 'AAPL', 'BTCUSD')
            interval: Candle interval
            period: Lookback period (e.g., '1d', '5d', '1mo', '1y')
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        # Convert interval to Yahoo Finance format
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "1d": "1d"
        }
        yf_interval = interval_map.get(interval, "1h")

        # Build URL
        url = f"{self.base_url}/{ticker}"
        params = {
            "interval": yf_interval,
            "includePrePost": "false"
        }

        if start_date and end_date:
            # Convert dates to Unix timestamps
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
            end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
            params["period1"] = start_ts
            params["period2"] = end_ts
        else:
            params["range"] = period

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Extract OHLCV data
            chart_data = data["chart"]["result"][0]
            timestamps = chart_data["timestamp"]
            quotes = chart_data["indicators"]["quote"][0]

            df = pd.DataFrame({
                "timestamp": pd.to_datetime(timestamps, unit="s"),
                "open": quotes["open"],
                "high": quotes["high"],
                "low": quotes["low"],
                "close": quotes["close"],
                "volume": quotes["volume"]
            })

            # Remove rows with NaN values
            df = df.dropna()

            return df

        except Exception as e:
            raise Exception(f"Error fetching TradingView data for {ticker}: {str(e)}")

    def get_realtime_price(self, ticker: str) -> dict:
        """
        Get current real-time price

        Returns:
            Dictionary with current price, change, volume
        """
        try:
            # Fetch 1-minute data for most recent price
            df = self.get_historical_data(ticker, interval="1m", period="1d")

            if df.empty:
                raise Exception(f"No data available for {ticker}")

            latest = df.iloc[-1]
            previous = df.iloc[-2] if len(df) > 1 else latest

            return {
                "ticker": ticker,
                "price": float(latest["close"]),
                "open": float(latest["open"]),
                "high": float(latest["high"]),
                "low": float(latest["low"]),
                "volume": float(latest["volume"]),
                "change": float(latest["close"] - previous["close"]),
                "change_percent": float((latest["close"] - previous["close"]) / previous["close"] * 100),
                "timestamp": latest["timestamp"].isoformat()
            }

        except Exception as e:
            raise Exception(f"Error fetching real-time price for {ticker}: {str(e)}")

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate common technical indicators used in TradingView

        Adds columns:
        - SMA (20, 50, 200)
        - EMA (12, 26)
        - RSI (14)
        - MACD
        - Bollinger Bands
        - ATR
        """
        # Simple Moving Averages
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()

        # Exponential Moving Averages
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()

        # MACD
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)

        # ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=14).mean()

        return df

    def register_alert_callback(self, callback):
        """Register a callback function to handle TradingView alerts"""
        self.alert_callbacks.append(callback)

    async def handle_alert(self, alert: TradingViewAlert):
        """Process incoming TradingView alert"""
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                print(f"Error in alert callback: {str(e)}")


# FastAPI router for TradingView webhooks
tradingview_router = APIRouter(prefix="/tradingview", tags=["tradingview"])

# Global client instance
tv_client = TradingViewClient()


@tradingview_router.post("/webhook")
async def tradingview_webhook(request: Request):
    """
    Endpoint to receive TradingView alerts via webhook

    TradingView Alert Message Format (JSON):
    {
        "ticker": "{{ticker}}",
        "interval": "{{interval}}",
        "time": "{{time}}",
        "signal": "buy",
        "price": {{close}},
        "indicator": "ICT Order Block",
        "metadata": {
            "high": {{high}},
            "low": {{low}},
            "volume": {{volume}}
        }
    }

    Setup in TradingView:
    1. Create alert
    2. Set webhook URL: http://your-server:8000/tradingview/webhook
    3. Set alert message to JSON above
    """
    try:
        body = await request.json()

        # Validate required fields
        required_fields = ["ticker", "signal", "price"]
        for field in required_fields:
            if field not in body:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )

        # Create alert object
        alert = TradingViewAlert(
            ticker=body["ticker"],
            interval=body.get("interval", "unknown"),
            time=body.get("time", datetime.now().isoformat()),
            signal=body["signal"],
            price=float(body["price"]),
            indicator=body.get("indicator"),
            metadata=body.get("metadata", {})
        )

        # Process alert
        await tv_client.handle_alert(alert)

        return {
            "status": "success",
            "message": f"Alert received for {alert.ticker}",
            "alert": {
                "ticker": alert.ticker,
                "signal": alert.signal,
                "price": alert.price
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing alert: {str(e)}")


@tradingview_router.get("/price/{ticker}")
async def get_current_price(ticker: str):
    """Get current price for a ticker"""
    try:
        price_data = tv_client.get_realtime_price(ticker)
        return price_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@tradingview_router.get("/chart/{ticker}")
async def get_chart_data(
    ticker: str,
    interval: str = "1h",
    period: str = "7d"
):
    """Get historical chart data"""
    try:
        df = tv_client.get_historical_data(ticker, interval=interval, period=period)
        return {
            "ticker": ticker,
            "interval": interval,
            "data": df.to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Example callback function
async def example_alert_handler(alert: TradingViewAlert):
    """
    Example callback that processes TradingView alerts

    You can customize this to:
    - Execute trades automatically
    - Send notifications
    - Log alerts to database
    - Run additional analysis
    """
    print(f"[ALERT] {alert.ticker} - {alert.signal} @ ${alert.price}")
    print(f"  Time: {alert.time}")
    print(f"  Indicator: {alert.indicator}")

    # Example: Execute trade based on alert
    # if alert.signal == "buy":
    #     execute_buy_order(alert.ticker, alert.price)
    # elif alert.signal == "sell":
    #     execute_sell_order(alert.ticker, alert.price)


# Register the example callback
tv_client.register_alert_callback(example_alert_handler)
