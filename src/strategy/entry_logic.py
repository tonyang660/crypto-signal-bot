import pandas as pd
from typing import Dict, Optional
from loguru import logger
from src.analysis.market_structure import MarketStructure
from src.analysis.regime_detector import RegimeDetector
from src.core.config import Config

class EntryLogic:
    """Entry condition validation for long and short positions, adapted for market regimes."""
    
    @staticmethod
    def get_entry_conditions(data: Dict[str, pd.DataFrame], direction: str) -> dict:
        """
        Determines and checks entry conditions based on the current market regime.

        Args:
            data (Dict[str, pd.DataFrame]): Dictionary with 'htf', 'primary', 'entry' dataframes.
            direction (str): 'long' or 'short'.

        Returns:
            Dict: {'valid': bool, 'reason': str}
        """
        primary_df = data['primary']
        
        # 1. Detect Market Regime
        regime = RegimeDetector.detect_regime(primary_df)
        strategy_type = RegimeDetector.get_regime_strategy(regime)
        
        logger.info(f"Market Regime: {regime} -> Strategy: {strategy_type}")

        # 2. Select and Execute Strategy
        if strategy_type == 'Trend-Following':
            if direction == 'long':
                return EntryLogic.check_trend_following_long(data)
            else:
                return EntryLogic.check_trend_following_short(data)
        elif strategy_type == 'Mean-Reversion':
            if direction == 'long':
                return EntryLogic.check_mean_reversion_long(data)
            else:
                return EntryLogic.check_mean_reversion_short(data)
        
        return {'valid': False, 'reason': 'Invalid strategy type'}

    @staticmethod
    def check_trend_following_long(data: Dict[str, pd.DataFrame]) -> dict:
        """Trend-following long entry conditions."""
        # This is the original check_long_entry logic
        return EntryLogic.check_long_entry(data)

    @staticmethod
    def check_trend_following_short(data: Dict[str, pd.DataFrame]) -> dict:
        """Trend-following short entry conditions."""
        # This is the original check_short_entry logic
        return EntryLogic.check_short_entry(data)

    @staticmethod
    def check_mean_reversion_long(data: Dict[str, pd.DataFrame]) -> dict:
        """
        Mean-reversion long entry: Buy near a support level in a sideways market,
        looking for signs of a bounce.
        """
        primary_df = data['primary']
        entry_df = data['entry']
        
        # 1. Confirm Sideways Market on the primary timeframe
        if RegimeDetector.detect_regime(primary_df) != 'Sideways':
            return {'valid': False, 'reason': 'MR Long: Not in a sideways market.'}

        # 2. Identify a clear support level using recent swing lows
        support_level = MarketStructure.find_swing_low(primary_df, lookback=50, prominence_percent=0.01)
        if support_level is None:
            return {'valid': False, 'reason': 'MR Long: No clear support level found.'}

        # 3. Entry Trigger: Price must be close to the identified support level
        current_price = entry_df['close'].iloc[-1]
        atr = primary_df['atr'].iloc[-1]
        
        # Define a "support zone" around the level
        support_zone_top = support_level + (0.3 * atr)
        support_zone_bottom = support_level - (0.3 * atr)

        if not (support_zone_bottom <= current_price <= support_zone_top):
            return {'valid': False, 'reason': f'MR Long: Price ${current_price:.2f} not in support zone (${support_zone_bottom:.2f}-${support_zone_top:.2f}).'}

        # 4. Reversal Confirmation
        # a) RSI showing bullish divergence or coming out of oversold
        rsi = primary_df['rsi'].iloc[-1]
        rsi_prev = primary_df['rsi'].iloc[-2]
        if not (rsi > rsi_prev and rsi < 45):
            return {'valid': False, 'reason': f'MR Long: RSI {rsi:.1f} not showing bullish confirmation.'}

        # b) Entry timeframe (5m) MACD must be turning up
        macd_5m_hist = entry_df['macd_hist'].iloc[-1]
        macd_5m_hist_prev = entry_df['macd_hist'].iloc[-2]
        if macd_5m_hist <= macd_5m_hist_prev:
            return {'valid': False, 'reason': 'MR Long: 5m MACD momentum is not turning positive.'}

        return {'valid': True, 'reason': f'Mean-reversion long triggered near support ${support_level:.2f} with reversal confirmation.'}

    @staticmethod
    def check_mean_reversion_short(data: Dict[str, pd.DataFrame]) -> dict:
        """
        Mean-reversion short entry: Sell near a resistance level in a sideways market,
        looking for signs of a rejection.
        """
        primary_df = data['primary']
        entry_df = data['entry']

        # 1. Confirm Sideways Market
        if RegimeDetector.detect_regime(primary_df) != 'Sideways':
            return {'valid': False, 'reason': 'MR Short: Not in a sideways market.'}

        # 2. Identify a clear resistance level
        resistance_level = MarketStructure.find_swing_high(primary_df, lookback=50, prominence_percent=0.01)
        if resistance_level is None:
            return {'valid': False, 'reason': 'MR Short: No clear resistance level found.'}

        # 3. Entry Trigger: Price must be close to the identified resistance level
        current_price = entry_df['close'].iloc[-1]
        atr = primary_df['atr'].iloc[-1]

        # Define a "resistance zone"
        resistance_zone_top = resistance_level + (0.3 * atr)
        resistance_zone_bottom = resistance_level - (0.3 * atr)

        if not (resistance_zone_bottom <= current_price <= resistance_zone_top):
            return {'valid': False, 'reason': f'MR Short: Price ${current_price:.2f} not in resistance zone (${resistance_zone_bottom:.2f}-${resistance_zone_top:.2f}).'}

        # 4. Reversal Confirmation
        # a) RSI showing bearish divergence or coming out of overbought
        rsi = primary_df['rsi'].iloc[-1]
        rsi_prev = primary_df['rsi'].iloc[-2]
        if not (rsi < rsi_prev and rsi > 55):
            return {'valid': False, 'reason': f'MR Short: RSI {rsi:.1f} not showing bearish confirmation.'}

        # b) Entry timeframe (5m) MACD must be turning down
        macd_5m_hist = entry_df['macd_hist'].iloc[-1]
        macd_5m_hist_prev = entry_df['macd_hist'].iloc[-2]
        if macd_5m_hist >= macd_5m_hist_prev:
            return {'valid': False, 'reason': 'MR Short: 5m MACD momentum is not turning negative.'}

        return {'valid': True, 'reason': f'Mean-reversion short triggered near resistance ${resistance_level:.2f} with reversal confirmation.'}
    
    @staticmethod
    def check_long_entry(data: Dict[str, pd.DataFrame]) -> dict:
        """
        Check if long entry conditions are met
        
        Args:
            data: Dict with 'htf', 'primary', 'entry' dataframes
        
        Returns:
            Dict with 'valid' (bool) and 'reason' (str)
        """
        try:
            htf_df = data['htf']
            primary_df = data['primary']
            entry_df = data['entry']
            
            # 1. HTF Bias Filter (4H must be bullish OR neutral with fast rally)
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            
            if htf_trend == 'bearish':
                # Never go long in bearish HTF
                return {'valid': False, 'reason': f'HTF trend is bearish, opposing direction'}
            
            elif htf_trend == 'neutral':
                # Allow neutral HTF IF we detect fast rally (explosive PRIMARY momentum)
                # Import here to avoid circular dependency
                from src.strategy.signal_scorer import SignalScorer
                
                rally_data = SignalScorer.detect_fast_rally(primary_df, 'long')
                is_strong_primary, primary_reason = SignalScorer.detect_strong_primary_trend(primary_df, 'long')
                
                # Require fast rally detection (multi-window velocity check) AND strong PRIMARY trend
                if not (rally_data['detected'] and is_strong_primary):
                    return {'valid': False, 'reason': f"HTF neutral without fast rally confirmation (1.5h: {rally_data['velocity_short']*100:+.1f}%, 3h: {rally_data['velocity_medium']*100:+.1f}%)"}
                
                # Fast rally detected - proceed with entry checks
                logger.info(f"Fast rally override: HTF neutral but {rally_data['strength']} rally detected: 1.5h: {rally_data['velocity_short']*100:+.1f}%, 3h: {rally_data['velocity_medium']*100:+.1f}%, {primary_reason}")
            
            # If HTF is bullish or neutral with fast rally, continue...
            
            # 2. Volatility Filter
            current_atr = primary_df['atr'].iloc[-1]
            avg_atr = primary_df['atr_sma'].iloc[-1]
            
            if avg_atr == 0:
                return {'valid': False, 'reason': 'Invalid ATR data'}
            
            atr_ratio = current_atr / avg_atr
            
            if atr_ratio < Config.VOLATILITY_MIN_RATIO:
                return {'valid': False, 'reason': f'ATR too low ({atr_ratio:.2f})'}
            
            if atr_ratio > Config.VOLATILITY_MAX_RATIO:
                return {'valid': False, 'reason': f'ATR too high ({atr_ratio:.2f})'}
            
            # 3. Primary Trend Structure (15M must align)
            primary_trend = MarketStructure.get_trend_direction(primary_df)
            if primary_trend != 'bullish':
                return {'valid': False, 'reason': f'Primary trend is {primary_trend}'}
            
            # 4. Momentum Confirmation (MACD histogram with STRENGTH)
            macd_hist = primary_df['macd_hist'].iloc[-1]
            macd_hist_prev = primary_df['macd_hist'].iloc[-2]
            macd_hist_2 = primary_df['macd_hist'].iloc[-3]
            
            if macd_hist <= 0:
                return {'valid': False, 'reason': 'MACD histogram not positive'}
            
            if macd_hist < macd_hist_prev:
                return {'valid': False, 'reason': 'MACD momentum declining'}
            
            # Require strong momentum - not just barely positive
            if abs(macd_hist) < abs(macd_hist_2) * 0.5:
                return {'valid': False, 'reason': 'MACD momentum too weak (losing strength)'}
            
            # 5. Entry Trigger (5M pullback to EMA21)
            if not MarketStructure.is_price_near_ema(entry_df, 'ema_21', 0.002):
                return {'valid': False, 'reason': 'Price not near EMA21'}
            
            # Check we're not entering right at a recent swing low (support)
            swing_low = MarketStructure.find_swing_low(primary_df, lookback=20)
            current_price = entry_df['close'].iloc[-1]
            atr = primary_df['atr'].iloc[-1]
            
            if swing_low and abs(current_price - swing_low) < (0.5 * atr):
                return {'valid': False, 'reason': f'Too close to swing low support (${swing_low:.2f})'}
            
            # 5M MACD turning up
            macd_5m_hist = entry_df['macd_hist'].iloc[-1]
            macd_5m_hist_prev = entry_df['macd_hist'].iloc[-2]
            
            if macd_5m_hist <= macd_5m_hist_prev:
                return {'valid': False, 'reason': '5M MACD not turning up'}
            
            # All conditions met
            return {'valid': True, 'reason': 'All long entry conditions met'}
            
        except Exception as e:
            logger.error(f"Error checking long entry: {e}")
            return {'valid': False, 'reason': f'Error: {str(e)}'}
    
    @staticmethod
    def check_short_entry(data: Dict[str, pd.DataFrame]) -> dict:
        """
        Check if short entry conditions are met
        
        Returns:
            Dict with 'valid' (bool) and 'reason' (str)
        """
        try:
            htf_df = data['htf']
            primary_df = data['primary']
            entry_df = data['entry']
            
            # 1. HTF Bias (must be bearish OR neutral with fast correction)
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            
            if htf_trend == 'bullish':
                # Never go short in bullish HTF
                return {'valid': False, 'reason': f'HTF trend is bullish, opposing direction'}
            
            elif htf_trend == 'neutral':
                # Allow neutral HTF IF we detect fast correction (explosive downward PRIMARY momentum)
                from src.strategy.signal_scorer import SignalScorer
                
                rally_data = SignalScorer.detect_fast_rally(primary_df, 'short')
                is_strong_primary, primary_reason = SignalScorer.detect_strong_primary_trend(primary_df, 'short')
                
                # Require fast correction detection (multi-window velocity check) AND strong PRIMARY trend
                if not (rally_data['detected'] and is_strong_primary):
                    return {'valid': False, 'reason': f"HTF neutral without fast correction confirmation (1.5h: {rally_data['velocity_short']*100:+.1f}%, 3h: {rally_data['velocity_medium']*100:+.1f}%)"}
                
                # Fast correction detected - proceed with entry checks
                logger.info(f"Fast correction override: HTF neutral but {rally_data['strength']} correction detected: 1.5h: {rally_data['velocity_short']*100:+.1f}%, 3h: {rally_data['velocity_medium']*100:+.1f}%, {primary_reason}")
            
            # If HTF is bearish or neutral with fast correction, continue...
            
            # 2. Volatility Filter
            current_atr = primary_df['atr'].iloc[-1]
            avg_atr = primary_df['atr_sma'].iloc[-1]
            
            if avg_atr == 0:
                return {'valid': False, 'reason': 'Invalid ATR data'}
            
            atr_ratio = current_atr / avg_atr
            
            if atr_ratio < Config.VOLATILITY_MIN_RATIO:
                return {'valid': False, 'reason': f'ATR too low ({atr_ratio:.2f})'}
            
            if atr_ratio > Config.VOLATILITY_MAX_RATIO:
                return {'valid': False, 'reason': f'ATR too high ({atr_ratio:.2f})'}
            
            # 3. Primary Trend (must be bearish)
            primary_trend = MarketStructure.get_trend_direction(primary_df)
            if primary_trend != 'bearish':
                return {'valid': False, 'reason': f'Primary trend is {primary_trend}'}
            
            # 4. Momentum (MACD negative and falling with STRENGTH)
            macd_hist = primary_df['macd_hist'].iloc[-1]
            macd_hist_prev = primary_df['macd_hist'].iloc[-2]
            macd_hist_2 = primary_df['macd_hist'].iloc[-3]
            
            if macd_hist >= 0:
                return {'valid': False, 'reason': 'MACD histogram not negative'}
            
            if macd_hist > macd_hist_prev:
                return {'valid': False, 'reason': 'MACD momentum not declining'}
            
            # Require strong momentum - not just barely negative
            if abs(macd_hist) < abs(macd_hist_2) * 0.5:
                return {'valid': False, 'reason': 'MACD momentum too weak (losing strength)'}
            
            # 5. Entry Trigger (pullback to EMA21)
            if not MarketStructure.is_price_near_ema(entry_df, 'ema_21', 0.002):
                return {'valid': False, 'reason': 'Price not near EMA21'}
            
            # Check we're not entering right at a recent swing high (resistance)
            swing_high = MarketStructure.find_swing_high(primary_df, lookback=20)
            current_price = entry_df['close'].iloc[-1]
            atr = primary_df['atr'].iloc[-1]
            
            if swing_high and abs(current_price - swing_high) < (0.5 * atr):
                return {'valid': False, 'reason': f'Too close to swing high resistance (${swing_high:.2f})'}
            
            # MACD turning down
            macd_5m_hist = entry_df['macd_hist'].iloc[-1]
            macd_5m_hist_prev = entry_df['macd_hist'].iloc[-2]
            
            if macd_5m_hist >= macd_5m_hist_prev:
                return {'valid': False, 'reason': '5M MACD not turning down'}
            
            return {'valid': True, 'reason': 'All short entry conditions met'}
            
        except Exception as e:
            logger.error(f"Error checking short entry: {e}")
            return {'valid': False, 'reason': f'Error: {str(e)}'}