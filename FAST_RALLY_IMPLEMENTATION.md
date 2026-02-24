# Fast Rally Detection Implementation

## Overview
Enhanced the signal scoring system to catch fast rallies (5-10% moves in 1-2 days) by detecting explosive momentum on PRIMARY (15M) timeframe when HTF (4H) is still neutral.

## Problem Solved
- **Previous Issue:** System missed fast rallies because HTF (4H) EMAs lagged behind explosive moves
- **Root Cause:** 4H timeframe needs 12+ bars (2+ days) for EMAs to align, by which time fast rallies were half over
- **Solution:** Detect explosive momentum on PRIMARY (15M) and award HTF partial credit when criteria met

---

## Implementation Details

### 1. New Helper Methods (signal_scorer.py)

#### `detect_price_velocity(df, lookback_bars=16)`
- **Purpose:** Measure rate of change over recent period
- **Default:** 16 bars = 4 hours on 15M timeframe
- **Returns:** Price change percentage (e.g., 0.05 = 5% move)
- **Usage:** Identify explosive price movements

#### `detect_strong_primary_trend(primary_df, direction)`
- **Purpose:** Validate PRIMARY (15M) shows strong trending characteristics
- **Criteria:**
  - PRIMARY trend must match direction (bullish for long, bearish for short)
  - MACD must show acceleration (3 consecutive bars of increasing/decreasing momentum)
  - Bonus: Recent Break of Structure (within 10 bars)
- **Returns:** `(is_strong: bool, reason: str)`

---

### 2. Enhanced HTF Scoring Logic

#### **For LONG Signals:**

**When HTF = Neutral:**
```python
velocity = detect_price_velocity(primary_df, lookback_bars=16)  # 4 hours
is_strong_primary = detect_strong_primary_trend(primary_df, 'long')

# Fast Rally Detection:
if velocity > 0.03 and is_strong_primary:
    # >5% in 4 hours → 20 points
    # 3-5% in 4 hours → 18 points
    # Replaces standard 8 points for neutral HTF
```

**Criteria:**
- Price velocity > 3% in 4 hours (PRIMARY timeframe)
- PRIMARY trend = bullish
- MACD accelerating upward (hist[-1] > hist[-2] > hist[-3])
- MACD histogram > 0

**Scoring:**
- Normal HTF neutral: **8 points**
- Fast rally detected (3-5% in 4h): **18 points** (↑10 points)
- Fast rally detected (>5% in 4h): **20 points** (↑12 points)

#### **For SHORT Signals:**

**When HTF = Neutral:**
```python
velocity = detect_price_velocity(primary_df, lookback_bars=16)
is_strong_primary = detect_strong_primary_trend(primary_df, 'short')

# Fast Correction Detection:
if velocity < -0.03 and is_strong_primary:
    # <-5% in 4 hours → 20 points
    # -3% to -5% in 4 hours → 18 points
```

**Criteria:**
- Price velocity < -3% in 4 hours
- PRIMARY trend = bearish
- MACD accelerating downward
- MACD histogram < 0

**Scoring:**
- Normal HTF neutral: **8 points**
- Fast correction detected (-3% to -5% in 4h): **18 points**
- Fast correction detected (<-5% in 4h): **20 points**

---

### 3. Enhanced Entry Logic

#### **Long Entry (entry_logic.py):**

**Previous:** HTF must be bullish (hard requirement)

**Updated:**
```python
if htf_trend == 'bearish':
    # Reject - never go long in bearish HTF
    
elif htf_trend == 'neutral':
    # Allow IF fast rally detected
    if velocity > 0.03 and is_strong_primary:
        # Proceed with entry checks
    else:
        # Reject - no fast rally confirmation
        
elif htf_trend == 'bullish':
    # Proceed with entry checks (existing logic)
```

**Key Change:** HTF neutral now allowed IF explosive PRIMARY momentum detected

#### **Short Entry:**
Same logic for shorts - allow HTF neutral IF explosive downward momentum detected (velocity < -3%)

---

## Scoring Impact Examples

### Example 1: Fast Rally (7% in 4 hours from consolidation)

