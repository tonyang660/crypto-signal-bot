# Backtesting Framework

Professional-grade backtesting system for the signal bot following best practices from the 12-principle guide.

## 📁 Structure

```
backtest/
├── config.py           # Backtest configuration
├── data_fetcher.py     # Historical data fetcher with validation
├── engine.py           # Core backtest engine (candle-by-candle)
├── run_backtest.py     # Main backtest runner
├── walk_forward.py     # Walk-forward testing
├── data/               # Cached historical data
└── results/            # Backtest results (JSON + CSV)
```

## 🚀 Quick Start

### 1. Run Full Backtest

```bash
python backtest/run_backtest.py
```

This will:
- Fetch 1-2 years of historical data from Bitget
- Run candle-by-candle simulation using your bot's exact logic
- Apply realistic slippage and fees
- Generate comprehensive metrics
- Save results to `backtest/results/`

### 2. Run Walk-Forward Test

```bash
python backtest/walk_forward.py
```

This validates the strategy on **unseen data**:
- Splits data 70% train / 30% test
- Runs backtest on train period
- Tests on unseen test period
- Checks for overfitting

**Critical**: If test results are much worse than train, the strategy is overfit!

## ⚙️ Configuration

Edit `backtest/config.py` to customize:

```python
# Date range
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)

# Symbols to test
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

# Capital
INITIAL_CAPITAL = 10000

# Execution
CONSERVATIVE_MODE = True  # If TP & SL both hit, assume SL
SLIPPAGE_PERCENT = 0.05   # 5 basis points
TAKER_FEE = 0.055         # Bitget taker fee
```

## 📊 Understanding Results

### Key Metrics

| Metric | What It Means | Good Target |
|--------|---------------|-------------|
| **Total Return** | Overall profit/loss % | >20% per year |
| **Win Rate** | % of winning trades | >50% (but not everything) |
| **Profit Factor** | Gross profit / Gross loss | >1.5 |
| **Expectancy** | Average $ per trade | >0 (positive) |
| **Sharpe Ratio** | Risk-adjusted returns | >1.0 |
| **Max Drawdown** | Worst peak-to-trough % | <20% |

### What to Look For

✅ **Good Signs:**
- Positive expectancy (makes money on average)
- Profit factor > 1.5
- Test results similar to train results
- Max drawdown manageable (<20%)
- Win rate 45-65% (too high = overfit)

🚨 **Red Flags:**
- Negative expectancy
- Test results much worse than train
- Profit factor < 1.0
- Max drawdown >30%
- Only works on specific symbols/timeframes

## 🔬 How It Works

### Conservative Execution Rules

The backtest follows **conservative assumptions** to avoid inflated results:

1. **Entry**: Only on candle close (no intra-candle entries)
2. **Slippage**: Applied to all market orders
3. **Fees**: Full taker fees on entry + exits
4. **TP/SL Same Candle**: If both hit, assume SL hit first
5. **No Future Data**: Only uses data available at that moment
6. **Stop Slippage**: Extra slippage on stop losses (0.1%)

### Candle-by-Candle Simulation

The engine replays history **one candle at a time**:

```
For each candle:
  1. Update active positions (check TP/SL)
  2. Check if trading allowed (cooldown, weekly limits)
  3. Scan for new signals using live bot logic
  4. Record equity
```

This ensures **no look-ahead bias** - the bot only knows what it would know in live trading.

### Using Live Bot Logic

The backtest imports and uses your **actual strategy code**:

```python
from src.strategy.entry_logic import EntryLogic
from src.strategy.signal_scorer import SignalScorer
from src.strategy.stop_tp_calculator import StopTPCalculator
```

This guarantees backtest matches live behavior.

## 📈 Analysis Tools

### View Results

Results are saved as:
- `backtest_TIMESTAMP.json` - Full results with equity curve
- `backtest_TIMESTAMP.csv` - Individual trades for Excel analysis

