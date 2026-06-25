import pandas as pd
from typing import Dict
from loguru import logger
from src.analysis.market_structure import MarketStructure

from src.analysis.regime_detector import RegimeDetector

class SignalScorer:
    """
    Calculates a signal quality score (0-100) based on a weighted breakdown of technical factors,
    adapting the scoring logic based on the detected market regime (Trend-Following vs. Mean-Reversion).
    """

    # --- Scoring Weights for Trend-Following ---
    TREND_WEIGHTS = {
        'htf_alignment': 25,
        'momentum': 20,
        'entry_location': 20,
        'break_of_structure': 15,
        'rsi_quality': 12,
        'volatility': 8,
    }

    # --- Scoring Weights for Mean-Reversion ---
    MEAN_REVERSION_WEIGHTS = {
        'range_confirmation': 20,
        'breakout_safety': 15,
        'reversal_pattern': 20,
        'entry_extremity': 20,
        'rsi_divergence': 15,
        'low_volatility': 10,
    }

    @staticmethod
    def calculate_score_with_breakdown(data: Dict[str, pd.DataFrame], direction: str, symbol: str, regime: str = None) -> tuple:
        """
        Routes to the appropriate scoring logic based on the market regime.
        """
        if regime is None:
            regime = RegimeDetector.detect_regime(data['primary'])

        if regime == 'Sideways':
            return SignalScorer._score_mean_reversion(data, direction, symbol)
        else:
            return SignalScorer._score_trend_following(data, direction, symbol)

    @staticmethod
    def _score_trend_following(data: Dict[str, pd.DataFrame], direction: str, symbol: str) -> tuple:
        """
        Calculates a trend-following signal score.
        """
        breakdown = {key: {'points': 0, 'max': value, 'details': ''} for key, value in SignalScorer.TREND_WEIGHTS.items()}
        
        htf_df = data['htf']
        primary_df = data['primary']
        entry_df = data['entry']

        # 1. HTF Trend Alignment
        htf_trend = MarketStructure.get_trend_direction(htf_df)
        price_vs_ema_dist = (htf_df['close'].iloc[-1] - htf_df['ema_slow'].iloc[-1]) / htf_df['ema_slow'].iloc[-1]
        
        if direction == 'long':
            if htf_trend == 'bullish':
                points = 25 if price_vs_ema_dist > 0.05 else (18 if price_vs_ema_dist > 0.02 else 12)
                details = f"Bullish, {price_vs_ema_dist*100:.1f}% above EMA200"
            elif htf_trend == 'neutral':
                points, details = SignalScorer._score_fast_rally(primary_df, direction)
            else:
                points, details = 0, f"Opposing HTF trend ({htf_trend})"
        else: # short
            if htf_trend == 'bearish':
                points = 25 if price_vs_ema_dist < -0.05 else (18 if price_vs_ema_dist < -0.02 else 12)
                details = f"Bearish, {abs(price_vs_ema_dist)*100:.1f}% below EMA200"
            elif htf_trend == 'neutral':
                points, details = SignalScorer._score_fast_rally(primary_df, direction)
            else:
                points, details = 0, f"Opposing HTF trend ({htf_trend})"
        breakdown['htf_alignment']['points'] = points
        breakdown['htf_alignment']['details'] = details

        # 2. Momentum Quality (MACD)
        macd_hist = primary_df['macd_hist'].tail(3).values
        if len(macd_hist) >= 3:
            is_accelerating = (macd_hist[-1] > macd_hist[-2] > macd_hist[-3] > 0) if direction == 'long' else (macd_hist[-1] < macd_hist[-2] < macd_hist[-3] < 0)
            is_increasing = (macd_hist[-1] > macd_hist[-2] > 0) if direction == 'long' else (macd_hist[-1] < macd_hist[-2] < 0)
            
            if is_accelerating:
                breakdown['momentum']['points'] = 20
                breakdown['momentum']['details'] = "Accelerating momentum"
            elif is_increasing:
                breakdown['momentum']['points'] = 14
                breakdown['momentum']['details'] = "Increasing momentum"
            elif (macd_hist[-1] > 0 and direction == 'long') or (macd_hist[-1] < 0 and direction == 'short'):
                breakdown['momentum']['points'] = 8
                breakdown['momentum']['details'] = "Positive but weak momentum"

        # 3. RSI Quality
        rsi = primary_df['rsi'].iloc[-1]
        is_bullish_context = htf_trend == 'bullish' or (htf_trend == 'neutral' and breakdown['htf_alignment']['points'] > 15)
        is_bearish_context = htf_trend == 'bearish' or (htf_trend == 'neutral' and breakdown['htf_alignment']['points'] > 15)

        if direction == 'long':
            points = 12 if 45 <= rsi <= 70 else (8 if 70 < rsi <= 80 else 4) if is_bullish_context else (12 if 30 <= rsi <= 50 else (8 if 50 < rsi <= 60 else 4))
        else: # short
            points = 12 if 30 <= rsi <= 55 else (8 if 20 <= rsi < 30 else 4) if is_bearish_context else (12 if 50 <= rsi <= 70 else (8 if 40 <= rsi < 50 else 4))
        breakdown['rsi_quality']['points'] = points
        breakdown['rsi_quality']['details'] = f"RSI at {rsi:.1f} in {'momentum' if (is_bullish_context or is_bearish_context) else 'reversal'} context"

        # 4. Entry Location
        dist_from_ema = abs(entry_df['close'].iloc[-1] - entry_df['ema_fast'].iloc[-1]) / primary_df['atr'].iloc[-1]
        points = 20 if dist_from_ema < 0.3 else (14 if dist_from_ema < 0.6 else (8 if dist_from_ema < 1.0 else 3))
        breakdown['entry_location']['points'] = points
        breakdown['entry_location']['details'] = f"{dist_from_ema:.2f} ATR from EMA21"

        # 5. Break of Structure
        try:
            bos_detected, bars_ago, _ = MarketStructure.detect_break_of_structure(primary_df, direction)
            points, details = MarketStructure.get_bos_quality_score(bos_detected, bars_ago, max_points=15)
            breakdown['break_of_structure']['points'] = points
            breakdown['break_of_structure']['details'] = details
        except Exception as e:
            breakdown['break_of_structure']['details'] = f"BOS detection error: {e}"

        # 6. Volatility Suitability
        atr_ratio = primary_df['atr'].iloc[-1] / primary_df['atr_sma'].iloc[-1]
        points, details = (8, f"Ideal volatility ({atr_ratio:.2f}x avg)") if 1.0 <= atr_ratio <= 1.5 else ((5, f"Acceptable volatility ({atr_ratio:.2f}x avg)") if 0.8 <= atr_ratio < 1.8 else (0, f"Poor volatility ({atr_ratio:.2f}x avg)"))
        breakdown['volatility']['points'] = points
        breakdown['volatility']['details'] = details

        total_score = sum(b['points'] for b in breakdown.values())
        
        # Log the detailed breakdown
        log_message = f"{symbol} {direction.upper()} signal score breakdown (Trend-Following):\n"
        for key, value in breakdown.items():
            log_message += f"  - {key.replace('_', ' ').title():<20}: {value['points']:>2}/{value['max']} - {value['details']}\n"
        log_message += f"  TOTAL SCORE: {total_score}/100"
        logger.info(log_message)

        return total_score, breakdown

    @staticmethod
    def _score_mean_reversion(data: Dict[str, pd.DataFrame], direction: str, symbol: str) -> tuple:
        """
        Calculates a mean-reversion signal score.
        """
        breakdown = {key: {'points': 0, 'max': value, 'details': ''} for key, value in SignalScorer.MEAN_REVERSION_WEIGHTS.items()}
        primary_df = data['primary']
        entry_df = data['entry']
        
        range_info = MarketStructure.analyze_mean_reversion_range(primary_df)

        # 1. Range Confirmation (Is the market truly sideways?)
        regime = RegimeDetector.detect_regime(primary_df)
        if regime == 'Sideways':
            breakdown['range_confirmation']['points'] = 20
            breakdown['range_confirmation']['details'] = "Confirmed sideways market"
        else:
            breakdown['range_confirmation']['points'] = 0
            breakdown['range_confirmation']['details'] = f"Market is not sideways ({regime})"

        # 2. Breakout Safety (only score contained, low-expansion ranges)
        if range_info.get('valid'):
            breakdown['breakout_safety']['points'] = 15
            breakdown['breakout_safety']['details'] = (
                f"Contained range ({range_info.get('range_width_atr', 0):.1f} ATR wide, "
                f"ATR {range_info.get('atr_ratio', 0):.2f}x avg)"
            )
        else:
            breakdown['breakout_safety']['points'] = 0
            breakdown['breakout_safety']['details'] = range_info.get('reason', 'Range not safe')

        # 3. Reversal Pattern (e.g., MACD turning)
        macd_hist_entry = entry_df['macd_hist'].iloc[-1]
        macd_hist_prev_entry = entry_df['macd_hist'].iloc[-2]
        if (direction == 'long' and macd_hist_entry > macd_hist_prev_entry) or \
           (direction == 'short' and macd_hist_entry < macd_hist_prev_entry):
            breakdown['reversal_pattern']['points'] = 20
            breakdown['reversal_pattern']['details'] = "5m MACD confirming reversal"
        else:
            breakdown['reversal_pattern']['points'] = 8
            breakdown['reversal_pattern']['details'] = "5m MACD not yet confirming"

        # 4. Entry Extremity (How close is the entry to the local range edge?)
        range_position = range_info.get('position')
        if range_position is not None:
            if direction == 'long':
                edge_score = (0.5 - range_position) / 0.5
                details = f"Entry at {range_position*100:.0f}% of local range (0%=support)"
            else:
                edge_score = (range_position - 0.5) / 0.5
                details = f"Entry at {range_position*100:.0f}% of local range (100%=resistance)"

            breakdown['entry_extremity']['points'] = int(20 * max(0, min(1, edge_score)))
            breakdown['entry_extremity']['details'] = details

        # 5. RSI Divergence / Oversold/Overbought
        rsi = primary_df['rsi'].iloc[-1]
        if direction == 'long':
            points = 15 if rsi < 35 else (10 if rsi < 45 else 5)
            details = f"RSI at {rsi:.1f} (Oversold)"
        else: # short
            points = 15 if rsi > 65 else (10 if rsi > 55 else 5)
            details = f"RSI at {rsi:.1f} (Overbought)"
        breakdown['rsi_divergence']['points'] = points
        breakdown['rsi_divergence']['details'] = details

        # 6. Low Volatility (ATR contracting)
        atr_ratio = primary_df['atr'].iloc[-1] / primary_df['atr_sma'].iloc[-1]
        if atr_ratio < 0.9:
            breakdown['low_volatility']['points'] = 10
            breakdown['low_volatility']['details'] = f"Volatility contracting ({atr_ratio:.2f}x avg)"
        elif atr_ratio <= 1.0:
            breakdown['low_volatility']['points'] = 5
            breakdown['low_volatility']['details'] = f"Volatility stable ({atr_ratio:.2f}x avg)"
        else:
            breakdown['low_volatility']['details'] = f"Volatility expanding ({atr_ratio:.2f}x avg)"

        total_score = sum(b['points'] for b in breakdown.values())

        # Log the detailed breakdown
        log_message = f"{symbol} {direction.upper()} signal score breakdown (Mean-Reversion):\n"
        for key, value in breakdown.items():
            log_message += f"  - {key.replace('_', ' ').title():<20}: {value['points']:>2}/{value['max']} - {value['details']}\n"
        log_message += f"  TOTAL SCORE: {total_score}/100"
        logger.info(log_message)

        return total_score, breakdown

    @staticmethod
    def _score_fast_rally(primary_df: pd.DataFrame, direction: str) -> tuple:
        """Scores a fast rally/correction for HTF neutral override."""
        velocity_short = SignalScorer.detect_price_velocity(primary_df, 6) # 1.5h
        velocity_medium = SignalScorer.detect_price_velocity(primary_df, 12) # 3h
        is_strong_primary, _ = SignalScorer.detect_strong_primary_trend(primary_df, direction)

        if not is_strong_primary:
            return 8, f"HTF neutral, weak primary trend (1.5h: {velocity_short*100:+.1f}%)"

        if direction == 'long':
            if velocity_short > 0.05:
                return 25, f"Explosive rally: {velocity_short*100:+.1f}% in 1.5h"
            if velocity_short > 0.03 or velocity_medium > 0.045:
                return 22, f"Strong rally: {velocity_short*100:+.1f}% (1.5h), {velocity_medium*100:+.1f}% (3h)"
        else: # short
            if velocity_short < -0.05:
                return 25, f"Explosive correction: {velocity_short*100:.1f}% in 1.5h"
            if velocity_short < -0.03 or velocity_medium < -0.045:
                return 22, f"Strong correction: {velocity_short*100:.1f}% (1.5h), {velocity_medium*100:.1f}% (3h)"
        
        return 15, f"Moderate rally/correction with strong primary trend"
    
    # Keep detect_price_velocity and detect_strong_primary_trend as they are helpers
    @staticmethod
    def detect_price_velocity(df: pd.DataFrame, lookback_bars: int = 16) -> float:
        """Calculates price velocity over a lookback period."""
        if len(df) < lookback_bars + 1: return 0.0
        price_current = df['close'].iloc[-1]
        price_past = df['close'].iloc[-lookback_bars]
        return (price_current - price_past) / price_past if price_past != 0 else 0.0

    @staticmethod
    def detect_strong_primary_trend(primary_df: pd.DataFrame, direction: str) -> tuple:
        """Detects if the primary (15M) timeframe shows strong trending characteristics."""
        primary_trend = MarketStructure.get_trend_direction(primary_df)
        if (direction == 'long' and primary_trend != 'bullish') or \
           (direction == 'short' and primary_trend != 'bearish'):
            return False, f"Primary trend ({primary_trend}) opposes direction"

        macd_hist = primary_df['macd_hist'].tail(3).values
        if len(macd_hist) < 3: return False, "Insufficient MACD data"

        if direction == 'long':
            if not (macd_hist[-1] > macd_hist[-2] > macd_hist[-3] and macd_hist[-1] > 0):
                return False, "MACD not accelerating upward"
        else:
            if not (macd_hist[-1] < macd_hist[-2] < macd_hist[-3] and macd_hist[-1] < 0):
                return False, "MACD not accelerating downward"
        
        return True, "Accelerating MACD with aligned primary trend"

    @staticmethod
    def detect_fast_rally(primary_df: pd.DataFrame, direction: str) -> dict:
        """
        Detects a fast rally or correction, returning a dictionary with detection status and details.
        This is a helper for trend-following logic in neutral HTF conditions.
        """
        velocity_short = SignalScorer.detect_price_velocity(primary_df, 6)  # 1.5h
        velocity_medium = SignalScorer.detect_price_velocity(primary_df, 12) # 3h
        is_strong_primary, primary_reason = SignalScorer.detect_strong_primary_trend(primary_df, direction)

        detected = False
        strength = "none"

        if is_strong_primary:
            if direction == 'long':
                if velocity_short > 0.05:
                    detected = True
                    strength = "explosive"
                elif velocity_short > 0.03 or velocity_medium > 0.045:
                    detected = True
                    strength = "strong"
                elif velocity_short > 0.015:
                    detected = True
                    strength = "moderate"
            else:  # short
                if velocity_short < -0.05:
                    detected = True
                    strength = "explosive"
                elif velocity_short < -0.03 or velocity_medium < -0.045:
                    detected = True
                    strength = "strong"
                elif velocity_short < -0.015:
                    detected = True
                    strength = "moderate"
        
        return {
            'detected': detected,
            'strength': strength,
            'velocity_short': velocity_short,
            'velocity_medium': velocity_medium,
            'primary_reason': primary_reason
        }
