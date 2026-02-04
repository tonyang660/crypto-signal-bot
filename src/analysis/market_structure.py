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
            
            # Bullish: Price > EMA21 > EMA50 > EMA200
            if last_price > ema_21 and ema_21 > ema_50 and ema_50 > ema_200:
                return 'bullish'
            
            # Bearish: Price < EMA21 < EMA50 < EMA200
            elif last_price < ema_21 and ema_21 < ema_50 and ema_50 < ema_200:
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
    ) -> Tuple[bool, Optional[int], Optional[float]]:
        """
        Detect break of market structure
        
        Args:
            df: DataFrame with price data
            direction: 'long' or 'short'
            lookback: Number of bars to look back for structure
            confirmation_bars: Number of bars after BOS for confirmation
            
        Returns:
            Tuple of (bos_detected, bars_ago, structure_level)
        """
        try:
            if len(df) < lookback + confirmation_bars:
                return False, None, None
            
            recent_data = df.tail(lookback + confirmation_bars)
            
            if direction == 'long':
                # For longs, look for break above recent swing high
                # Find swing high in the lookback period (excluding most recent bars)
                swing_high_data = recent_data.iloc[:-confirmation_bars] if confirmation_bars > 0 else recent_data
                swing_high = swing_high_data['high'].max()
                swing_high_idx = swing_high_data['high'].idxmax()
                
                # Check if price broke above this swing high recently
                current_price = df['close'].iloc[-1]
                recent_high = df['high'].tail(confirmation_bars).max()
                
                if recent_high > swing_high:
                    # Find how many bars ago the break occurred
                    break_idx = None
                    for i in range(len(df) - 1, max(0, len(df) - confirmation_bars - 1), -1):
                        if df['high'].iloc[i] > swing_high:
                            break_idx = len(df) - 1 - i
                            break
                    
                    return True, break_idx, swing_high
                
            elif direction == 'short':
                # For shorts, look for break below recent swing low
                swing_low_data = recent_data.iloc[:-confirmation_bars] if confirmation_bars > 0 else recent_data
                swing_low = swing_low_data['low'].min()
                swing_low_idx = swing_low_data['low'].idxmin()
                
                # Check if price broke below this swing low recently
                current_price = df['close'].iloc[-1]
                recent_low = df['low'].tail(confirmation_bars).min()
                
                if recent_low < swing_low:
                    # Find how many bars ago the break occurred
                    break_idx = None
                    for i in range(len(df) - 1, max(0, len(df) - confirmation_bars - 1), -1):
                        if df['low'].iloc[i] < swing_low:
                            break_idx = len(df) - 1 - i
                            break
                    
                    return True, break_idx, swing_low
            
            return False, None, None
            
        except Exception as e:
            logger.error(f"Error detecting break of structure: {e}")
            return False, None, None
    
    @staticmethod
    def get_bos_quality_score(
        bos_detected: bool, 
        bars_ago: Optional[int],
        max_points: int = 10
    ) -> Tuple[int, str]:
        """
        Score the quality of a break of structure
        
        Args:
            bos_detected: Whether BOS was detected
            bars_ago: How many bars ago the break occurred
            max_points: Maximum points to award
            
        Returns:
            Tuple of (points, description)
        """
        if not bos_detected or bars_ago is None:
            return 0, "No BOS detected"
        
        # Score based on recency - more recent breaks are more relevant
        if bars_ago <= 3:
            points = max_points
            desc = "Recent BOS (very strong)"
        elif bars_ago <= 7:
            points = int(max_points * 0.8)
            desc = "BOS within 7 bars (strong)"
        elif bars_ago <= 15:
            points = int(max_points * 0.6)
            desc = "BOS within 15 bars (moderate)"
        elif bars_ago <= 25:
            points = int(max_points * 0.4)
            desc = "BOS within 25 bars (weak)"
        else:
            points = int(max_points * 0.2)
            desc = "Old BOS (very weak)"
        
        return points, desc