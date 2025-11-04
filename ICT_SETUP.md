# ICT Trading System Setup Guide

This guide explains how to use the new ICT (Inner Circle Trader) trading system with TradingView integration and professional risk management.

## 🎯 What's New

### 1. ICT Strategy Implementation
- **Order Blocks**: Identifies institutional buying/selling zones
- **Fair Value Gaps (FVG)**: Detects price imbalances
- **Liquidity Pools**: Finds stop hunt zones
- **Market Structure**: Detects BOS (Break of Structure) and CHoCH (Change of Character)
- **Kill Zones**: London (02:00-05:00 EST) and NY (08:00-11:00 EST) session times

### 2. TradingView Integration
- Real-time data fetching via Yahoo Finance API
- Webhook receiver for TradingView alerts
- Technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR)
- Chart data in pandas DataFrame format

### 3. Professional Risk Management
- **Value-at-Risk (VaR)** and **Conditional VaR (CVaR)**
- **Dynamic Position Sizing**: Kelly Criterion and volatility-adjusted sizing
- **Portfolio Risk Metrics**: Correlation, concentration, leverage limits
- **Stop Loss/Take Profit**: ATR-based with configurable risk:reward ratios

### 4. Realistic Backtesting
- **Transaction Costs**: Commission fees (default 0.1% per trade)
- **Slippage**: Square-root market impact model
- **Walk-Forward Optimization**: Train/test splits with out-of-sample validation
- **Statistical Significance Testing**: T-tests and Information Ratio

---

## 📦 Installation

### Additional Dependencies

Add these to your existing Poetry environment:

```bash
poetry add scipy fastapi uvicorn websockets
```

Or update your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
scipy = "^1.11.0"
fastapi = "^0.104.0"
uvicorn = "^0.24.0"
websockets = "^12.0"
```

Then run:
```bash
poetry install
```

---

## 🚀 Quick Start

### 1. Run ICT Strategy Analysis

```bash
# Run ICT analysis on a ticker
poetry run python -c "
from src.strategies.ict_strategy import ICTStrategy
from src.integrations.tradingview import TradingViewClient

# Fetch data
tv_client = TradingViewClient()
df = tv_client.get_historical_data('AAPL', interval='1h', period='7d')

# Analyze with ICT
ict = ICTStrategy()
signal = ict.analyze(df)

print('Signal:', signal['signal'])
print('Confidence:', signal['confidence'])
print('Reasons:', signal['reasons'])
"
```

### 2. Run with ICT Agent in Main System

Update your analyst selection to include the ICT agent:

```python
# In src/utils/analysts.py, add:
("ICT Trader", "ict_agent"),
```

Then run:
```bash
poetry run python src/main.py --ticker AAPL,MSFT --analysts ict_agent
```

### 3. Start TradingView Webhook Server

```bash
# In a separate terminal, start the FastAPI server
poetry run uvicorn src.integrations.tradingview:tradingview_router --host 0.0.0.0 --port 8000
```

This starts a webhook receiver at `http://localhost:8000/tradingview/webhook`

---

## 📊 TradingView Integration

### Setting Up TradingView Alerts

1. **Create Alert in TradingView**:
   - Open your chart
   - Click the Alert icon (⏰)
   - Set your conditions (e.g., "Price crosses SMA 50")

2. **Configure Webhook**:
   - In the alert settings, check "Webhook URL"
   - Enter: `http://your-server-ip:8000/tradingview/webhook`

3. **Set Alert Message** (JSON format):
```json
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
```

4. **Test Alert**:
   - Trigger the alert manually
   - Check your server logs for incoming webhook

### Fetching Real-Time Data

```python
from src.integrations.tradingview import TradingViewClient

tv = TradingViewClient()

# Get current price
price_data = tv.get_realtime_price("AAPL")
print(f"Current price: ${price_data['price']}")
print(f"Change: {price_data['change_percent']:.2f}%")

# Get historical data
df = tv.get_historical_data(
    ticker="AAPL",
    interval="1h",
    period="30d"
)

# Add indicators
df = tv.calculate_indicators(df)
print(df[['close', 'rsi', 'macd']].tail())
```

---

## 🎛️ Risk Management

### Using Professional Risk Manager

