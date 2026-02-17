# Dynamic Risk Management Implementation

## Summary

Successfully implemented dynamic risk management where risk parameters automatically adjust based on account equity. This provides better capital preservation as the account grows.

## Dynamic Risk Tiers

| Equity Range | Risk/Trade | Daily Loss Limit | Weekly Loss Limit |
|-------------|-----------|-----------------|-------------------|
| <$3,000 | 1.0% | 2.0% | 6.0% |
| $3,000-$5,000 | 0.8% | 1.6% | 5.0% |
| $5,000-$7,000 | 0.7% | 1.4% | 4.5% |
| $7,000-$10,000 | 0.6% | 1.2% | 4.2% |
| $10,000-$20,000 | 0.5% | 1.0% | 3.9% |
| $20,000+ | 0.4% | 1.0% | 3.6% |

## Benefits

1. **Aggressive Growth** when small (<$3k) - 1% risk per trade
2. **Conservative Protection** as capital grows - reduces to 0.4% at $20k+
3. **Automatic Adjustment** - no manual configuration needed
4. **Same Logic** everywhere - backtest and live bot use identical calculations

## Implementation Changes

### 1. Config Class (`src/core/config.py`)
- Added `get_dynamic_risk_params(equity)` static method
- Returns risk parameters based on current equity tier
- Baseline constants remain for backward compatibility

### 2. Risk Manager (`src/risk/risk_manager.py`)
- Updated `can_trade()` to use dynamic max_daily_loss and max_weekly_loss
- Updated `get_risk_stats()` to include current dynamic parameters
- All risk limits now adjust automatically with equity

### 3. Position Sizer (`src/risk/position_sizer.py`)
- Updated `calculate_position_size()` to use dynamic risk_per_trade
- Position sizes automatically scale with equity tier
- Logging now shows current dynamic risk percentage

### 4. Backtest Config (`backtest/config.py`)
- Inherits from live Config - no changes needed
- Automatically uses same dynamic risk logic
- Ensures backtest results reflect actual trading behavior

## Consistency Verification

### ✅ Entry Logic
Both backtest and main use identical entry logic:
- `EntryLogic.check_long_entry(data)`
- `EntryLogic.check_short_entry(data)`
- Score override at 85+ points

### ✅ Signal Scoring
Both use the same scoring system:
- `SignalScorer.calculate_score_with_breakdown(data, direction, symbol)`
- Same scoring components and weights
- Same thresholds (70 normal, 85 drawdown)

### ✅ Stop Loss Calculation
Both use identical stop loss logic:
- `StopTPCalculator.calculate_stop_loss(data, direction, entry_price)`
- ATR_STOP_MULTIPLIER = 2.5 (from Config)

### ✅ Take Profit Calculation
Both use identical TP logic:
- `StopTPCalculator.calculate_take_profits(entry_price, stop_loss, direction, regime)`
- Regime-adjusted ratios (trending vs choppy)
- TP1: 1.5R, TP2: 2.5R, TP3: 3.5R

### ✅ Position Sizing
Both use identical position sizing:
- `PositionSizer.calculate_position_size(equity, entry_price, stop_loss, symbol, available_margin)`
- Dynamic leverage based on stop tightness
- BTC regime adjustments applied identically

### ✅ BTC Regime Adjustments
Both apply the same BTC regime logic:
- Position size multiplier when BTC is choppy
- Threshold adjustments based on BTC trend
- Same detection and response logic

## Example Scenarios

### Scenario 1: Starting Account ($2,000)
- Risk per trade: 1.0% = $20
- Daily loss limit: 2.0% = $40
- Weekly loss limit: 6.0% = $120
- **Aggressive** growth phase

### Scenario 2: Growing Account ($5,500)
- Risk per trade: 0.7% = $38.50
- Daily loss limit: 1.4% = $77
- Weekly loss limit: 4.5% = $247.50
- **Transitioning** to conservative

### Scenario 3: Established Account ($15,000)
- Risk per trade: 0.5% = $75
- Daily loss limit: 1.0% = $150
- Weekly loss limit: 3.9% = $585
- **Conservative** capital preservation

### Scenario 4: Large Account ($25,000)
- Risk per trade: 0.4% = $100
- Daily loss limit: 1.0% = $250
- Weekly loss limit: 3.6% = $900
- **Maximum** capital preservation

## Testing Recommendations

1. **Run Backtest** with dynamic risk to verify performance across equity tiers
2. **Monitor Logs** to confirm dynamic parameters are being applied
3. **Check Risk Stats** in Discord notifications to see current tier
4. **Verify Transitions** when equity crosses tier boundaries

## Files Modified

1. `src/core/config.py` - Added dynamic risk calculation
2. `src/risk/risk_manager.py` - Uses dynamic parameters
3. `src/risk/position_sizer.py` - Applies dynamic risk per trade
4. No changes needed to `backtest/config.py` (inherits automatically)

## Backward Compatibility

- Baseline config values remain unchanged
- .env file doesn't need updates (baseline only)
- Existing logic continues to work
- Dynamic calculation happens transparently

## Notes

- Risk parameters update **in real-time** as equity changes
- No manual intervention needed
- Both wins and losses trigger parameter updates
- Backtest uses same logic for accurate future projection
