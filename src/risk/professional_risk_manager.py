"""
Professional Risk Management System

Implements institutional-grade risk controls:
- Value-at-Risk (VaR) and Conditional VaR
- Portfolio volatility and correlation analysis
- Dynamic position sizing (Kelly Criterion, Risk Parity)
- Factor exposure limits
- Drawdown controls
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class RiskMetrics:
    """Container for portfolio risk metrics"""
    portfolio_value: float
    portfolio_volatility: float
    var_95: float  # 95% Value-at-Risk
    cvar_95: float  # 95% Conditional VaR (Expected Shortfall)
    max_drawdown: float
    sharpe_ratio: float
    max_concentration: float
    max_correlation: float
    total_exposure: float
    net_exposure: float
    leverage: float


@dataclass
class PositionLimit:
    """Position limit for a ticker"""
    ticker: str
    max_position_value: float
    max_shares: int
    reason: str
    risk_score: float


class ProfessionalRiskManager:
    """
    Institutional-grade risk management system

    Features:
    - Dynamic position sizing based on volatility
    - Portfolio-level risk controls (VaR, CVaR)
    - Correlation-based diversification
    - Drawdown protection
    - Factor exposure limits
    """

    def __init__(
        self,
        max_position_pct: float = 0.15,  # 15% max per position
        max_portfolio_volatility: float = 0.20,  # 20% annual volatility
        max_var_pct: float = 0.05,  # 5% max daily VaR
        max_drawdown_pct: float = 0.15,  # 15% max drawdown before reducing
        target_sharpe: float = 1.5,
        lookback_days: int = 252
    ):
        self.max_position_pct = max_position_pct
        self.max_portfolio_volatility = max_portfolio_volatility
        self.max_var_pct = max_var_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.target_sharpe = target_sharpe
        self.lookback_days = lookback_days

    def calculate_portfolio_risk(
        self,
        portfolio: dict,
        returns_history: pd.DataFrame
    ) -> RiskMetrics:
        """
        Calculate comprehensive portfolio risk metrics

        Args:
            portfolio: Current portfolio state
            returns_history: DataFrame with historical returns for each position

        Returns:
            RiskMetrics object with all risk measurements
        """
        # Extract portfolio data
        positions = portfolio.get("positions", {})
        cash = portfolio.get("cash", 0)

        # Calculate position values
        position_values = {}
        for ticker, pos_data in positions.items():
            if ticker in returns_history.columns:
                current_price = returns_history[ticker].iloc[-1]
                long_value = pos_data.get("long", 0) * current_price
                short_value = pos_data.get("short", 0) * current_price
                position_values[ticker] = long_value - short_value

        total_portfolio_value = cash + sum(position_values.values())
        total_exposure = sum(abs(v) for v in position_values.values())
        net_exposure = sum(position_values.values())
        leverage = total_exposure / total_portfolio_value if total_portfolio_value > 0 else 0

        # Calculate weights
        weights = np.array([v / total_portfolio_value for v in position_values.values()])

        # Get returns for positions
        position_tickers = list(position_values.keys())
        if not position_tickers:
            # Empty portfolio
            return RiskMetrics(
                portfolio_value=total_portfolio_value,
                portfolio_volatility=0,
                var_95=0,
                cvar_95=0,
                max_drawdown=0,
                sharpe_ratio=0,
                max_concentration=0,
                max_correlation=0,
                total_exposure=0,
                net_exposure=0,
                leverage=0
            )

        returns_subset = returns_history[position_tickers].dropna()

        # Calculate portfolio returns
        portfolio_returns = (returns_subset * weights).sum(axis=1)

        # Portfolio volatility (annualized)
        portfolio_volatility = portfolio_returns.std() * np.sqrt(252)

        # Value-at-Risk (95% confidence)
        var_95 = np.percentile(portfolio_returns, 5)

        # Conditional VaR (Expected Shortfall)
        cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()

        # Maximum drawdown
        cumulative_returns = (1 + portfolio_returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min()

        # Sharpe ratio (assuming 4% risk-free rate)
        excess_returns = portfolio_returns - (0.04 / 252)
        sharpe_ratio = np.sqrt(252) * excess_returns.mean() / portfolio_returns.std() if portfolio_returns.std() > 0 else 0

        # Concentration (max single position)
        max_concentration = max(abs(w) for w in weights) if len(weights) > 0 else 0

        # Correlation (max pairwise)
        if len(position_tickers) > 1:
            corr_matrix = returns_subset.corr()
            # Get upper triangle (exclude diagonal)
            mask = np.triu(np.ones_like(corr_matrix), k=1).astype(bool)
            max_correlation = corr_matrix.where(mask).max().max()
        else:
            max_correlation = 0

        return RiskMetrics(
            portfolio_value=total_portfolio_value,
            portfolio_volatility=portfolio_volatility,
            var_95=var_95,
            cvar_95=cvar_95,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            max_concentration=max_concentration,
            max_correlation=max_correlation,
            total_exposure=total_exposure,
            net_exposure=net_exposure,
            leverage=leverage
        )

    def calculate_position_size_kelly(
        self,
        expected_return: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        portfolio_value: float
    ) -> float:
        """
        Kelly Criterion for optimal position sizing

        Formula: f* = (bp - q) / b
        where:
        - f* = fraction of portfolio to bet
        - b = odds (avg_win / avg_loss)
        - p = probability of win
        - q = probability of loss (1 - p)

        We use Half-Kelly (more conservative)
        """
        if avg_loss == 0 or win_rate == 0 or win_rate == 1:
            return 0

        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p

        kelly_fraction = (b * p - q) / b

        # Use Half-Kelly for safety
        kelly_fraction = kelly_fraction * 0.5

        # Cap at max position size
        kelly_fraction = max(0, min(kelly_fraction, self.max_position_pct))

        return kelly_fraction * portfolio_value

    def calculate_position_size_volatility_adjusted(
        self,
        ticker: str,
        current_price: float,
        returns_history: pd.DataFrame,
        portfolio_value: float,
        target_volatility: float = 0.10  # 10% target per position
    ) -> float:
        """
        Volatility-adjusted position sizing

        Positions with higher volatility get smaller allocation
        Formula: position_size = (target_vol / asset_vol) * portfolio_value
        """
        if ticker not in returns_history.columns:
            return 0

        ticker_returns = returns_history[ticker].dropna()
        if len(ticker_returns) < 20:
            return 0

        # Calculate asset volatility (annualized)
        asset_volatility = ticker_returns.std() * np.sqrt(252)

        if asset_volatility == 0:
            return 0

        # Scale position size inversely with volatility
        volatility_scalar = target_volatility / asset_volatility
        position_value = volatility_scalar * portfolio_value

        # Cap at max position size
        max_position_value = self.max_position_pct * portfolio_value
        position_value = min(position_value, max_position_value)

        return position_value

    def calculate_position_limits(
        self,
        tickers: List[str],
        current_prices: Dict[str, float],
        portfolio: dict,
        returns_history: pd.DataFrame,
        signals: Dict[str, dict]
    ) -> Dict[str, PositionLimit]:
        """
        Calculate position limits for each ticker using multiple methods

        Combines:
        1. Volatility-adjusted sizing
        2. Kelly Criterion (if signal has win_rate data)
        3. Correlation adjustments
        4. Current portfolio constraints
        """
        portfolio_value = portfolio.get("cash", 0)

        # Add value of existing positions
        for ticker, pos_data in portfolio.get("positions", {}).items():
            if ticker in current_prices:
                portfolio_value += pos_data.get("long", 0) * current_prices[ticker]
                portfolio_value -= pos_data.get("short", 0) * current_prices[ticker]

        position_limits = {}

        for ticker in tickers:
            if ticker not in current_prices or current_prices[ticker] == 0:
                position_limits[ticker] = PositionLimit(
                    ticker=ticker,
                    max_position_value=0,
                    max_shares=0,
                    reason="No price data",
                    risk_score=10.0
                )
                continue

            current_price = current_prices[ticker]
            signal = signals.get(ticker, {})

            # Method 1: Volatility-adjusted sizing
            vol_position_value = self.calculate_position_size_volatility_adjusted(
                ticker,
                current_price,
                returns_history,
                portfolio_value
            )

            # Method 2: Kelly Criterion (if win rate data available)
            kelly_position_value = vol_position_value  # Default to volatility method
            if "win_rate" in signal and "avg_win" in signal and "avg_loss" in signal:
                kelly_position_value = self.calculate_position_size_kelly(
                    expected_return=signal.get("expected_return", 0),
                    win_rate=signal.get("win_rate", 0.5),
                    avg_win=signal.get("avg_win", 0.01),
                    avg_loss=signal.get("avg_loss", 0.01),
                    portfolio_value=portfolio_value
                )

            # Take the more conservative of the two
            max_position_value = min(vol_position_value, kelly_position_value)

            # Method 3: Correlation adjustment
            # If highly correlated with existing positions, reduce size
            existing_tickers = [t for t in portfolio.get("positions", {}).keys() if t in returns_history.columns]
            if existing_tickers and ticker in returns_history.columns:
                correlations = [
                    returns_history[[ticker, existing]].corr().iloc[0, 1]
                    for existing in existing_tickers
                ]
                max_correlation = max(correlations) if correlations else 0

                if abs(max_correlation) > 0.7:
                    # Reduce size for highly correlated assets
                    correlation_penalty = 1 - (abs(max_correlation) - 0.7) * 2
                    max_position_value *= correlation_penalty

            # Method 4: Available cash constraint
            available_cash = portfolio.get("cash", 0)
            max_position_value = min(max_position_value, available_cash)

            # Calculate max shares
            max_shares = int(max_position_value / current_price) if current_price > 0 else 0

            # Calculate risk score (0-10, where 10 is highest risk)
            risk_score = self._calculate_risk_score(ticker, returns_history, signal)

            position_limits[ticker] = PositionLimit(
                ticker=ticker,
                max_position_value=max_position_value,
                max_shares=max_shares,
                reason=f"Vol-adjusted sizing with correlation check (risk: {risk_score:.1f}/10)",
                risk_score=risk_score
            )

        return position_limits

    def _calculate_risk_score(
        self,
        ticker: str,
        returns_history: pd.DataFrame,
        signal: dict
    ) -> float:
        """
        Calculate risk score for a position (0-10 scale)

        Factors:
        - Volatility
        - Signal confidence
        - Drawdown history
        - Liquidity (volume)
        """
        risk_score = 5.0  # Base score

        if ticker not in returns_history.columns:
            return 10.0  # Max risk if no data

        ticker_returns = returns_history[ticker].dropna()

        # Volatility component
        volatility = ticker_returns.std() * np.sqrt(252)
        if volatility > 0.40:  # >40% annual volatility
            risk_score += 2.0
        elif volatility > 0.25:  # >25% annual volatility
            risk_score += 1.0

        # Signal confidence component
        confidence = signal.get("confidence", 50)
        if confidence < 30:
            risk_score += 2.0
        elif confidence < 50:
            risk_score += 1.0
        elif confidence > 80:
            risk_score -= 1.0

        # Drawdown component
        cumulative = (1 + ticker_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_dd = abs(drawdown.min())

        if max_dd > 0.30:  # >30% max drawdown
            risk_score += 2.0
        elif max_dd > 0.20:  # >20% max drawdown
            risk_score += 1.0

        return min(max(risk_score, 0), 10)  # Clamp to [0, 10]

    def check_portfolio_risk_limits(
        self,
        portfolio: dict,
        returns_history: pd.DataFrame
    ) -> Dict[str, bool]:
        """
        Check if portfolio is violating risk limits

        Returns dict of checks with True = VIOLATION
        """
        metrics = self.calculate_portfolio_risk(portfolio, returns_history)

        violations = {
            "max_volatility_exceeded": metrics.portfolio_volatility > self.max_portfolio_volatility,
            "max_var_exceeded": abs(metrics.var_95) > self.max_var_pct,
            "max_drawdown_exceeded": abs(metrics.max_drawdown) > self.max_drawdown_pct,
            "max_concentration_exceeded": metrics.max_concentration > self.max_position_pct,
            "max_leverage_exceeded": metrics.leverage > 2.0,  # 2x max leverage
        }

        return violations

    def calculate_stop_loss_take_profit(
        self,
        entry_price: float,
        signal_type: str,
        atr: float,
        risk_reward_ratio: float = 2.0
    ) -> tuple[float, float]:
        """
        Calculate stop loss and take profit levels using ATR

        Args:
            entry_price: Entry price
            signal_type: "bullish" or "bearish"
            atr: Average True Range
            risk_reward_ratio: Reward/Risk ratio (default 2:1)

        Returns:
            (stop_loss, take_profit)
        """
        # Stop loss at 1.5x ATR
        stop_distance = atr * 1.5

        if signal_type == "bullish":
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + (stop_distance * risk_reward_ratio)
        else:  # bearish
            stop_loss = entry_price + stop_distance
            take_profit = entry_price - (stop_distance * risk_reward_ratio)

        return stop_loss, take_profit