```python
from src.risk.professional_risk_manager import ProfessionalRiskManager

# Initialize risk manager
risk_mgr = ProfessionalRiskManager(
    max_position_pct=0.15,  # 15% max per position
    max_portfolio_volatility=0.20,  # 20% annual volatility
    max_var_pct=0.05,  # 5% max daily VaR
    max_drawdown_pct=0.15,  # 15% max drawdown
)

# Calculate position limits
position_limits = risk_mgr.calculate_position_limits(
    tickers=['AAPL', 'MSFT'],
    current_prices={'AAPL': 180.0, 'MSFT': 380.0},
    portfolio=portfolio,
    returns_history=returns_df,
    signals=signals
)

for ticker, limit in position_limits.items():
    print(f"{ticker}:")
    print(f"  Max position: ${limit.max_position_value:,.2f}")
    print(f"  Max shares: {limit.max_shares}")
    print(f"  Risk score: {limit.risk_score}/10")

# Check portfolio risk
risk_metrics = risk_mgr.calculate_portfolio_risk(portfolio, returns_df)
print(f"Portfolio VaR (95%): {risk_metrics.var_95:.2%}")
print(f"Portfolio CVaR (95%): {risk_metrics.cvar_95:.2%}")
print(f"Max Drawdown: {risk_metrics.max_drawdown:.2%}")
print(f"Sharpe Ratio: {risk_metrics.sharpe_ratio:.2f}")

# Calculate stop loss and take profit
entry_price = 180.0
atr = 3.5
stop_loss, take_profit = risk_mgr.calculate_stop_loss_take_profit(
    entry_price=entry_price,
    signal_type="bullish",
    atr=atr,
    risk_reward_ratio=2.0  # 2:1 RR
)
print(f"Entry: ${entry_price}")
print(f"Stop Loss: ${stop_loss:.2f}")
print(f"Take Profit: ${take_profit:.2f}")
```

---

## 🔬 Realistic Backtesting

### Running Backtest with Transaction Costs

```python
from src.backtest.realistic_backtester import RealisticBacktester

backtester = RealisticBacktester(
    agent=run_hedge_fund,
    tickers=['AAPL', 'MSFT'],
    start_date='2024-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    commission_rate=0.001,  # 0.1% per trade
    slippage_bps=5.0,  # 5 basis points slippage
    min_commission=1.0,  # $1 minimum
    selected_analysts=['ict_agent']
)

# Run backtest
performance = backtester.run_backtest()

# Analyze costs
cost_analysis = backtester.analyze_costs()
print(cost_analysis)

# Output:
#   Total Commissions: $1,234.56
#   Total Slippage: $567.89
#   Total Transaction Costs: $1,802.45
#   Cost as % of Initial Capital: 1.80%
```

### Walk-Forward Analysis

```python
# Run walk-forward optimization
wf_results = backtester.run_walk_forward_analysis(
    train_window=252,  # 1 year training
    test_window=63     # 3 months testing
)

print(wf_results)
```

### Statistical Significance Testing

```python
import pandas as pd

# Compare strategy vs benchmark
strategy_returns = pd.Series([...])  # Your strategy returns
benchmark_returns = pd.Series([...])  # S&P 500 returns

significance = backtester.test_statistical_significance(
    strategy_returns,
    benchmark_returns
)

print(f"T-Statistic: {significance['t_statistic']:.3f}")
print(f"P-Value: {significance['p_value']:.4f}")
print(f"Significant at 5%: {significance['significant_at_5pct']}")
print(f"Information Ratio: {significance['information_ratio']:.2f}")
print(f"Strategy Sharpe: {significance['strategy_sharpe']:.2f}")
print(f"Benchmark Sharpe: {significance['benchmark_sharpe']:.2f}")
```

---

## 🏗️ Architecture Changes

### New File Structure

```
ai-hedge-fund/
├── src/
│   ├── agents/
│   │   └── ict_agent.py          # NEW: ICT trading agent
│   ├── strategies/
│   │   └── ict_strategy.py       # NEW: ICT strategy implementation
│   ├── integrations/
│   │   └── tradingview.py        # NEW: TradingView integration
│   ├── risk/
│   │   └── professional_risk_manager.py  # NEW: Advanced risk management
│   ├── backtest/
│   │   └── realistic_backtester.py  # NEW: Improved backtester
│   └── ... (existing files)
├── ICT_SETUP.md                   # NEW: This file
└── ... (existing files)
```

### Integration Points

1. **ICT Agent** → Uses TradingView client → Generates signals
2. **Risk Manager** → Validates signals → Calculates position limits
3. **Portfolio Manager** → Receives limits → Executes with costs
4. **Backtester** → Tracks performance → Calculates metrics

---

## 🎨 Customization

### Adjust ICT Parameters

```python
from src.strategies.ict_strategy import ICTStrategy

ict = ICTStrategy(
    lookback_period=100,              # How far back to look
    fvg_threshold=0.001,              # Minimum gap size (0.1%)
    order_block_strength_threshold=0.5  # Minimum OB strength
)
```

### Adjust Risk Parameters

```python
from src.risk.professional_risk_manager import ProfessionalRiskManager

risk_mgr = ProfessionalRiskManager(
    max_position_pct=0.10,            # 10% max per position (more conservative)
    max_portfolio_volatility=0.15,    # 15% annual volatility target
    max_var_pct=0.03,                 # 3% max daily VaR
    max_drawdown_pct=0.10,            # 10% max drawdown
    target_sharpe=2.0,                # Target Sharpe ratio
    lookback_days=252                 # 1 year lookback
)
```

### Adjust Transaction Costs

