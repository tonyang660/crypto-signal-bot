import pandas as pd
from typing import Dict, Optional
from loguru import logger
from src.analysis.market_structure import MarketStructure
from src.core.config import Config
from src.strategy.regime_algorithm_manager import MarketRegime
from src.strategy.regime_scorers import HVScorer, IQScorer, CSScorer

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
        entry_price: float,
        regime: Optional[MarketRegime] = None
    ) -> float:
        """
        Calculate stop loss level using regime-specific ATR multipliers.
        
        Regime ATR Multipliers:
        - HV (Bull): 1.8x ATR (tighter - trend is your friend)
        - IQ (Bear): 2.0x ATR (wider - expect volatility spikes)
        - CS (Choppy): 1.5x ATR (tightest - exit bad trades fast)
        
        Uses tighter of:
        - Regime-adjusted ATR-based stop
        - Swing structure stop
        
        With hard cap at 2× ATR
        
        Args:
            data: Multi-timeframe data dict
            direction: 'long' or 'short'
            entry_price: Entry price level
            regime: Current market regime
        
        Returns:
            Stop loss price
        """
        try:
            primary_df = data['primary']
            
            atr = primary_df['atr'].iloc[-1]
            
            # Get regime-specific ATR multiplier
            if regime == MarketRegime.HV:
                atr_multiplier = HVScorer.get_config()['sl_multiplier']  # 1.8
            elif regime == MarketRegime.IQ:
                atr_multiplier = IQScorer.get_config()['sl_multiplier']  # 2.0
            elif regime == MarketRegime.CS:
                atr_multiplier = CSScorer.get_config()['sl_multiplier']  # 1.5
            else:
                atr_multiplier = Config.ATR_STOP_MULTIPLIER  # Fallback to default
            
            if direction == 'long':
                # Regime-adjusted ATR-based stop
                stop_atr = entry_price - (atr_multiplier * atr)
                
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
                # Regime-adjusted ATR-based stop
                stop_atr = entry_price + (atr_multiplier * atr)
                
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
        regime: Optional[MarketRegime] = None
    ) -> Dict[str, Dict]:
        """
        Calculate TP levels based on risk multiples, using regime-specific ratios.
        
        Regime TP Ratios:
        - HV (Bull): [2.0R, 3.5R, 5.0R] - let winners run
        - IQ (Bear): [1.5R, 2.5R, 4.0R] - take profits faster
        - CS (Choppy): [1.2R, 2.0R, 3.0R] - scalp mode
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            direction: 'long' or 'short'
            regime: Current market regime
        
        Returns:
            Dict with tp1, tp2, tp3 containing price and close_percent
        """
        try:
            # Get regime-specific TP ratios
            if regime == MarketRegime.HV:
                tp_ratios = HVScorer.get_config()['tp_ratios']  # [2.0, 3.5, 5.0]
                tp_percentages = HVScorer.get_config()['tp_percentages']
                regime_desc = "HV Bull - Aggressive"
            elif regime == MarketRegime.IQ:
                tp_ratios = IQScorer.get_config()['tp_ratios']  # [1.5, 2.5, 4.0]
                tp_percentages = IQScorer.get_config()['tp_percentages']
                regime_desc = "IQ Bear - Conservative"
            elif regime == MarketRegime.CS:
                tp_ratios = CSScorer.get_config()['tp_ratios']  # [1.2, 2.0, 3.0]
                tp_percentages = CSScorer.get_config()['tp_percentages']
                regime_desc = "CS Choppy - Scalp"
            else:
                # Fallback to defaults from Config
                tp_ratios = [Config.TP1_RATIO, Config.TP2_RATIO, Config.TP3_RATIO]
                tp_percentages = [Config.TP1_CLOSE_PERCENT, Config.TP2_CLOSE_PERCENT, Config.TP3_CLOSE_PERCENT]
                regime_desc = "Default"
            
            logger.debug(f"Regime '{regime_desc}': TP ratios {tp_ratios}")
            
            if direction == 'long':
                risk = entry_price - stop_loss
                
                return {
                    'tp1': {
                        'price': StopTPCalculator._smart_round(entry_price + (risk * tp_ratios[0])),
                        'close_percent': tp_percentages[0],
                        'ratio': tp_ratios[0]
                    },
                    'tp2': {
                        'price': StopTPCalculator._smart_round(entry_price + (risk * tp_ratios[1])),
                        'close_percent': tp_percentages[1],
                        'ratio': tp_ratios[1]
                    },
                    'tp3': {
                        'price': StopTPCalculator._smart_round(entry_price + (risk * tp_ratios[2])),
                        'close_percent': tp_percentages[2],
                        'ratio': tp_ratios[2]
                    }
                }
            
            else:  # short
                risk = stop_loss - entry_price
                
                return {
                    'tp1': {
                        'price': StopTPCalculator._smart_round(entry_price - (risk * tp_ratios[0])),
                        'close_percent': tp_percentages[0],
                        'ratio': tp_ratios[0]
                    },
                    'tp2': {
                        'price': StopTPCalculator._smart_round(entry_price - (risk * tp_ratios[1])),
                        'close_percent': tp_percentages[1],
                        'ratio': tp_ratios[1]
                    },
                    'tp3': {
                        'price': StopTPCalculator._smart_round(entry_price - (risk * tp_ratios[2])),
                        'close_percent': tp_percentages[2],
                        'ratio': tp_ratios[2]
                    }
                }
                
        except Exception as e:
            logger.error(f"Error calculating take profits: {e}")
            return {}