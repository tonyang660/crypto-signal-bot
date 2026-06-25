import pandas as pd
from typing import Dict, Optional, Tuple
from loguru import logger

class MarketStructure:
    """Analyze market structure and trend direction"""
    
    @staticmethod
    def get_trend_direction(df: pd.DataFrame) -> str:
        """
        Determine trend direction based on EMA alignment
        
        Returns: 'bullish', 'bearish', or 'neutral'
        """
        try:
            last_price = df['close'].iloc[-1]
            ema_fast = df['ema_fast'].iloc[-1]
            ema_medium = df['ema_medium'].iloc[-1]
            ema_slow = df['ema_slow'].iloc[-1]
            
            # === BULLISH CONDITIONS ===
            # Strong bullish: Perfect EMA order
            if last_price > ema_fast and ema_fast > ema_medium and ema_medium > ema_slow:
                return 'bullish'
            
            # Bullish with momentum: Price and ema_fast above ema_medium, even if ema_medium hasn't crossed ema_slow yet
            # This catches strong bullish moves where fast EMAs respond but slow ones lag
            elif last_price > ema_fast and last_price > ema_medium and ema_fast > ema_medium:
                # Verify it's not just a spike - check ema_fast is meaningfully above ema_medium
                ema_fast_above_ema_medium = (ema_fast - ema_medium) / ema_medium
                if ema_fast_above_ema_medium > 0.005:  # ema_fast > 0.5% above ema_medium
                    return 'bullish'
            
            # Bullish with strong price action: Price significantly above all EMAs
            elif last_price > ema_fast and last_price > ema_medium and last_price > ema_slow:
                # Check if price is strongly above (indicates momentum)
                price_above_ema_slow = (last_price - ema_slow) / ema_slow
                if price_above_ema_slow > 0.02:  # Price > 2% above ema_slow
                    return 'bullish'
            
            # === BEARISH CONDITIONS ===
            # Strong bearish: Perfect EMA order
            elif last_price < ema_fast and ema_fast < ema_medium and ema_medium < ema_slow:
                return 'bearish'
            
            # Bearish with momentum: Price and ema_fast below ema_medium
            elif last_price < ema_fast and last_price < ema_medium and ema_fast < ema_medium:
                ema_fast_below_ema_medium = (ema_medium - ema_fast) / ema_medium
                if ema_fast_below_ema_medium > 0.005:  # ema_fast > 0.5% below ema_medium
                    return 'bearish'
            
            # Bearish with strong price action: Price significantly below all EMAs
            elif last_price < ema_fast and last_price < ema_medium and last_price < ema_slow:
                price_below_ema_slow = (ema_slow - last_price) / ema_slow
                if price_below_ema_slow > 0.02:  # Price > 2% below ema_slow
                    return 'bearish'
            
            # Neutral/Mixed
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Error determining trend direction: {e}")
            return 'neutral'
    
    @staticmethod
    def find_swing_low(df: pd.DataFrame, lookback: int = 20) -> Optional[float]:
        """Find recent swing low within lookback period"""
        try:
            recent_data = df.tail(lookback)
            return recent_data['low'].min()
        except Exception as e:
            logger.error(f"Error finding swing low: {e}")
            return None
    
    @staticmethod
    def find_swing_high(df: pd.DataFrame, lookback: int = 20) -> Optional[float]:
        """Find recent swing high within lookback period"""
        try:
            recent_data = df.tail(lookback)
            return recent_data['high'].max()
        except Exception as e:
            logger.error(f"Error finding swing high: {e}")
            return None

    @staticmethod
    def analyze_mean_reversion_range(df: pd.DataFrame, lookback: int = 24) -> Dict:
        """
        Analyze the local sideways box used by mean-reversion entries.

        This intentionally uses a shorter local window than broad swing detection so
        a recent impulse leg does not make the current consolidation look like an
        extreme inside a stale 50-bar range.
        """
        try:
            if len(df) < lookback:
                return {
                    'valid': False,
                    'reason': f'Need at least {lookback} bars for local range analysis'
                }

            recent = df.tail(lookback)
            current_price = df['close'].iloc[-1]
            support = recent['low'].min()
            resistance = recent['high'].max()
            range_width = resistance - support

            if range_width <= 0:
                return {'valid': False, 'reason': 'Invalid local range width'}

            atr = df['atr'].iloc[-1] if 'atr' in df.columns else 0
            atr_sma = df['atr_sma'].iloc[-1] if 'atr_sma' in df.columns else atr
            atr_ratio = atr / atr_sma if atr_sma else 1.0
            range_width_atr = range_width / atr if atr else 0
            range_position = (current_price - support) / range_width

            buffer = 0.15 * atr if atr else 0
            recent_closes = recent['close'].tail(8)
            closes_above = int((recent_closes > resistance + buffer).sum())
            closes_below = int((recent_closes < support - buffer).sum())
            last_close = recent['close'].iloc[-1]
            previous_close = recent['close'].iloc[-2] if len(recent) > 1 else last_close
            upper_pressure = range_position >= 0.85 and last_close > previous_close
            lower_pressure = range_position <= 0.15 and last_close < previous_close

            adx = df['adx'].iloc[-1] if 'adx' in df.columns else 0
            ema_fast = df['ema_fast'].iloc[-1] if 'ema_fast' in df.columns else current_price
            ema_slow = df['ema_slow'].iloc[-1] if 'ema_slow' in df.columns else current_price
            ema_spread_pct = abs(ema_fast - ema_slow) / current_price if current_price else 0

            breakout_risk_reasons = []
            if closes_above or closes_below:
                breakout_risk_reasons.append('recent close outside range')
            if atr_ratio > 1.0:
                breakout_risk_reasons.append(f'ATR expanding ({atr_ratio:.2f}x avg)')
            if adx > 16:
                breakout_risk_reasons.append(f'ADX too high ({adx:.1f})')
            if ema_spread_pct > 0.01:
                breakout_risk_reasons.append(f'EMA spread too wide ({ema_spread_pct*100:.2f}%)')
            if range_width_atr < 1.5:
                breakout_risk_reasons.append(f'range too tight ({range_width_atr:.1f} ATR)')
            if range_width_atr > 5.0:
                breakout_risk_reasons.append(f'range too wide ({range_width_atr:.1f} ATR)')
            if upper_pressure:
                breakout_risk_reasons.append('price pressing upper boundary')
            if lower_pressure:
                breakout_risk_reasons.append('price pressing lower boundary')

            return {
                'valid': len(breakout_risk_reasons) == 0,
                'support': support,
                'resistance': resistance,
                'width': range_width,
                'position': max(0.0, min(1.0, range_position)),
                'atr': atr,
                'atr_ratio': atr_ratio,
                'range_width_atr': range_width_atr,
                'buffer': buffer,
                'breakout_risk_reasons': breakout_risk_reasons,
                'reason': '; '.join(breakout_risk_reasons) if breakout_risk_reasons else 'Contained local range'
            }

        except Exception as e:
            logger.error(f"Error analyzing mean-reversion range: {e}")
            return {'valid': False, 'reason': f'Range analysis error: {e}'}
    
    @staticmethod
    def is_price_near_ema(
        df: pd.DataFrame, 
        ema_col: str, 
        threshold: float = 0.003
    ) -> bool:
        """
        Check if price is within threshold of EMA
        
        Args:
            df: DataFrame with price and EMA data
            ema_col: Column name of EMA (e.g., 'ema_fast')
            threshold: Distance threshold (default 0.3%)
        
        Returns:
            True if price is within threshold
        """
        try:
            last_price = df['close'].iloc[-1]
            ema_value = df[ema_col].iloc[-1]
            
            distance = abs(last_price - ema_value) / ema_value
            return distance <= threshold
            
        except Exception as e:
            logger.error(f"Error checking price near EMA: {e}")
            return False
    
    @staticmethod
    def get_ema_slope(df: pd.DataFrame, ema_col: str, periods: int = 3) -> float:
        """
        Calculate EMA slope to determine trend strength
        
        Positive slope = uptrend, Negative slope = downtrend
        """
        try:
            ema_values = df[ema_col].tail(periods).values
            if len(ema_values) < 2:
                return 0.0
            
            # Calculate average change per period
            slope = (ema_values[-1] - ema_values[0]) / ema_values[0]
            return slope
            
        except Exception as e:
            logger.error(f"Error calculating EMA slope: {e}")
            return 0.0
    
    @staticmethod
    def detect_break_of_structure(
        df: pd.DataFrame,
        direction: str,
        lookback: int = 20,
        confirmation_bars: int = 20
    ) -> Tuple[bool, int, float]:
        """
        Detect if price has broken a recent market structure (swing high/low)
        
        For LONG: Detects bullish BOS (break above recent swing high)
        For SHORT: Detects bearish BOS (break below recent swing low)
        
        Args:
            df: DataFrame with OHLC data
            direction: 'long' or 'short'
            lookback: Bars to look back for swing points (default 20)
            confirmation_bars: Recent bars to check for the break (default 20)
        
        Returns:
            (bos_detected: bool, bars_ago: int, structure_level: float)
            - bos_detected: True if structure break detected
            - bars_ago: How many bars ago the break occurred (0 = current bar)
            - structure_level: Price level that was broken
        """
        try:
            if len(df) < lookback + confirmation_bars:
                return False, 0, 0.0
            
            # Get data excluding the most recent confirmation_bars
            # (to find structure before the potential break)
            historical_df = df.iloc[:-confirmation_bars] if confirmation_bars > 0 else df
            
            if len(historical_df) < lookback:
                return False, 0, 0.0
            
            # Get recent bars where break might have occurred
            recent_df = df.tail(confirmation_bars)
            
            if direction == 'long':
                # Find the most significant swing high in historical data
                structure_level = historical_df.tail(lookback)['high'].max()
                
                # Check if price has broken above this level in recent bars
                # Search from MOST RECENT to OLDEST to find the freshest BOS
                for i in range(len(recent_df) - 1, -1, -1):
                    if recent_df.iloc[i]['high'] > structure_level:
                        bars_ago = len(recent_df) - 1 - i
                        return True, bars_ago, structure_level
                
                return False, 0, structure_level
            
            elif direction == 'short':
                # Find the most significant swing low in historical data
                structure_level = historical_df.tail(lookback)['low'].min()
                
                # Check if price has broken below this level in recent bars
                # Search from MOST RECENT to OLDEST to find the freshest BOS
                for i in range(len(recent_df) - 1, -1, -1):
                    if recent_df.iloc[i]['low'] < structure_level:
                        bars_ago = len(recent_df) - 1 - i
                        return True, bars_ago, structure_level
                
                return False, 0, structure_level
            
            else:
                logger.warning(f"Invalid direction for BOS detection: {direction}")
                return False, 0, 0.0
                
        except Exception as e:
            logger.error(f"Error detecting break of structure: {e}")
            return False, 0, 0.0
    
    @staticmethod
    def get_bos_quality_score(
        bos_detected: bool,
        bars_ago: int,
        max_points: int = 13
    ) -> Tuple[int, str]:
        """
        Calculate quality score for Break of Structure based on recency
        
        Recent breaks are stronger signals than older breaks
        
        Args:
            bos_detected: Whether BOS was detected
            bars_ago: How many bars ago the break occurred
            max_points: Maximum points possible (default 13)
        
        Returns:
            (points: int, description: str)
            
        Scoring:
            - Within 3 bars: 13 points (very strong)
            - Within 7 bars: 10 points (strong)
            - Within 10 bars: 7 points (moderate)
            - Within 15 bars: 4 points (weak)
            - Within 20 bars: 2 points (very weak)
            - Older or no BOS: 0 points
        """
        if not bos_detected:
            return 0, "No structure break"
        
        # Score based on recency
        if bars_ago <= 3:
            return max_points, f"BOS within {bars_ago} bars (very strong)"
        elif bars_ago <= 7:
            points = int(max_points * 0.77)  # ~10 points for 13 max
            return points, f"BOS within {bars_ago} bars (strong)"
        elif bars_ago <= 10:
            points = int(max_points * 0.54)  # ~7 points
            return points, f"BOS within {bars_ago} bars (moderate)"
        elif bars_ago <= 15:
            points = int(max_points * 0.31)  # ~4 points
            return points, f"BOS within {bars_ago} bars (weak)"
        elif bars_ago <= 20:
            points = int(max_points * 0.15)  # ~2 points
            return points, f"BOS within {bars_ago} bars (very weak)"
        else:
            return 0, f"BOS {bars_ago} bars ago (too old)"
