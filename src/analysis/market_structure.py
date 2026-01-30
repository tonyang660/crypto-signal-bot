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