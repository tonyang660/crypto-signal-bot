import pandas as pd
from loguru import logger
from .indicators import Indicators

class RegimeDetector:
    """Detect market regime for adaptive strategy behavior"""
    
    @staticmethod
    def detect_regime(df: pd.DataFrame) -> str:
        """
        Detect market regime
        
        Returns: 'high_volatility', 'low_volatility', 'trending', or 'choppy'
        """
        try:
            atr = df['atr'].iloc[-1]
            atr_avg = df['atr_sma'].iloc[-1]
            
            # Prevent division by zero
            if atr_avg == 0:
                return 'choppy'
            
            atr_ratio = atr / atr_avg
            
            # Calculate ADX for trend strength
            adx = Indicators.calculate_adx(df)
            
            # High Volatility (ATR spike)
            if atr_ratio > 1.5:
                return 'high_volatility'
            
            # Low Volatility (compressed)
            elif atr_ratio < 0.7:
                return 'low_volatility'
            
            # Trending (strong directional movement)
            elif adx > 25:
                return 'trending'
            
            # Choppy (sideways, no clear direction)
            else:
                return 'choppy'
                
        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return 'choppy'
    
    @staticmethod
    def should_trade_regime(regime: str) -> bool:
        """
        Determine if regime is suitable for trading
        
        Skip trading in: low_volatility, choppy
        Trade in: trending, high_volatility (with caution)
        """
        favorable_regimes = ['trending', 'high_volatility']
        return regime in favorable_regimes
    
    @staticmethod
    def get_regime_multipliers(regime: str) -> dict:
        """
        Get strategy parameter adjustments based on regime
        
        Returns dict with ATR multiplier, score threshold, etc.
        """
        multipliers = {
            'trending': {
                'atr_multiplier': 1.5,
                'score_threshold': 70,
                'tp_extension': 1.0  # Allow full TP targets
            },
            'high_volatility': {
                'atr_multiplier': 1.8,  # Wider stops
                'score_threshold': 80,   # Higher quality only
                'tp_extension': 0.8      # Take profits earlier
            },
            'low_volatility': {
                'atr_multiplier': 1.2,
                'score_threshold': 85,
                'tp_extension': 0.6
            },
            'choppy': {
                'atr_multiplier': 1.5,
                'score_threshold': 90,   # Almost never trade
                'tp_extension': 0.5
            }
        }
        
        return multipliers.get(regime, multipliers['choppy'])