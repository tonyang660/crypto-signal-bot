import pandas as pd
from typing import Optional, Tuple
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
            ema_21 = df['ema_21'].iloc[-1]
            ema_50 = df['ema_50'].iloc[-1]
            ema_200 = df['ema_200'].iloc[-1]
            
            # === BULLISH CONDITIONS ===
            # Strong bullish: Perfect EMA order
            if last_price > ema_21 and ema_21 > ema_50 and ema_50 > ema_200:
                return 'bullish'
            
            # Bullish with momentum: Price and EMA21 above EMA50, even if EMA50 hasn't crossed EMA200 yet
            # This catches strong bullish moves where fast EMAs respond but slow ones lag
            elif last_price > ema_21 and last_price > ema_50 and ema_21 > ema_50:
                # Verify it's not just a spike - check EMA21 is meaningfully above EMA50
                ema21_above_ema50 = (ema_21 - ema_50) / ema_50
                if ema21_above_ema50 > 0.005:  # EMA21 > 0.5% above EMA50
                    return 'bullish'
            
            # Bullish with strong price action: Price significantly above all EMAs
            elif last_price > ema_21 and last_price > ema_50 and last_price > ema_200:
                # Check if price is strongly above (indicates momentum)
                price_above_ema200 = (last_price - ema_200) / ema_200
                if price_above_ema200 > 0.02:  # Price > 2% above EMA200
                    return 'bullish'
            
            # === BEARISH CONDITIONS ===
            # Strong bearish: Perfect EMA order
            elif last_price < ema_21 and ema_21 < ema_50 and ema_50 < ema_200:
                return 'bearish'
            
            # Bearish with momentum: Price and EMA21 below EMA50
            elif last_price < ema_21 and last_price < ema_50 and ema_21 < ema_50:
                ema21_below_ema50 = (ema_50 - ema_21) / ema_50
                if ema21_below_ema50 > 0.005:  # EMA21 > 0.5% below EMA50
                    return 'bearish'
            
            # Bearish with strong price action: Price significantly below all EMAs
            elif last_price < ema_21 and last_price < ema_50 and last_price < ema_200:
                price_below_ema200 = (ema_200 - last_price) / ema_200
                if price_below_ema200 > 0.02:  # Price > 2% below EMA200
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
    def is_price_near_ema(
        df: pd.DataFrame, 
        ema_col: str, 
        threshold: float = 0.003
    ) -> bool:
        """
        Check if price is within threshold of EMA
        
        Args:
            df: DataFrame with price and EMA data
            ema_col: Column name of EMA (e.g., 'ema_21')
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