```python
from src.backtest.realistic_backtester import RealisticBacktester

backtester = RealisticBacktester(
    commission_rate=0.0005,  # 0.05% (Interactive Brokers-like)
    slippage_bps=2.0,        # 2 bps (very liquid stocks)
    min_commission=0.35      # $0.35 minimum (IBKR pricing)
)
```

---

## 🧪 Testing

### Test ICT Strategy

```bash
poetry run python -m pytest tests/test_ict_strategy.py -v
```

### Test TradingView Integration

```bash
# Test webhook receiver
curl -X POST http://localhost:8000/tradingview/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "signal": "buy",
    "price": 180.0,
    "time": "2024-01-01T09:30:00"
  }'
```

### Test Risk Manager

```bash
poetry run python -m pytest tests/test_risk_manager.py -v
```

---

## 📈 Example: Complete Workflow

```python
from src.strategies.ict_strategy import ICTStrategy
from src.integrations.tradingview import TradingViewClient
from src.risk.professional_risk_manager import ProfessionalRiskManager

# 1. Fetch data from TradingView
tv = TradingViewClient()
df = tv.get_historical_data('AAPL', interval='1h', period='30d')
df = tv.calculate_indicators(df)

# 2. Run ICT analysis
ict = ICTStrategy()
signal = ict.analyze(df)

print(f"Signal: {signal['signal']}")
print(f"Confidence: {signal['confidence']:.1f}%")
print(f"Entry: ${signal['entry_price']:.2f}")
print(f"Stop: ${signal['stop_loss']:.2f}")
print(f"Target: ${signal['take_profit']:.2f}")

# 3. Calculate position size with risk management
risk_mgr = ProfessionalRiskManager()

# Get historical returns for risk calculation
returns_df = df[['close']].pct_change().dropna()
returns_df.columns = ['AAPL']

position_limit = risk_mgr.calculate_position_size_volatility_adjusted(
    ticker='AAPL',
    current_price=signal['entry_price'],
    returns_history=returns_df,
    portfolio_value=100000
)

shares = int(position_limit / signal['entry_price'])
print(f"Position size: {shares} shares (${position_limit:,.2f})")

# 4. Calculate risk:reward
risk = signal['entry_price'] - signal['stop_loss']
reward = signal['take_profit'] - signal['entry_price']
rr_ratio = reward / risk if risk > 0 else 0

print(f"Risk: ${risk:.2f} per share")
print(f"Reward: ${reward:.2f} per share")
print(f"R:R Ratio: {rr_ratio:.2f}:1")

# 5. Execute trade (paper trading)
if signal['signal'] == 'bullish' and signal['confidence'] > 70 and rr_ratio >= 2.0:
    print(f"\n✅ EXECUTE BUY: {shares} shares @ ${signal['entry_price']:.2f}")
    print(f"   Stop Loss: ${signal['stop_loss']:.2f}")
    print(f"   Take Profit: ${signal['take_profit']:.2f}")
else:
    print(f"\n❌ SKIP: Signal not strong enough or poor R:R")
```

---

## 🚨 Important Notes

### Risk Warnings

1. **This is still educational software** - Do not use for real trading without extensive testing
2. **Past performance ≠ future results** - Backtest results may not reflect live trading
3. **Transaction costs matter** - Real costs may be higher than modeled
4. **Slippage varies** - Market conditions affect execution quality
5. **ICT is discretionary** - Automated implementation may miss nuances

### Production Checklist

Before using in production:

- [ ] Test on paper trading account for 3-6 months
- [ ] Validate all ICT concepts manually on charts
- [ ] Verify transaction cost assumptions with your broker
- [ ] Test webhook reliability under load
- [ ] Implement monitoring and alerts
- [ ] Add database for persistent storage
- [ ] Set up proper error handling and logging
- [ ] Implement circuit breakers for extreme conditions
- [ ] Add multi-timeframe analysis
- [ ] Backtest on at least 5 years of data
- [ ] Compare results with manual ICT trading

---

## 📚 Resources

### ICT Concepts
- [ICT YouTube Channel](https://www.youtube.com/@InnerCircleTrader)
- [Order Blocks Explained](https://www.tradingview.com/script/...)
- [Fair Value Gaps Guide](https://www.tradingview.com/script/...)

### TradingView
- [TradingView Webhooks Documentation](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/)
- [TradingView Pine Script](https://www.tradingview.com/pine-script-docs/)

### Risk Management
- [Kelly Criterion](https://en.wikipedia.org/wiki/Kelly_criterion)
- [Value at Risk](https://en.wikipedia.org/wiki/Value_at_risk)
- [Portfolio Theory](https://en.wikipedia.org/wiki/Modern_portfolio_theory)

---

## 🤝 Contributing

If you improve the ICT strategy or add new features:

1. Fork the repository
2. Create a feature branch
3. Add tests
4. Submit a pull request

---

## 📞 Support

For issues or questions:
- Open an issue on GitHub
- Check existing documentation
- Review the code comments

**Happy Trading! 📈**
