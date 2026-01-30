import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
from .bitget_client import BitGetClient
from .config import Config

class DataManager:
    """Manage OHLCV data fetching with caching"""
    
    def __init__(self):
        self.client = BitGetClient()
        self.cache: Dict[str, pd.DataFrame] = {}
        self.cache_expiry: Dict[str, datetime] = {}
    
    def get_data(
        self, 
        symbol: str, 
        timeframe: str, 
        limit: int = 500,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Get OHLCV data with caching
        
        Cache expires based on timeframe:
        - 5m: 1 minute
        - 15m: 3 minutes
        - 1h: 5 minutes
        - 4h: 15 minutes
        """
        cache_key = f"{symbol}_{timeframe}"
        now = datetime.now()
        
        # Check cache validity
        if not force_refresh and cache_key in self.cache:
            expiry = self.cache_expiry.get(cache_key)
            if expiry and now < expiry:
                logger.debug(f"Using cached data for {cache_key}")
                return self.cache[cache_key]
        
        # Fetch fresh data
        logger.debug(f"Fetching fresh data for {cache_key}")
        df = self.client.fetch_ohlcv(symbol, timeframe, limit)
        
        if not df.empty:
            # Store in cache
            self.cache[cache_key] = df
            
            # Set expiry based on timeframe
            cache_duration = self._get_cache_duration(timeframe)
            self.cache_expiry[cache_key] = now + cache_duration
        
        return df
    
    def get_multi_timeframe_data(
        self, 
        symbol: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Get data for all required timeframes
        
        Returns:
            Dict with 'htf', 'primary', 'entry' keys
        """
        return {
            'htf': self.get_data(symbol, Config.HTF_TIMEFRAME, 200),
            'primary': self.get_data(symbol, Config.PRIMARY_TIMEFRAME, 500),
            'entry': self.get_data(symbol, Config.ENTRY_TIMEFRAME, 200)
        }
    
    def clear_cache(self, symbol: Optional[str] = None):
        """Clear cache for specific symbol or all"""
        if symbol:
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(symbol)]
            for key in keys_to_remove:
                del self.cache[key]
                del self.cache_expiry[key]
            logger.info(f"Cache cleared for {symbol}")
        else:
            self.cache.clear()
            self.cache_expiry.clear()
            logger.info("All cache cleared")
    
    def _get_cache_duration(self, timeframe: str) -> timedelta:
        """Determine cache duration based on timeframe"""
        durations = {
            '1m': timedelta(seconds=30),
            '5m': timedelta(minutes=1),
            '15m': timedelta(minutes=3),
            '30m': timedelta(minutes=5),
            '1h': timedelta(minutes=5),
            '4h': timedelta(minutes=15),
            '1d': timedelta(minutes=30)
        }
        
        return durations.get(timeframe, timedelta(minutes=5))