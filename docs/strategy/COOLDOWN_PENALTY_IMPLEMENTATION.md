# Cooldown System Enhancement Implementation

## Summary

Enhanced the cooldown system with threshold penalties that make re-entry more difficult after triggering risk limits.

## Changes Implemented

### 1. Cooldown Duration Updates
- **Consecutive Loss Cooldown**: 4 hours (unchanged)
- **Weekly Loss Cooldown**: **Changed from 24 hours to 12 hours**

### 2. Threshold Penalty System

#### When Penalties Apply:
1. **3 Consecutive Losses**: +5 points to signal threshold
2. **Weekly Loss Limit Hit**: +5 points to signal threshold
3. **Both Active**: +10 points total (penalties stack)

#### How It Works:
- Base threshold: 70 (normal) or 85 (drawdown)
- BTC regime adjustments: -5 to +5
- **NEW**: Cooldown penalties: +5 per active cooldown
- Final threshold can be 70-90+ depending on conditions

#### Penalty Lifecycle:
- **Activated**: When cooldown is triggered
- **Active**: While cooldown is in effect
- **Cleared**: When cooldown expires OR on daily/weekly reset

### 3. Code Changes

#### RiskManager (`src/risk/risk_manager.py`)
```python
# New attributes
self.daily_threshold_penalty = 0  # +5 when consecutive loss cooldown active
self.weekly_threshold_penalty = 0  # +5 when weekly loss cooldown active

# New method
def get_threshold_adjustment(self) -> int:
    """Get total threshold adjustment from active penalties"""
    return self.daily_threshold_penalty + self.weekly_threshold_penalty
```

**Updated Methods:**
- `__init__()`: Added threshold penalty tracking
- `can_trade()`: Shows penalty in cooldown messages, clears when expired
- `record_trade()`: Sets daily penalty when consecutive losses hit
- `get_risk_stats()`: Includes penalty information
- `_save_state()` / `_load_state()`: Persists penalties
- `_check_daily_reset()`: Clears daily penalty on new day
- `_check_weekly_reset()`: Clears weekly penalty on new week

#### Main Algorithm (`src/main.py`)
```python
# Apply cooldown penalty adjustment to threshold
cooldown_penalty = self.risk_manager.get_threshold_adjustment()
if cooldown_penalty > 0:
    threshold += cooldown_penalty
    logger.warning(f"{symbol}: Cooldown penalty active +{cooldown_penalty}pt | Adjusted threshold: {threshold}")
```

#### Backtest Engine (`backtest/engine.py`)
```python
# New attributes
self.daily_threshold_penalty = 0
self.weekly_threshold_penalty = 0

# Apply cooldown penalty in scan_for_signals
cooldown_penalty = self.daily_threshold_penalty + self.weekly_threshold_penalty
if cooldown_penalty > 0:
    threshold += cooldown_penalty
```

**Updated Methods:**
- `__init__()`: Added threshold penalty tracking
- `_close_position()`: Sets penalty when consecutive losses hit
- `_can_take_new_signal()`: Clears penalties when cooldowns expire
- `_check_daily_reset()`: Clears daily penalty on new day
- `_scan_for_signals()`: Applies penalty to threshold

## Example Scenarios

### Scenario 1: Normal Trading
- Base threshold: 70
- BTC adjustment: 0
- Cooldown penalty: 0
- **Final threshold: 70**

### Scenario 2: After 3 Consecutive Losses
- Base threshold: 70
- BTC adjustment: 0
- Cooldown penalty: +5 (daily)
- **Final threshold: 75**
- Cooldown: 4 hours
- More selective signal entry required

### Scenario 3: Weekly Loss Limit Hit
- Base threshold: 70
- BTC adjustment: 0
- Cooldown penalty: +5 (weekly)
- **Final threshold: 75**
- Cooldown: 12 hours
- More selective signal entry required

### Scenario 4: Both Penalties Active (Worst Case)
- Base threshold: 85 (drawdown state)  
- BTC adjustment: +5 (choppy BTC)
- Cooldown penalty: +10 (both)
- **Final threshold: 100** (impossible to trade)
- System effectively paused for quality reset

### Scenario 5: Penalty Expiration
- At 4-hour mark: Daily penalty cleared automatically
- At midnight: Daily penalty cleared on new day
- At Monday: Weekly penalty cleared on new week

## Benefits

1. **Progressive Risk Reduction**: Each setback makes system more selective
2. **Automatic Recovery**: Penalties clear when conditions improve
3. **Double Protection**: Both time cooldown AND quality threshold increase
4. **Adaptive Response**: Worse situation = stricter requirements
5. **Backtest Accuracy**: Same logic used in live and historical testing

## State Management

### Persisted in performance.json:
```json
{
  "cooldown_until": "2026-02-16T23:16:04",
  "daily_threshold_penalty": 5,
  "weekly_cooldown_until": "2026-02-17T07:16:04",
  "weekly_threshold_penalty": 5
}
```

### Risk Stats Output:
```python
{
  'daily_threshold_penalty': 5,
  'weekly_threshold_penalty': 0,
  'total_threshold_penalty': 5
}
```

## Testing

Created `test_cooldown_penalties.py` to verify:
- ✅ Daily penalty added after 3 consecutive losses
- ✅ Weekly penalty added when weekly limit hit
- ✅ Penalties stack correctly
- ✅ Penalties clear on cooldown expiry
- ✅ Penalties reset on new day/week
- ✅ `get_threshold_adjustment()` returns correct total

## Files Modified

1. `src/risk/risk_manager.py` - Core risk management logic
2. `src/main.py` - Live trading threshold application
3. `backtest/engine.py` - Backtest threshold application
4. `test_cooldown_penalties.py` - Verification tests (new)

## Backward Compatibility

- Existing `performance.json` files will work (penalties default to 0)
- No .env changes required
- Cooldown mechanics unchanged (just penalty addition)
- All existing logic preserved

## Impact

### When Cooldowns Are Active:
- **Without penalties** (before): Wait X hours, then resume normal trading
- **With penalties** (now): Wait X hours, then require higher quality signals

### Progressive Degradation:
1. Normal: 70pt threshold
2. One cooldown: 75pt threshold (+5)
3. Both cooldowns: 80pt threshold (+10)
4. Drawdown + both: 95pt threshold (+25 from base 85)

This creates natural pressure to let conditions stabilize before aggressive re-entry.
