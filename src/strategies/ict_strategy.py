"""
ICT (Inner Circle Trader) Strategy Implementation

Key Concepts:
- Order Blocks (OB): Institutional buying/selling zones
- Fair Value Gaps (FVG): Price imbalances that tend to get filled
- Liquidity Pools: Areas where stop losses cluster (swept by institutions)
- Market Structure: BOS (Break of Structure), CHoCH (Change of Character)
- Premium/Discount Zones: Price trading above/below equilibrium
- Optimal Trade Entry (OTE): Fibonacci 0.62-0.79 retracement zones
- Kill Zones: London (02:00-05:00 EST), New York (08:00-11:00 EST)
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
from typing import Literal, Optional
from dataclasses import dataclass


@dataclass
class OrderBlock:
    """Represents an institutional order block"""
    start_idx: int
    end_idx: int
    high: float
    low: float
    type: Literal["bullish", "bearish"]
    strength: float  # Based on volume and displacement
    touched: bool = False


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap (imbalance)"""
    start_idx: int
    end_idx: int
    top: float
    bottom: float
    type: Literal["bullish", "bearish"]
    filled: bool = False
    fill_percentage: float = 0.0


@dataclass
class LiquidityPool:
    """Represents a liquidity pool (stop hunt zone)"""
    price_level: float
    type: Literal["buy_side", "sell_side"]  # Above resistance or below support
    strength: float  # Number of times tested
    swept: bool = False


@dataclass
class MarketStructure:
    """Represents current market structure"""
    trend: Literal["bullish", "bearish", "ranging"]
    last_higher_high: Optional[float] = None
    last_higher_low: Optional[float] = None
    last_lower_high: Optional[float] = None
    last_lower_low: Optional[float] = None
    structure_break: bool = False  # BOS or CHoCH detected


