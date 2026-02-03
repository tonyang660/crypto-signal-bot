import pandas as pd
from typing import Dict
from loguru import logger
from src.analysis.market_structure import MarketStructure
from src.core.config import Config

class StopTPCalculator:
    """Calculate stop loss and take profit levels"""
    
    @staticmethod
    def _smart_round(price: float) -> float:
        """Round price based on its magnitude for precision"""
        if price < 0.01:
            return round(price, 8)
        elif price < 0.1:
            return round(price, 6)
        elif price < 1:
            return round(price, 5)
        elif price < 10:
            return round(price, 4)
        elif price < 100:
            return round(price, 3)
        else:
            return round(price, 2)
    
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
            
            return StopTPCalculator._smart_round(stop_loss)
            
        except Exception as e:
            logger.error(f"Error calculating stop loss: {e}")
            # Fallback to simple ATR-based stop
            atr = data['primary']['atr'].iloc[-1]
            if direction == 'long':
                return StopTPCalculator._smart_round(entry_price - (1.5 * atr))
            else:
                return StopTPCalculator._smart_round(entry_price + (1.5 * atr))
    
    @staticmethod
    def calculate_take_profits(
        entry_price: float,
        stop_loss: float,
        direction: str,
        regime: str = 'trending'
    ) -> Dict[str, Dict]:
        """
        Calculate TP levels based on risk multiples, adjusted for market regime
        
        Regime adjustments:
        - trending: Full TP targets (let winners run)
        - high_volatility: Tighter TPs (take profits faster before reversal)
        - choppy/low_volatility: Very tight TPs (scalp mode)
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            direction: 'long' or 'short'
            regime: Market regime from RegimeDetector
        
        Returns:
            Dict with tp1, tp2, tp3 containing price and close_percent
        """
        try:
            # Adjust TP ratios based on regime
            if regime == 'trending':
                # Let winners run in strong trends
                tp1_ratio = Config.TP1_RATIO
                tp2_ratio = Config.TP2_RATIO
                tp3_ratio = Config.TP3_RATIO
                logger.debug(f"Regime '{regime}': Using full TP targets")
                
            elif regime == 'high_volatility':
                # Take profits faster in volatile markets (prevents giveback)
                tp1_ratio = Config.TP1_RATIO * 0.8  # 1.5 → 1.2
                tp2_ratio = Config.TP2_RATIO * 0.8  # 2.5 → 2.0
                tp3_ratio = Config.TP3_RATIO * 0.8  # 3.5 → 2.8
                logger.info(f"Regime '{regime}': Tighter TPs (80% of normal)")
                
            else:  # choppy or low_volatility
                # Very conservative in choppy markets
                tp1_ratio = Config.TP1_RATIO * 0.6  # 1.5 → 0.9
                tp2_ratio = Config.TP2_RATIO * 0.6  # 2.5 → 1.5
                tp3_ratio = Config.TP3_RATIO * 0.6  # 3.5 → 2.1
                logger.info(f"Regime '{regime}': Very tight TPs (60% of normal) - scalp mode")
            
            if direction == 'long':
                risk = entry_price - stop_loss
                
                return {
                    'tp1': {
                        'price': StopTPCalculator._smart_round(entry_price + (risk * tp1_ratio)),
                        'close_percent': Config.TP1_CLOSE_PERCENT,
                        'ratio': tp1_ratio
                    },
                    'tp2': {
                        'price': StopTPCalculator._smart_round(entry_price + (risk * tp2_ratio)),
                        'close_percent': Config.TP2_CLOSE_PERCENT,
                        'ratio': tp2_ratio
                    },
                    'tp3': {
                        'price': StopTPCalculator._smart_round(entry_price + (risk * tp3_ratio)),
                        'close_percent': Config.TP3_CLOSE_PERCENT,
                        'ratio': tp3_ratio
                    }
                }
            
            else:  # short
                risk = stop_loss - entry_price
                
                return {
                    'tp1': {
                        'price': StopTPCalculator._smart_round(entry_price - (risk * tp1_ratio)),
                        'close_percent': Config.TP1_CLOSE_PERCENT,
                        'ratio': tp1_ratio
                    },
                    'tp2': {
                        'price': StopTPCalculator._smart_round(entry_price - (risk * tp2_ratio)),
                        'close_percent': Config.TP2_CLOSE_PERCENT,
                        'ratio': tp2_ratio
                    },
                    'tp3': {
                        'price': StopTPCalculator._smart_round(entry_price - (risk * tp3_ratio)),
                        'close_percent': Config.TP3_CLOSE_PERCENT,
                        'ratio': tp3_ratio
                    }
                }
                
        except Exception as e:
            logger.error(f"Error calculating take profits: {e}")
            return {}