import pandas as pd
from typing import Dict
from loguru import logger
from src.analysis.market_structure import MarketStructure
from src.core.config import Config

class StopTPCalculator:
    """Calculate stop loss and take profit levels"""
    
    @staticmethod
    def calculate_stop_loss(
        data: Dict[str, pd.DataFrame],
        direction: str,
        entry_price: float
    ) -> float:
        """
        Calculate stop loss level
        
        Uses tighter of:
        - ATR-based stop
        - Swing structure stop
        
        With hard cap at 2× ATR
        
        Args:
            data: Multi-timeframe data dict
            direction: 'long' or 'short'
            entry_price: Entry price level
        
        Returns:
            Stop loss price
        """
        try:
            primary_df = data['primary']
            
            atr = primary_df['atr'].iloc[-1]
            
            if direction == 'long':
                # ATR-based stop
                stop_atr = entry_price - (Config.ATR_STOP_MULTIPLIER * atr)
                
                # Swing low stop
                swing_low = MarketStructure.find_swing_low(primary_df, lookback=20)
                if swing_low:
                    stop_swing = swing_low - (0.2 * atr)  # Buffer below swing
                else:
                    stop_swing = stop_atr
                
                # Use tighter stop (higher value for long)
                stop_loss = max(stop_atr, stop_swing)
                
                # Hard cap: stop distance cannot exceed 2× ATR
                max_stop_distance = 2 * atr
                if (entry_price - stop_loss) > max_stop_distance:
                    stop_loss = entry_price - max_stop_distance
            
            else:  # short
                # ATR-based stop
                stop_atr = entry_price + (Config.ATR_STOP_MULTIPLIER * atr)
                
                # Swing high stop
                swing_high = MarketStructure.find_swing_high(primary_df, lookback=20)
                if swing_high:
                    stop_swing = swing_high + (0.2 * atr)  # Buffer above swing
                else:
                    stop_swing = stop_atr
                
                # Use tighter stop (lower value for short)
                stop_loss = min(stop_atr, stop_swing)
                
                # Hard cap
                max_stop_distance = 2 * atr
                if (stop_loss - entry_price) > max_stop_distance:
                    stop_loss = entry_price + max_stop_distance
            
            return round(stop_loss, 2)
            
        except Exception as e:
            logger.error(f"Error calculating stop loss: {e}")
            # Fallback to simple ATR-based stop
            atr = data['primary']['atr'].iloc[-1]
            if direction == 'long':
                return round(entry_price - (1.5 * atr), 2)
            else:
                return round(entry_price + (1.5 * atr), 2)
    
    @staticmethod
    def calculate_take_profits(
        entry_price: float,
        stop_loss: float,
        direction: str
    ) -> Dict[str, Dict]:
        """
        Calculate TP levels based on risk multiples
        
        Returns:
            Dict with tp1, tp2, tp3 containing price and close_percent
        """
        try:
            if direction == 'long':
                risk = entry_price - stop_loss
                
                return {
                    'tp1': {
                        'price': round(entry_price + (risk * Config.TP1_RATIO), 2),
                        'close_percent': Config.TP1_CLOSE_PERCENT,
                        'ratio': Config.TP1_RATIO
                    },
                    'tp2': {
                        'price': round(entry_price + (risk * Config.TP2_RATIO), 2),
                        'close_percent': Config.TP2_CLOSE_PERCENT,
                        'ratio': Config.TP2_RATIO
                    },
                    'tp3': {
                        'price': round(entry_price + (risk * Config.TP3_RATIO), 2),
                        'close_percent': Config.TP3_CLOSE_PERCENT,
                        'ratio': Config.TP3_RATIO
                    }
                }
            
            else:  # short
                risk = stop_loss - entry_price
                
                return {
                    'tp1': {
                        'price': round(entry_price - (risk * Config.TP1_RATIO), 2),
                        'close_percent': Config.TP1_CLOSE_PERCENT,
                        'ratio': Config.TP1_RATIO
                    },
                    'tp2': {
                        'price': round(entry_price - (risk * Config.TP2_RATIO), 2),
                        'close_percent': Config.TP2_CLOSE_PERCENT,
                        'ratio': Config.TP2_RATIO
                    },
                    'tp3': {
                        'price': round(entry_price - (risk * Config.TP3_RATIO), 2),
                        'close_percent': Config.TP3_CLOSE_PERCENT,
                        'ratio': Config.TP3_RATIO
                    }
                }
                
        except Exception as e:
            logger.error(f"Error calculating take profits: {e}")
            return {}