class ICTStrategy:
    """
    ICT Trading Strategy Implementation

    This strategy identifies institutional order flow patterns and trades
    with smart money, not against it.
    """

    def __init__(
        self,
        lookback_period: int = 100,
        fvg_threshold: float = 0.001,  # Minimum gap size (0.1%)
        order_block_strength_threshold: float = 0.5,
    ):
        self.lookback_period = lookback_period
        self.fvg_threshold = fvg_threshold
        self.order_block_strength_threshold = order_block_strength_threshold

        # State tracking
        self.order_blocks: list[OrderBlock] = []
        self.fair_value_gaps: list[FairValueGap] = []
        self.liquidity_pools: list[LiquidityPool] = []
        self.market_structure = MarketStructure(trend="ranging")

    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Main analysis function - identifies all ICT concepts

        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)

        Returns:
            Dictionary with ICT analysis and trading signals
        """
        if len(df) < self.lookback_period:
            return {
                "signal": "neutral",
                "confidence": 0.0,
                "reason": "Insufficient data for ICT analysis"
            }

        # 1. Identify market structure (trend, BOS, CHoCH)
        self.market_structure = self._detect_market_structure(df)

        # 2. Identify order blocks (institutional zones)
        self.order_blocks = self._find_order_blocks(df)

        # 3. Identify fair value gaps (imbalances)
        self.fair_value_gaps = self._find_fair_value_gaps(df)

        # 4. Identify liquidity pools (stop hunt zones)
        self.liquidity_pools = self._find_liquidity_pools(df)

        # 5. Check if we're in a kill zone
        in_kill_zone = self._is_kill_zone()

        # 6. Generate trading signal
        signal = self._generate_signal(df, in_kill_zone)

        return signal

    def _detect_market_structure(self, df: pd.DataFrame) -> MarketStructure:
        """
        Detect market structure using swing highs/lows

        Returns:
            MarketStructure object with trend and key levels
        """
        # Find swing highs and lows (local peaks/troughs)
        swing_window = 5
        swing_highs = []
        swing_lows = []

        for i in range(swing_window, len(df) - swing_window):
            # Swing high: higher than surrounding candles
            if df['high'].iloc[i] == df['high'].iloc[i-swing_window:i+swing_window+1].max():
                swing_highs.append((i, df['high'].iloc[i]))

            # Swing low: lower than surrounding candles
            if df['low'].iloc[i] == df['low'].iloc[i-swing_window:i+swing_window+1].min():
                swing_lows.append((i, df['low'].iloc[i]))

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return MarketStructure(trend="ranging")

        # Analyze structure
        recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows

        # Check for higher highs and higher lows (bullish structure)
        hh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i][1] > recent_highs[i-1][1])
        hl_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i][1] > recent_lows[i-1][1])

        # Check for lower lows and lower highs (bearish structure)
        ll_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i][1] < recent_lows[i-1][1])
        lh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i][1] < recent_highs[i-1][1])

        # Determine trend
        if hh_count >= 1 and hl_count >= 1:
            trend = "bullish"
        elif ll_count >= 1 and lh_count >= 1:
            trend = "bearish"
        else:
            trend = "ranging"

        # Check for structure break (BOS or CHoCH)
        current_price = df['close'].iloc[-1]
        structure_break = False

        if trend == "bullish" and len(recent_lows) >= 2:
            # Break of Structure: price breaks below recent higher low
            if current_price < recent_lows[-1][1]:
                structure_break = True
        elif trend == "bearish" and len(recent_highs) >= 2:
            # Break of Structure: price breaks above recent lower high
            if current_price > recent_highs[-1][1]:
                structure_break = True

        return MarketStructure(
            trend=trend,
            last_higher_high=recent_highs[-1][1] if trend == "bullish" and recent_highs else None,
            last_higher_low=recent_lows[-1][1] if trend == "bullish" and recent_lows else None,
            last_lower_high=recent_highs[-1][1] if trend == "bearish" and recent_highs else None,
            last_lower_low=recent_lows[-1][1] if trend == "bearish" and recent_lows else None,
            structure_break=structure_break
        )

    def _find_order_blocks(self, df: pd.DataFrame) -> list[OrderBlock]:
        """
        Identify order blocks (institutional buying/selling zones)

        Order Block = Last down candle before strong up move (bullish OB)
                      Last up candle before strong down move (bearish OB)
        """
        order_blocks = []
        min_displacement = 0.02  # 2% move to qualify as "strong"

        for i in range(10, len(df) - 1):
            # Bullish Order Block: Last red candle before strong green move
            if df['close'].iloc[i] < df['open'].iloc[i]:  # Red candle
                next_move = (df['close'].iloc[i+1] - df['close'].iloc[i]) / df['close'].iloc[i]
                if next_move > min_displacement:
                    strength = next_move / min_displacement
                    order_blocks.append(OrderBlock(
                        start_idx=i,
                        end_idx=i,
                        high=df['high'].iloc[i],
                        low=df['low'].iloc[i],
                        type="bullish",
                        strength=min(strength, 5.0)  # Cap at 5.0
                    ))

            # Bearish Order Block: Last green candle before strong red move
            elif df['close'].iloc[i] > df['open'].iloc[i]:  # Green candle
                next_move = (df['close'].iloc[i] - df['close'].iloc[i+1]) / df['close'].iloc[i]
                if next_move > min_displacement:
                    strength = next_move / min_displacement
                    order_blocks.append(OrderBlock(
                        start_idx=i,
                        end_idx=i,
                        high=df['high'].iloc[i],
                        low=df['low'].iloc[i],
                        type="bearish",
                        strength=min(strength, 5.0)
                    ))

        # Keep only recent and untouched order blocks
        recent_obs = [ob for ob in order_blocks[-20:] if not ob.touched]

        # Check if any have been touched by recent price action
        current_price = df['close'].iloc[-1]
        for ob in recent_obs:
            if ob.type == "bullish" and current_price <= ob.high:
                ob.touched = True
            elif ob.type == "bearish" and current_price >= ob.low:
                ob.touched = True

        return recent_obs

    def _find_fair_value_gaps(self, df: pd.DataFrame) -> list[FairValueGap]:
        """
        Identify Fair Value Gaps (FVG) - price imbalances

        FVG occurs when:
        - Bullish FVG: Candle 2's low > Candle 0's high (gap up)
        - Bearish FVG: Candle 2's high < Candle 0's low (gap down)
        """
        fvgs = []

        for i in range(2, len(df)):
            # Bullish FVG (gap that should pull price down to fill)
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                gap_size = (df['low'].iloc[i] - df['high'].iloc[i-2]) / df['high'].iloc[i-2]
                if gap_size > self.fvg_threshold:
                    fvgs.append(FairValueGap(
                        start_idx=i-2,
                        end_idx=i,
                        top=df['low'].iloc[i],
                        bottom=df['high'].iloc[i-2],
                        type="bullish"
                    ))

            # Bearish FVG (gap that should pull price up to fill)
            elif df['high'].iloc[i] < df['low'].iloc[i-2]:
                gap_size = (df['low'].iloc[i-2] - df['high'].iloc[i]) / df['high'].iloc[i]
                if gap_size > self.fvg_threshold:
                    fvgs.append(FairValueGap(
                        start_idx=i-2,
                        end_idx=i,
                        top=df['low'].iloc[i-2],
                        bottom=df['high'].iloc[i],
                        type="bearish"
                    ))

        # Keep only recent unfilled gaps
        recent_fvgs = [fvg for fvg in fvgs[-10:] if not fvg.filled]

        # Check if gaps have been filled
        current_price = df['close'].iloc[-1]
        for fvg in recent_fvgs:
            if fvg.type == "bullish" and current_price <= fvg.top:
                fvg.filled = True
                fvg.fill_percentage = 1.0
            elif fvg.type == "bearish" and current_price >= fvg.bottom:
                fvg.filled = True
                fvg.fill_percentage = 1.0

        return recent_fvgs

    def _find_liquidity_pools(self, df: pd.DataFrame) -> list[LiquidityPool]:
        """
        Identify liquidity pools (areas where stops cluster)

        Liquidity pools form at:
        - Equal highs (buy-side liquidity above)
        - Equal lows (sell-side liquidity below)
        - Round numbers
        """
        liquidity_pools = []
        tolerance = 0.001  # 0.1% tolerance for "equal" levels

        # Find equal highs (resistance tested multiple times)
        highs = df['high'].rolling(window=5).max()
        for i in range(20, len(df)):
            price_level = highs.iloc[i]
            # Count how many times this level was tested
            touches = sum(1 for j in range(max(0, i-50), i)
                         if abs(df['high'].iloc[j] - price_level) / price_level < tolerance)

            if touches >= 2:
                liquidity_pools.append(LiquidityPool(
                    price_level=price_level,
                    type="buy_side",
                    strength=touches
                ))

        # Find equal lows (support tested multiple times)
        lows = df['low'].rolling(window=5).min()
        for i in range(20, len(df)):
            price_level = lows.iloc[i]
            touches = sum(1 for j in range(max(0, i-50), i)
                         if abs(df['low'].iloc[j] - price_level) / price_level < tolerance)

            if touches >= 2:
                liquidity_pools.append(LiquidityPool(
                    price_level=price_level,
                    type="sell_side",
                    strength=touches
                ))

        # Remove duplicates and keep strongest pools
        unique_pools = {}
        for pool in liquidity_pools:
            key = f"{pool.type}_{round(pool.price_level, 2)}"
            if key not in unique_pools or pool.strength > unique_pools[key].strength:
                unique_pools[key] = pool

        return list(unique_pools.values())[-10:]  # Keep 10 most recent

    def _is_kill_zone(self) -> bool:
        """
        Check if current time is in a kill zone (optimal trading time)

        Kill Zones (EST):
        - London: 02:00 - 05:00
        - New York: 08:00 - 11:00
        """
        current_time = datetime.now().time()

        # London kill zone (02:00 - 05:00 EST)
        london_start = time(2, 0)
        london_end = time(5, 0)

        # New York kill zone (08:00 - 11:00 EST)
        ny_start = time(8, 0)
        ny_end = time(11, 0)

        return (london_start <= current_time <= london_end or
                ny_start <= current_time <= ny_end)

    def _generate_signal(self, df: pd.DataFrame, in_kill_zone: bool) -> dict:
        """
        Generate trading signal based on ICT concepts

        Strong signals occur when:
        1. Price is at an order block
        2. Price is at/near FVG
        3. Liquidity has been swept
        4. Market structure confirms direction
        5. We're in a kill zone
        """
        current_price = df['close'].iloc[-1]
        signal = "neutral"
        confidence = 0.0
        reasons = []
        entry_price = None
        stop_loss = None
        take_profit = None

        # Check for bullish setup
        bullish_score = 0
        bullish_reasons = []

        # 1. Price at bullish order block
        for ob in self.order_blocks:
            if ob.type == "bullish" and ob.low <= current_price <= ob.high and not ob.touched:
                bullish_score += 2 * ob.strength
                bullish_reasons.append(f"At bullish order block (strength {ob.strength:.1f})")
                stop_loss = ob.low * 0.995  # Stop below OB
                entry_price = current_price

        # 2. Unfilled bullish FVG below (discount zone)
        for fvg in self.fair_value_gaps:
            if fvg.type == "bullish" and not fvg.filled and current_price <= fvg.top:
                bullish_score += 1.5
                bullish_reasons.append("Price at bullish FVG (discount zone)")

        # 3. Sell-side liquidity swept
        for pool in self.liquidity_pools:
            if pool.type == "sell_side" and pool.swept and current_price > pool.price_level:
                bullish_score += 1.0
                bullish_reasons.append("Sell-side liquidity swept")

        # 4. Bullish market structure
        if self.market_structure.trend == "bullish":
            bullish_score += 1.0
            bullish_reasons.append("Bullish market structure")

        # Check for bearish setup
        bearish_score = 0
        bearish_reasons = []

        # 1. Price at bearish order block
        for ob in self.order_blocks:
            if ob.type == "bearish" and ob.low <= current_price <= ob.high and not ob.touched:
                bearish_score += 2 * ob.strength
                bearish_reasons.append(f"At bearish order block (strength {ob.strength:.1f})")
                stop_loss = ob.high * 1.005  # Stop above OB
                entry_price = current_price

        # 2. Unfilled bearish FVG above (premium zone)
        for fvg in self.fair_value_gaps:
            if fvg.type == "bearish" and not fvg.filled and current_price >= fvg.bottom:
                bearish_score += 1.5
                bearish_reasons.append("Price at bearish FVG (premium zone)")

        # 3. Buy-side liquidity swept
        for pool in self.liquidity_pools:
            if pool.type == "buy_side" and pool.swept and current_price < pool.price_level:
                bearish_score += 1.0
                bearish_reasons.append("Buy-side liquidity swept")

        # 4. Bearish market structure
        if self.market_structure.trend == "bearish":
            bearish_score += 1.0
            bearish_reasons.append("Bearish market structure")

        # Kill zone bonus
        if in_kill_zone:
            bullish_score *= 1.3
            bearish_score *= 1.3
            reasons.append("In kill zone (optimal trading time)")

        # Determine final signal
        if bullish_score > bearish_score and bullish_score >= 3.0:
            signal = "bullish"
            confidence = min(bullish_score * 10, 100)
            reasons = bullish_reasons + reasons
            if entry_price and stop_loss:
                risk = entry_price - stop_loss
                take_profit = entry_price + (risk * 2)  # 2:1 RR
        elif bearish_score > bullish_score and bearish_score >= 3.0:
            signal = "bearish"
            confidence = min(bearish_score * 10, 100)
            reasons = bearish_reasons + reasons
            if entry_price and stop_loss:
                risk = stop_loss - entry_price
                take_profit = entry_price - (risk * 2)  # 2:1 RR

        return {
            "signal": signal,
            "confidence": confidence,
            "reasons": reasons,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "market_structure": self.market_structure.trend,
            "in_kill_zone": in_kill_zone,
            "order_blocks_count": len([ob for ob in self.order_blocks if not ob.touched]),
            "fvg_count": len([fvg for fvg in self.fair_value_gaps if not fvg.filled]),
            "liquidity_pools_count": len(self.liquidity_pools)
        }
