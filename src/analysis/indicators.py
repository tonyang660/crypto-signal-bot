import pandas as pd
import numpy as np
from typing import Dict
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator

class Indicators:
    """Technical indicator calculations"""
    
    @staticmethod
    def calculate_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
        """Calculate Exponential Moving Average"""
        return EMAIndicator(close=df[column], window=period).ema_indicator()
    
    @staticmethod
    def calculate_macd(
        df: pd.DataFrame, 
        fast: int = 12, 
        slow: int = 26, 
        signal: int = 9
    ) -> Dict:
        """Calculate MACD"""
        macd = MACD(
            close=df['close'],
            window_fast=fast,
            window_slow=slow,
            window_sign=signal
        )
        
        return {
            'macd': macd.macd(),
            'signal': macd.macd_signal(),
            'histogram': macd.macd_diff()
        }
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        atr = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=period
        )
        return atr.average_true_range()
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        rsi = RSIIndicator(close=df['close'], window=period)
        return rsi.rsi()
    
    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ADX for trend strength"""
        adx = ADXIndicator(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=period
        )
        return adx.adx().iloc[-1]
    
    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add all required indicators to dataframe"""
        from src.core.config import Config
        
        # EMAs
        df['ema_21'] = Indicators.calculate_ema(df, Config.EMA_FAST)
        df['ema_50'] = Indicators.calculate_ema(df, Config.EMA_MEDIUM)
        df['ema_200'] = Indicators.calculate_ema(df, Config.EMA_SLOW)
        
        # MACD
        macd_data = Indicators.calculate_macd(
            df, 
            Config.MACD_FAST, 
            Config.MACD_SLOW, 
            Config.MACD_SIGNAL
        )
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal']
        df['macd_hist'] = macd_data['histogram']
        
        # ATR
        df['atr'] = Indicators.calculate_atr(df, Config.ATR_PERIOD)
        df['atr_sma'] = df['atr'].rolling(20).mean()
        
        # RSI
        df['rsi'] = Indicators.calculate_rsi(df, Config.RSI_PERIOD)
        
        # Volume SMA
        df['volume_sma'] = df['volume'].rolling(20).mean()
        
        return df