**Before Implementation:**
```
HTF Alignment:   8/25  (neutral)
Momentum:       20/20  (accelerating)
Entry Location: 20/20  (near EMA)
BOS:            10/13  (recent break)
RSI:            12/12  (optimal)
Volatility:     10/10  (ideal)
Volume:          8/8   (strong)
TOTAL:          88/100 (but entry rejected - HTF not bullish)
```

**After Implementation:**
```
HTF Alignment:  20/25  (FAST RALLY: +7.0% in 4h, accelerating MACD)
Momentum:       20/20  (accelerating)
Entry Location: 20/20  (near EMA)
BOS:            10/13  (recent break)
RSI:            12/12  (optimal)
Volatility:     10/10  (ideal)
Volume:          8/8   (strong)
TOTAL:         100/100 ✅ Entry allowed (fast rally override)
```

**Gain:** +12 points, entry now valid

---

### Example 2: Slow Rally (2% in 4 hours, no acceleration)

**Before Implementation:**
```
HTF Alignment:   8/25  (neutral)
Entry rejected
```

**After Implementation:**
```
HTF Alignment:   8/25  (neutral, velocity: +2.0% - no fast rally)
Entry still rejected ✅ Correctly filtered
```

**No change** - system correctly identifies this as choppy, not trending

---

## Thresholds & Rationale

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| **Price Velocity** | ±3% in 4 hours | Distinguishes trending from choppy |
| **Lookback Period** | 16 bars (4 hours on 15M) | Balances recency vs noise |
| **MACD Acceleration** | 3 consecutive bars | Confirms sustained momentum |
| **HTF Points (Fast Rally)** | 18-20 points | Compensates for lagging HTF |
| **BOS Bonus** | Within 10 bars | Recent structure break = very strong signal |

---

## What This Does NOT Change

✅ **Preserved Conservative Nature:**
- HTF opposing direction still blocks entry (never long in bearish HTF)
- All other entry checks remain (volatility, momentum strength, entry location)
- Minimum score thresholds unchanged
- Risk management unchanged

✅ **Filters Choppy Markets:**
- 2% daily oscillations: velocity < 3% → rejected ✅
- Range-bound movement: no MACD acceleration → rejected ✅
- Weak momentum: fails strength checks → rejected ✅

---

## Expected Behavior Changes

### **Catches Now (Previously Missed):**
- ✅ 5-10% rallies in 1-2 days from consolidation
- ✅ Explosive breakouts with strong momentum
- ✅ Fast corrections that start before HTF turns bearish

### **Still Filters (Correctly):**
- ❌ Choppy 2-3% daily noise
- ❌ Weak rallies without acceleration
- ❌ Counter-trend moves (HTF opposing)
- ❌ Low volatility grinding

---

## Monitoring & Validation

**Look for in logs:**
```
FAST RALLY: +5.3% in 4h, Strong BOS + accelerating MACD (BOS 6 bars ago)
Fast rally override: HTF neutral but velocity +5.3% in 4h, Accelerating MACD + PRIMARY trend aligned
```

**Success Metrics:**
1. Catch rate for 5-10% rallies improves
2. Signal quality scores for fast rallies: 80-95+ (up from 60-75)
3. Entry acceptance rate for explosive moves increases
4. False positive rate remains low (choppy markets still filtered)

---

## Technical Notes

- **Circular Import Avoided:** Entry logic imports SignalScorer dynamically (inside function)
- **Backwards Compatible:** Existing signals with HTF alignment remain unaffected
- **Conservative Override:** Fast rally detection is strict (requires multiple confirmations)
- **Symmetrical Logic:** Same approach for longs and shorts

---

## Summary

**Philosophy:** "Strong momentum on lower timeframes can itself indicate a trending market, even before HTF catches up"

**Result:** System now catches legitimate fast rallies (5-10% in 1-2 days) while maintaining conservative trend-following nature and filtering choppy markets.

**Key Insight:** The difference between:
- ❌ 2% daily noise (chop) → filtered
- ✅ 5-10% directional move (fast trend) → caught

This implementation resolves the asymmetry where corrections were caught better than rallies, making the system more balanced for both directions of explosive moves.