### Analyze by Regime

Results include breakdown by:
- Market regime (trending, choppy, high_vol, low_vol)
- Symbol
- Exit reason (completed, stopped, backtest_end)

Example:
```
PERFORMANCE BY REGIME:
  trending           42 trades | $ +1,245.67 | Avg: $  +29.66
  high_volatility    31 trades | $   -234.11 | Avg: $   -7.55
  choppy             18 trades | $   -156.23 | Avg: $   -8.68
```

## 🎯 Walk-Forward Testing

Walk-forward testing **prevents overfitting** by testing on data the bot has never "seen."

### How It Works

1. **Train Period** (70% of data): Bot runs backtest
2. **Test Period** (30% of data): Bot tested on unseen future data
3. **Compare**: If test << train, strategy is overfit

### Interpreting Results

```
Train: 2024-01-01 to 2024-09-15  →  +34% return, 58% win rate
Test:  2024-09-16 to 2024-12-31  →  +29% return, 54% win rate
```

✅ **This is good** - test results are similar to train

```
Train: 2024-01-01 to 2024-09-15  →  +47% return, 64% win rate
Test:  2024-09-16 to 2024-12-31  →  -12% return, 38% win rate
```

🚨 **This is bad** - major degradation = overfitting or regime change

## 🔧 Troubleshooting

### "No data available for backtesting"

- Check date range in `config.py`
- Ensure symbols exist on Bitget
- Check internet connection (data fetch failed)

### "Not enough margin for position"

- Reduce number of symbols
- Increase initial capital
- Check position sizing logic

### Backtest too slow

- Reduce date range (test shorter period first)
- Use fewer symbols
- Cache will speed up subsequent runs

## 📝 Best Practices

### Before Running Backtest

1. ✅ Ensure bot logic is finalized
2. ✅ Test on small date range first (1-2 months)
3. ✅ Check data quality (no major gaps)

### When Analyzing Results

1. ✅ Don't just look at total return
2. ✅ Check **all** metrics (drawdown, Sharpe, expectancy)
3. ✅ Analyze by regime - does it work in all conditions?
4. ✅ Run walk-forward test to check overfitting
5. ✅ Compare multiple symbols

### Red Flags to Watch

🚨 **Too good to be true** (>100% yearly return, >80% win rate)
🚨 **Test results collapse** compared to train
🚨 **Only works on one symbol/timeframe**
🚨 **Only works in trending markets**
🚨 **Max drawdown > 30%**

## 🎓 What Good Results Look Like

Based on professional trading standards:

```
Total Return:       +28% per year
Win Rate:           53%
Profit Factor:      1.8
Expectancy:         $12 per trade
Sharpe Ratio:       1.4
Max Drawdown:       -14%
```

This shows:
- Consistent profitability
- Reasonable win rate (not overfit)
- Good risk-adjusted returns
- Manageable drawdowns

## 🔄 Continuous Improvement

After backtesting:

1. **Identify weaknesses** (which regimes lose money?)
2. **Improve strategy** (better filters, adjusted TPs)
3. **Re-backtest** to validate improvements
4. **Walk-forward test** to check overfitting
5. **Repeat** until results are robust

## ⚠️ Important Notes

### Backtest ≠ Guaranteed Future Performance

- Markets change
- Past performance doesn't guarantee future results
- Use backtest to **validate logic**, not predict exact returns

### Use Conservative Assumptions

The backtest already uses conservative assumptions, but consider:
- API downtime (can't always enter/exit)
- Extreme volatility (slippage can be worse)
- Black swan events (not in historical data)

### Start Small in Live Trading

Even with good backtest:
- Start with minimum position sizes
- Monitor first 20-30 live trades closely
- Compare live vs backtest performance
- Adjust if needed

---

**Remember**: The backtest's job is to **find problems** before live trading, not to make you feel good about the strategy. Take issues seriously!
