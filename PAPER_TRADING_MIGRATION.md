# Paper Trading Mode Migration Notes

## Summary of Changes

The bot now uses `paper_account.json` as the single source of truth for equity tracking when paper trading is enabled. The old `performance.json` file is no longer updated in paper trading mode.

---

## What Changed

### Before (Signal-Only Mode)
- **Equity tracked in**: `data/performance.json`
- **Updated by**: `RiskManager.record_trade()`
- **P&L calculation**: Simulated from signal TP/SL hits
- **No execution costs**: Fees, slippage, funding not accounted for

### After (Paper Trading Mode)
- **Equity tracked in**: `data/paper_account.json`
- **Updated by**: `PaperAccount` class (real execution simulation)
- **P&L calculation**: From actual simulated order fills with live prices
- **Execution costs**: Realistic fees (0.02-0.06%), slippage (0.03-0.15%), funding rates

---

## File Usage by Mode

### When `PAPER_TRADING_ENABLED=true`:
| File | Purpose | Updated By |
|------|---------|------------|
| `paper_account.json` | ✅ **Equity tracking** (source of truth) | `PaperAccount` |
| `performance.json` | ❌ **Disabled** (not updated) | - |
| `signals_active.json` | ✅ Active signals + execution data | `SignalTracker` + `PaperEngine` |
| `signals_history.json` | ✅ Completed signals with real P&L | `SignalTracker` |
| `trade_history.json` | ✅ Trade log for analytics | `PerformanceLogger` |

### When `PAPER_TRADING_ENABLED=false` (Signal-Only):
| File | Purpose | Updated By |
|------|---------|------------|
| `paper_account.json` | ❌ Not created | - |
| `performance.json` | ✅ **Equity tracking** (source of truth) | `RiskManager` |
| `signals_active.json` | ✅ Active signals (no execution data) | `SignalTracker` |
| `signals_history.json` | ✅ Completed signals with simulated P&L | `SignalTracker` |
| `trade_history.json` | ✅ Trade log for analytics | `PerformanceLogger` |

---

## Code Changes

### `RiskManager.__init__()` 
Now accepts `paper_account` parameter:
```python
def __init__(self, performance_logger=None, discord=None, paper_account=None):
    self.paper_account = paper_account
    self.paper_trading_mode = Config.PAPER_TRADING_ENABLED
```

### `RiskManager._load_state()`
Loads equity from paper account in paper trading mode:
```python
if self.paper_trading_mode and self.paper_account:
    self.equity = self.paper_account.get_equity()
else:
    self.equity = state.get('equity', Config.INITIAL_CAPITAL)
```

### `RiskManager._save_state()`
Skips updating `performance.json` in paper trading mode:
```python
if self.paper_trading_mode:
    logger.debug("Paper trading mode: skipping performance.json update")
    return
```

### `RiskManager.record_trade()`
Gets equity from paper account instead of self-tracking:
```python
if not self.paper_trading_mode:
    self.equity += pnl
else:
    if self.paper_account:
        self.equity = self.paper_account.get_equity()
```

### `main.py`
Paper account initialized before risk manager:
```python
# Initialize paper trading first
if self.paper_trading_enabled:
    self.paper_account = PaperAccount(...)
else:
    self.paper_account = None

# Pass paper_account to risk manager
self.risk_manager = RiskManager(
    performance_logger=self.performance_logger,
    discord=self.discord,
    paper_account=self.paper_account  # NEW
)
```

---

## Data Migration

### No Migration Needed!
- Old `performance.json` still exists but won't be updated
- When switching back to signal-only mode, it will resume using `performance.json`
- Paper trading starts fresh with `INITIAL_CAPITAL` from config

### If You Want to Preserve Old Equity:
Not recommended, but if you want to start paper trading with your current simulated equity:

1. Check current equity:
```bash
# View current performance.json equity
cat data/performance.json | grep "equity"
```

2. Update paper account manually:
```bash
# Edit data/paper_account.json
# Set "balance" and "initial_capital" to your desired starting value
```

⚠️ **Note**: This defeats the purpose of realistic simulation. Better to start fresh.

---

## Backwards Compatibility

### Switching Between Modes

**Paper Trading → Signal-Only:**
```bash
# Set to false in .env
PAPER_TRADING_ENABLED=false

# Restart bot
python -m src.main
```
- Bot loads equity from `performance.json` (last saved value)
- `paper_account.json` ignored
- No data loss

**Signal-Only → Paper Trading:**
```bash
# Set to true in .env
PAPER_TRADING_ENABLED=true

# Restart bot
python -m src.main
```
- Bot creates fresh `paper_account.json` with `INITIAL_CAPITAL`
- `performance.json` preserved but not updated
- Old simulated equity not carried over (intentional)

---

## Risk Management Impact

### What Still Uses `performance.json`:
- ❌ Nothing in paper trading mode
- ✅ Consecutive loss counter (stored but not saved in paper mode)
- ✅ Cooldown timers (stored but not saved in paper mode)
- ✅ Daily/weekly reset dates (stored but not saved in paper mode)

### What's Tracked Separately:
In paper trading mode, risk management state is kept in memory but not persisted to `performance.json`. This is intentional:
- Equity comes from `paper_account.json` (more accurate)
- Risk limits (cooldowns, loss counters) still function
- On bot restart, loads equity from paper account

---

## Monitoring

### Check Current Mode:
```bash
# Bot logs on startup
python -m src.main

# Look for:
# "📊 Paper Trading Engine: ENABLED"  (paper trading mode)
# OR
# "📝 Paper Trading Engine: DISABLED (signal-only mode)"
```

### Check Active Equity Source:
```bash
# If paper trading enabled
python check_paper_trading.py
# Shows: Current Balance, Equity, P&L

# If signal-only mode
cat data/performance.json
# Shows: "equity": 2000.0
```

### Both Modes Analytics:
```bash
python analytics.py
# In paper trading mode: Shows dedicated section "📊 PAPER TRADING PERFORMANCE"
# In signal-only mode: Shows regular analytics without paper section
```

---

## Troubleshooting

### "Equity not updating"
**Problem**: In paper trading mode, `performance.json` equity stays the same

**Solution**: This is correct! Equity now in `paper_account.json`:
```bash
cat data/paper_account.json | grep balance
```

### "Started paper trading but equity = $2000"
**Problem**: Expected to continue from previous simulated equity

**Solution**: Intended behavior. Paper trading starts fresh from `INITIAL_CAPITAL`. This ensures:
- Clean slate for realistic simulation
- Proper fee/slippage accounting from start
- No contamination from simulated signal P&L

If you absolutely need to preserve equity, manually set `balance` and `initial_capital` in `paper_account.json` before first run.

### "Risk limits not working"
**Problem**: Bot not respecting consecutive losses / weekly limits

**Solution**: Risk management still functions, just not saved to `performance.json` in paper mode. Check logs for:
- "⏸️ Cooldown active"
- "🛑 Weekly loss limit hit"

Equity for risk calculations comes from `paper_account.get_equity()`.

---

## Summary

✅ **Paper trading mode**: Uses `paper_account.json` exclusively for equity
✅ **Signal-only mode**: Uses `performance.json` as before (unchanged)
✅ **No data loss**: Old files preserved when switching modes
✅ **Risk management**: Works in both modes (equity source changes)
✅ **Analytics**: Automatically detects mode and shows relevant data

The change makes paper trading **more accurate** by tracking real execution costs that were previously ignored.
