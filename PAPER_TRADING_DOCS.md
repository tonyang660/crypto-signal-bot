# Paper Trading Implementation

## Overview

The signalbot now supports **self-hosted paper trading** execution. This simulates realistic order fills, tracks fees, slippage, funding rates, and position management using live BitGet market data—without risking real capital.

## 🎯 What It Does

### Signal-Only Mode (Default)
- Bot generates entry signals
- Calculates entry/SL/TP levels
- Tracks hypothetical performance
- Sends Discord notifications

### Paper Trading Mode (New!)
- Everything from signal-only mode, PLUS:
- **Places virtual limit orders** at signal entry price
- **Simulates order fills** based on real-time bid/ask data
- **Tracks fees** (BitGet: 0.02% maker, 0.06% taker)
- **Applies funding rates** every 8 hours (perpetual futures)
- **Calculates slippage** based on volatility and order type
- **Monitors positions** for TP/SL exits
- **Checks liquidation** prices with leverage
- **Saves state** to `data/paper_account.json`

## 🚀 Quick Start

### 1. Enable Paper Trading

Add to `.env`:
```bash
PAPER_TRADING_ENABLED=true
```

### 2. Run the Bot

```bash
python -m src.main
```

The bot will:
- Initialize a paper account with `INITIAL_CAPITAL` ($2000 default)
- Generate signals as usual
- Automatically place limit orders for quality signals
- Monitor positions and execute exits

### 3. Monitor Performance

**Check paper trading status:**
```bash
python check_paper_trading.py
```

**View detailed analytics:**
```bash
python analytics.py
```

**Watch Discord notifications:**
- 📊 Limit order placed
- ✅ Order filled (with slippage/fees)
- 🎯 TP1/TP2/TP3 hits
- 🛑 Stop loss hits
- 💀 Liquidations (if any)

## 📊 How It Works

### Order Execution Flow

1. **Signal Generated**
   - Bot finds quality setup (score ≥ threshold)
   - Calculates entry, SL, TP levels
   - Creates signal in `signals_active.json`

2. **Limit Order Placed**
   - Paper engine places virtual limit order at entry price
   - Order tracked in pending state
   - Discord notified

3. **Order Fill Check** (every 5 min scan)
   - Fetch current ticker: `bid`, `ask`, `last`
   - **Long limit buy** fills if `ask ≤ limit_price`
   - **Short limit sell** fills if `bid ≥ limit_price`
   - Apply maker fee (0.02%) if passive fill
   - Apply taker fee (0.06%) if crossed spread

4. **Position Opened**
   - Calculate liquidation price based on leverage
   - Track margin used
   - Set SL/TP as virtual orders
   - Update `paper_account.json`

5. **Exit Monitoring**
   - Check price vs SL/TP levels each scan
   - **Stop loss**: Market exit with 0.15% slippage (worst fill)
   - **Take profit**: Limit exit at exact TP price (maker fee)
   - Close partial positions (33% @ TP1, 33% @ TP2, 34% @ TP3)

6. **Position Closed**
   - Calculate realized P&L
   - Deduct fees and funding costs
   - Update balance
   - Move to `signals_history.json`

### Fee Structure (BitGet Perpetual Futures)

| Order Type | Fee Rate | When Applied |
|------------|----------|--------------|
| **Maker** | 0.02% | Limit orders that add liquidity |
| **Taker** | 0.06% | Market orders or aggressive limits |
| **Funding** | ~0.01% | Every 8 hours (00:00, 08:00, 16:00 UTC) |

### Slippage Simulation

```python
BASE_SLIPPAGE = 0.03%       # Normal volatility
ELEVATED_SLIPPAGE = 0.08%   # High volatility (ATR > 5%)
STOP_SLIPPAGE = 0.15%       # Stop loss exits (worst case)
```

Additional slippage added based on order book depth if position size is large.

### Leverage & Liquidation

- **Leverage**: 5-15× based on stop distance (calculated by `PositionSizer`)
- **Maintenance Margin**: ~0.5% for most pairs (0.4% for BTC)
- **Liquidation Formula**:
  - Long: `liq_price = entry * (1 - 1/leverage + maintenance_margin)`
  - Short: `liq_price = entry * (1 + 1/leverage - maintenance_margin)`

Example: 10× leverage long @ $45,000
- Liquidation: $40,950 (9% drop)

