import pandas as pd
from typing import Dict, Optional
from loguru import logger
from src.analysis.market_structure import MarketStructure
from src.analysis.regime_detector import RegimeDetector
from src.core.config import Config

class EntryLogic:
    """Entry condition validation for long and short positions"""
    
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
            
            # 1. HTF Bias Filter (4H must be bullish)
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            if htf_trend != 'bullish':
                return {'valid': False, 'reason': f'HTF trend is {htf_trend}, not bullish'}
            
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
            
            # 4. Momentum Confirmation (MACD histogram)
            macd_hist = primary_df['macd_hist'].iloc[-1]
            macd_hist_prev = primary_df['macd_hist'].iloc[-2]
            
            if macd_hist <= 0:
                return {'valid': False, 'reason': 'MACD histogram not positive'}
            
            if macd_hist < macd_hist_prev:
                return {'valid': False, 'reason': 'MACD momentum declining'}
            
            # 5. Entry Trigger (5M pullback to EMA21)
            if not MarketStructure.is_price_near_ema(entry_df, 'ema_21', 0.002):
                return {'valid': False, 'reason': 'Price not near EMA21'}
            
            # Must be bullish candle
            last_close = entry_df['close'].iloc[-1]
            last_open = entry_df['open'].iloc[-1]
            
            if last_close <= last_open:
                return {'valid': False, 'reason': 'Not a bullish candle'}
            
            # MACD turning up on 5M
            macd_5m_hist = entry_df['macd_hist'].iloc[-1]
            macd_5m_hist_prev = entry_df['macd_hist'].iloc[-2]
            
            if macd_5m_hist <= macd_5m_hist_prev:
                return {'valid': False, 'reason': '5M MACD not turning up'}
            
            # 6. Volume Confirmation
            volume = entry_df['volume'].iloc[-1]
            volume_sma = entry_df['volume_sma'].iloc[-1]
            
            if volume <= volume_sma:
                return {'valid': False, 'reason': 'Insufficient volume'}
            
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
            
            # 1. HTF Bias (must be bearish)
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            if htf_trend != 'bearish':
                return {'valid': False, 'reason': f'HTF trend is {htf_trend}, not bearish'}
            
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
            
            # 4. Momentum (MACD negative and falling)
            macd_hist = primary_df['macd_hist'].iloc[-1]
            macd_hist_prev = primary_df['macd_hist'].iloc[-2]
            
            if macd_hist >= 0:
                return {'valid': False, 'reason': 'MACD histogram not negative'}
            
            if macd_hist > macd_hist_prev:
                return {'valid': False, 'reason': 'MACD momentum not declining'}
            
            # 5. Entry Trigger (pullback to EMA21)
            if not MarketStructure.is_price_near_ema(entry_df, 'ema_21', 0.002):
                return {'valid': False, 'reason': 'Price not near EMA21'}
            
            # Bearish candle
            last_close = entry_df['close'].iloc[-1]
            last_open = entry_df['open'].iloc[-1]
            
            if last_close >= last_open:
                return {'valid': False, 'reason': 'Not a bearish candle'}
            
            # MACD turning down
            macd_5m_hist = entry_df['macd_hist'].iloc[-1]
            macd_5m_hist_prev = entry_df['macd_hist'].iloc[-2]
            
            if macd_5m_hist >= macd_5m_hist_prev:
                return {'valid': False, 'reason': '5M MACD not turning down'}
            
            # 6. Volume
            volume = entry_df['volume'].iloc[-1]
            volume_sma = entry_df['volume_sma'].iloc[-1]
            
            if volume <= volume_sma:
                return {'valid': False, 'reason': 'Insufficient volume'}
            
            return {'valid': True, 'reason': 'All short entry conditions met'}
            
        except Exception as e:
            logger.error(f"Error checking short entry: {e}")
            return {'valid': False, 'reason': f'Error: {str(e)}'}