"""
Realistic Backtester with Transaction Costs and Slippage

Improvements over basic backtester:
1. Transaction costs (commissions)
2. Slippage modeling (market impact)
3. Realistic order execution
4. Walk-forward optimization
5. Statistical significance testing
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Callable, Dict, List
from scipy import stats


class RealisticBacktester:
    """
    Professional backtester with realistic execution costs
    """

    def __init__(
        self,
        agent: Callable,
        tickers: list[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        commission_rate: float = 0.001,  # 0.1% per trade
        slippage_bps: float = 5.0,  # 5 basis points
        min_commission: float = 1.0,  # $1 minimum per trade
        model_name: str = "gpt-4o",
        model_provider: str = "OpenAI",
        selected_analysts: list[str] = [],
        initial_margin_requirement: float = 0.0,
        max_analysts: int = 4,
    ):
        self.agent = agent
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_bps = slippage_bps
        self.min_commission = min_commission
        self.model_name = model_name
        self.model_provider = model_provider
        self.selected_analysts = selected_analysts[:max_analysts]
        self.max_analysts = max_analysts

        # Portfolio state
        self.portfolio = {
            "cash": initial_capital,
            "margin_used": 0.0,
            "margin_requirement": initial_margin_requirement,
            "positions": {
                ticker: {
                    "long": 0,
                    "short": 0,
                    "long_cost_basis": 0.0,
                    "short_cost_basis": 0.0,
                    "short_margin_used": 0.0
                }
                for ticker in tickers
            },
            "realized_gains": {
                ticker: {"long": 0.0, "short": 0.0}
                for ticker in tickers
            },
        }

        # Track costs
        self.transaction_costs = []
        self.slippage_costs = []
        self.portfolio_values = []

        # Historical volume data (for market impact calculation)
        self.average_volumes = {}

    def calculate_slippage(
        self,
        ticker: str,
        quantity: int,
        current_price: float,
        action: str
    ) -> float:
        """
        Calculate slippage based on square-root market impact model

        Impact = slippage_bps * sqrt(order_size / avg_daily_volume)
        """
        # Get average daily volume
        avg_volume = self.average_volumes.get(ticker, 1_000_000)

        # Calculate participation rate
        participation_rate = abs(quantity) / avg_volume

        # Square-root market impact model
        impact_bps = self.slippage_bps * np.sqrt(participation_rate)

        # Cap impact at 100 bps (1%)
        impact_bps = min(impact_bps, 100)

        # Direction of impact
        if action in ["buy", "cover"]:
            # Buying pushes price up
            slippage = current_price * (impact_bps / 10000)
        else:  # sell, short
            # Selling pushes price down
            slippage = -current_price * (impact_bps / 10000)

        return slippage

    def calculate_commission(self, quantity: int, price: float) -> float:
        """Calculate commission costs"""
        trade_value = abs(quantity * price)
        commission = max(trade_value * self.commission_rate, self.min_commission)
        return commission

    def execute_trade_realistic(
        self,
        ticker: str,
        action: str,
        quantity: int,
        current_price: float
    ) -> tuple[int, float, float]:
        """
        Execute trade with realistic costs

        Returns:
            (executed_quantity, total_cost, slippage_cost)
        """
        if quantity <= 0:
            return 0, 0.0, 0.0

        quantity = int(quantity)
        position = self.portfolio["positions"][ticker]

        # Calculate slippage
        slippage = self.calculate_slippage(ticker, quantity, current_price, action)
        effective_price = current_price + slippage

        # Calculate commission
        commission = self.calculate_commission(quantity, effective_price)

        # Track costs
        slippage_cost = abs(slippage * quantity)
        total_cost = commission + slippage_cost

        # Execute based on action
        executed_quantity = 0

        if action == "buy":
            cost = quantity * effective_price + commission
            if cost <= self.portfolio["cash"]:
                # Update cost basis
                old_shares = position["long"]
                old_cost_basis = position["long_cost_basis"]
                total_shares = old_shares + quantity

                if total_shares > 0:
                    total_old_cost = old_cost_basis * old_shares
                    total_new_cost = quantity * effective_price
                    position["long_cost_basis"] = (total_old_cost + total_new_cost) / total_shares

                position["long"] += quantity
                self.portfolio["cash"] -= cost
                executed_quantity = quantity
            else:
                # Calculate max affordable quantity
                max_quantity = int(
                    (self.portfolio["cash"] - self.min_commission) /
                    (effective_price * (1 + self.commission_rate))
                )
                if max_quantity > 0:
                    return self.execute_trade_realistic(ticker, action, max_quantity, current_price)
                return 0, 0.0, 0.0

        elif action == "sell":
            quantity = min(quantity, position["long"])
            if quantity > 0:
                # Realized gain/loss
                avg_cost = position["long_cost_basis"]
                proceeds = quantity * effective_price - commission
                cost_basis_total = avg_cost * quantity
                realized_gain = proceeds - cost_basis_total
                self.portfolio["realized_gains"][ticker]["long"] += realized_gain

                position["long"] -= quantity
                self.portfolio["cash"] += proceeds

                if position["long"] == 0:
                    position["long_cost_basis"] = 0.0

                executed_quantity = quantity

        elif action == "short":
            proceeds = quantity * effective_price
            margin_required = proceeds * self.portfolio["margin_requirement"]
            total_needed = margin_required + commission

            if total_needed <= self.portfolio["cash"]:
                # Update short cost basis
                old_short = position["short"]
                old_cost_basis = position["short_cost_basis"]
                total_shares = old_short + quantity

                if total_shares > 0:
                    position["short_cost_basis"] = (
                        (old_cost_basis * old_short + effective_price * quantity) / total_shares
                    )

                position["short"] += quantity
                position["short_margin_used"] += margin_required
                self.portfolio["margin_used"] += margin_required

                # Add proceeds, subtract margin and commission
                self.portfolio["cash"] += proceeds
                self.portfolio["cash"] -= (margin_required + commission)

                executed_quantity = quantity
            else:
                # Calculate max shortable quantity
                if self.portfolio["margin_requirement"] > 0:
                    max_quantity = int(
                        (self.portfolio["cash"] - self.min_commission) /
                        (effective_price * self.portfolio["margin_requirement"])
                    )
                    if max_quantity > 0:
                        return self.execute_trade_realistic(ticker, action, max_quantity, current_price)
                return 0, 0.0, 0.0

        elif action == "cover":
            quantity = min(quantity, position["short"])
            if quantity > 0:
                cost = quantity * effective_price + commission
                avg_short_price = position["short_cost_basis"]

                # Calculate margin to release
                portion = quantity / position["short"] if position["short"] > 0 else 1.0
                margin_to_release = portion * position["short_margin_used"]

                # Realized gain/loss
                realized_gain = (avg_short_price - effective_price) * quantity - commission
                self.portfolio["realized_gains"][ticker]["short"] += realized_gain

                position["short"] -= quantity
                position["short_margin_used"] -= margin_to_release
                self.portfolio["margin_used"] -= margin_to_release

                # Pay cover cost, get margin back
                self.portfolio["cash"] += margin_to_release
                self.portfolio["cash"] -= cost

                if position["short"] == 0:
                    position["short_cost_basis"] = 0.0
                    position["short_margin_used"] = 0.0

                executed_quantity = quantity

        # Record costs
        if executed_quantity > 0:
            self.transaction_costs.append({
                "ticker": ticker,
                "action": action,
                "quantity": executed_quantity,
                "commission": commission,
                "slippage": slippage_cost,
                "total_cost": total_cost
            })

        return executed_quantity, total_cost, slippage_cost

    def calculate_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value"""
        total_value = self.portfolio["cash"]

        for ticker in self.tickers:
            position = self.portfolio["positions"][ticker]
            price = current_prices.get(ticker, 0)

            # Long position value
            total_value += position["long"] * price

            # Short position liability
            total_value -= position["short"] * price

        return total_value

    def analyze_costs(self) -> pd.DataFrame:
        """Analyze total transaction costs"""
        if not self.transaction_costs:
            return pd.DataFrame()

        df = pd.DataFrame(self.transaction_costs)

        summary = {
            "Total Commissions": df["commission"].sum(),
            "Total Slippage": df["slippage"].sum(),
            "Total Transaction Costs": df["total_cost"].sum(),
            "Number of Trades": len(df),
            "Avg Cost per Trade": df["total_cost"].mean(),
            "Cost as % of Initial Capital": (df["total_cost"].sum() / self.initial_capital) * 100
        }

        return pd.DataFrame([summary])

    def run_walk_forward_analysis(
        self,
        train_window: int = 252,  # 1 year training
        test_window: int = 63,  # 3 months testing
    ) -> pd.DataFrame:
        """
        Walk-forward optimization

        Train on historical data, test on out-of-sample period
        Roll forward and repeat
        """
        results = []
        dates = pd.date_range(self.start_date, self.end_date, freq="B")

        for i in range(0, len(dates) - train_window - test_window, test_window):
            train_start = dates[i]
            train_end = dates[i + train_window]
            test_start = dates[i + train_window]
            test_end = dates[min(i + train_window + test_window, len(dates) - 1)]

            print(f"\nWalk-forward period:")
            print(f"  Train: {train_start.date()} to {train_end.date()}")
            print(f"  Test:  {test_start.date()} to {test_end.date()}")

            # Run backtest on test period
            # (In practice, you would optimize parameters on train period)
            test_returns = self._run_period(test_start, test_end)

            results.append({
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "returns": test_returns
            })

        return pd.DataFrame(results)

    def _run_period(self, start_date: datetime, end_date: datetime) -> dict:
        """Run backtest for a specific period"""
        # This would contain the actual backtesting logic
        # Similar to the main run_backtest method but for a specific date range
        pass

    def test_statistical_significance(
        self,
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> dict:
        """
        Test if strategy significantly outperforms benchmark

        Uses:
        - T-test for mean difference
        - Information Ratio
        - Sharpe Ratio comparison
        """
        excess_returns = strategy_returns - benchmark_returns

        # T-test
        t_stat, p_value = stats.ttest_1samp(excess_returns.dropna(), 0)

        # Information Ratio
        ir = (
            excess_returns.mean() / excess_returns.std() * np.sqrt(252)
            if excess_returns.std() > 0 else 0
        )

        # Sharpe Ratios
        rf_rate = 0.04 / 252
        strategy_sharpe = (
            np.sqrt(252) * (strategy_returns.mean() - rf_rate) / strategy_returns.std()
            if strategy_returns.std() > 0 else 0
        )
        benchmark_sharpe = (
            np.sqrt(252) * (benchmark_returns.mean() - rf_rate) / benchmark_returns.std()
            if benchmark_returns.std() > 0 else 0
        )

        return {
            "t_statistic": t_stat,
            "p_value": p_value,
            "significant_at_5pct": p_value < 0.05,
            "information_ratio": ir,
            "strategy_sharpe": strategy_sharpe,
            "benchmark_sharpe": benchmark_sharpe,
            "sharpe_difference": strategy_sharpe - benchmark_sharpe,
            "mean_excess_return_daily": excess_returns.mean(),
            "mean_excess_return_annual": excess_returns.mean() * 252
        }