## 📁 File Structure

```
data/
├── paper_account.json       # Virtual account state
├── signals_active.json      # Active signals + execution data
└── signals_history.json     # Completed signals with real P&L

src/execution/
├── paper_engine.py          # Core execution simulator
├── paper_account.py         # Virtual balance tracker
└── margin_calculator.py     # Leverage/liquidation math
```

### `paper_account.json` Schema

```json
{
  "balance": 2000.0,
  "initial_capital": 2000.0,
  "total_realized_pnl": 0.0,
  "total_fees_paid": 0.0,
  "total_funding_costs": 0.0,
  "positions_count": 0,
  "trades_count": 0,
  "equity_curve": [
    {
      "timestamp": "2026-02-06T12:00:00",
      "equity": 2000.0,
      "balance": 2000.0,
      "unrealized_pnl": 0.0,
      "open_positions": 0
    }
  ],
  "last_updated": "2026-02-06T12:00:00"
}
```

### Signal Execution Fields

When paper trading is enabled, signals include:
```json
{
  "paper_trading": true,
  "execution_state": "position_open",
  "entry_order_id": "PAPER_BTCUSDT_long_1234567890_ENTRY",
  "filled_at": "2026-02-06T12:05:00",
  "fill_price": 45012.50,
  "entry_slippage": 0.0003,
  "fees_paid": 2.70,
  "funding_costs": 0.0,
  "liquidation_price": 40950.00,
  "margin_used": 450.00
}
```

## 🔧 Configuration

### Environment Variables

```bash
# Enable/disable paper trading
PAPER_TRADING_ENABLED=true          # Default: false

# Existing config (still applies)
INITIAL_CAPITAL=2000                # Virtual starting balance
RISK_PER_TRADE=0.01                 # 1% risk per trade
MAX_LEVERAGE=15.0                   # Max leverage allowed
```

### Advanced Settings (`src/core/config.py`)

```python
# Order timeout
LIMIT_ORDER_TIMEOUT_SCANS = 6      # Cancel after 30 mins (6 × 5min scans)

# Simulation toggles
SIMULATE_SLIPPAGE = True            # Apply slippage to fills
APPLY_FUNDING_RATES = True          # Deduct funding every 8h
FUNDING_INTERVAL_HOURS = 8          # BitGet schedule
```

## 📈 Analytics & Reporting

### Check Paper Trading Status

```bash
python check_paper_trading.py
```

Output:
```
================================================================================
📊 PAPER TRADING STATUS
================================================================================

💰 ACCOUNT SUMMARY
--------------------------------------------------------------------------------
Initial Capital:      $2,000.00
Current Balance:      $2,045.30
Current Equity:       $2,045.30
Total Return:         +$45.30 (+2.27%)

Realized P&L:         +$52.00
Fees Paid:            $5.20
Funding Costs:        $1.50
Net P&L:              +$45.30

📊 TRADING STATISTICS
--------------------------------------------------------------------------------
Total Positions Opened:  5
Total Trades Closed:     3
Average P&L per Trade:   +$15.10

📈 EQUITY CURVE
--------------------------------------------------------------------------------
Snapshots Recorded:      120
Latest Snapshot (2026-02-06T12:00:00):
  Equity:                $2,045.30
  Balance:               $2,045.30
  Unrealized P&L:        $0.00
  Open Positions:        0
```

### Analytics Integration

```bash
python analytics.py
```

New section: **📊 PAPER TRADING PERFORMANCE**
- Account return vs. initial capital
- Gross P&L vs. Net P&L (after fees/funding)
- Average execution costs per trade
- Slippage analysis
- Simulation vs. reality comparison

## 🎮 Usage Examples

### Test Locally (Continuous Mode)

```bash
# Enable paper trading
export PAPER_TRADING_ENABLED=true

# Run bot continuously
python -m src.main
```

Bot will scan every 5 minutes, simulating trades in real-time.

### GitHub Actions (Production)

1. **Add GitHub Secret**:
   - Go to repository Settings → Secrets
   - Add: `PAPER_TRADING_ENABLED=true`

2. **Workflow picks it up automatically**:
   - Bot runs every 5 minutes
   - State persists to S3 between runs
   - `paper_account.json` uploaded/downloaded like other state files

3. **Monitor via Discord**:
   - All execution notifications sent to webhook
   - See: order fills, TP/SL hits, P&L updates

## 🔄 Migration Path

### From Signal-Only → Paper Trading

1. Set `PAPER_TRADING_ENABLED=true`
2. Restart bot
3. Existing active signals continue tracking (signal-only)
4. New signals will use paper trading execution

### Paper Trading → Live Trading

⚠️ **Live trading not yet implemented**

When ready to go live:
1. Bot can be extended with real BitGet order execution
2. Same logic, just swap `PaperTradingEngine` with `LiveTradingEngine`
3. API keys need trading permissions (not just read-only)

## 🛡️ Safety Features

### Risk Management Still Active

Paper trading respects all existing limits:
- ✅ Max 1 signal per pair
- ✅ Max 1 BTC signal at a time
- ✅ Max 4 total active signals
- ✅ Correlation group limits (max 2 per group)
- ✅ Consecutive loss cooldown (3 losses → pause)
- ✅ Weekly loss limit (6% → 24h cooldown)
- ✅ Margin availability checks

### Position Safety

- **Liquidation monitoring**: Closes position if price hits liq level
- **Funding rate tracking**: Realistic costs for perpetual positions
- **Margin validation**: Won't open new position if insufficient margin

## 🐛 Troubleshooting

### Paper account not initializing

**Problem**: Bot starts but no `data/paper_account.json` created

**Solution**:
```bash
# Check config
echo $PAPER_TRADING_ENABLED  # Should be 'true'

# Verify data directory exists
ls -la data/

# Run bot with debug logging
LOG_LEVEL=DEBUG python -m src.main
```

### Orders not filling

**Symptom**: Limit orders placed but never fill

**Check**:
1. **Price movement**: Limit order only fills when market crosses price
   - Long entry @ $45000 needs `ask ≤ $45000`
   - Short entry @ $45000 needs `bid ≥ $45000`

2. **Timeout**: Orders cancel after 30 minutes (6 scans)
   - Check Discord for "⏰ Limit order timeout" message

3. **Market data**: Ensure BitGet API is responding
   ```bash
   # Check logs for ticker fetch errors
   tail -f logs/bot.log | grep ticker
   ```

### Fees seem high

**Expected**: Typical trade costs 0.08-0.10% (entry + exit fees)

Breakdown:
- Entry limit (maker): 0.02%
- Exit at TP (maker): 0.02%
- Exit at SL (taker): 0.06%
- Funding (8h): ~0.01%

For leveraged position (10×):
- $1000 position = $10,000 notional
- Entry fee: $10,000 × 0.0002 = $2.00
- Exit fee: $10,000 × 0.0002 = $2.00
- Total: $4.00 (0.4% of margin)

This is realistic for futures trading.

### Discord shows duplicate notifications

**Cause**: Bot running multiple instances simultaneously

**Fix**:
- Only run one instance at a time
- If using GitHub Actions + local, disable one
- Check for zombie processes: `ps aux | grep python`

## 📝 Future Enhancements

Planned features:
- [ ] More sophisticated limit order strategies (e.g., iceberg, TWAP)
- [ ] Partial fill simulation (order fills over multiple scans)
- [ ] Exchange-specific order book depth modeling
- [ ] Backtesting mode (run paper engine on historical data)
- [ ] Live trading mode (real BitGet order execution)
- [ ] Performance comparison: simulated vs. paper vs. live

## 💡 Tips

**Best Practices:**
1. **Run paper trading for 2-4 weeks** before considering live trading
2. **Monitor fee impact** - if fees > 30% of gross P&L, strategy may not scale
3. **Track slippage** - high average slippage indicates poor execution timing
4. **Compare to signal-only** - use `analytics.py` to see cost of execution
5. **Test with different capital** - change `INITIAL_CAPITAL` to see position sizing effects

**What to Watch:**
- Win rate should be similar to backtests (± 5%)
- Average slippage should be < 0.1%
- Fee impact should be < 20% of gross P&L
- No unexpected liquidations (indicates leverage too high)

## 🆘 Support

**Logs**: `logs/bot.log`
**State files**: `data/*.json`
**Discord**: Check webhook for notifications

Report issues with:
- Bot version / commit hash
- Config settings (PAPER_TRADING_ENABLED, etc.)
- Relevant log excerpts
- Signal that failed to execute
