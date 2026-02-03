"""
Load historical data from Binance CSV files for backtesting

Replaces the old Bitget API data fetcher with static historical data
"""

import pandas as pd
from pathlib import Path
from loguru import logger
from datetime import datetime
from typing import Dict, List

class BinanceDataLoader:
    """Load historical data from downloaded Binance CSV files"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).parent / "data_binance"
        self.data_dir = Path(data_dir)
        
        if not self.data_dir.exists():
            raise FileNotFoundError(
                f"Data directory not found: {self.data_dir}\n"
                "Run backtest/download_binance_data.py to download historical data"
            )
    
    def load_symbol_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        Load historical data for a symbol and timeframe
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Interval (e.g., '5m', '15m', '4h')
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            DataFrame with OHLCV data
        """
        # Find matching file
        pattern = f"{symbol}_{timeframe}_*.csv"
        files = list(self.data_dir.glob(pattern))
        
        if not files:
            logger.warning(f"No data file found for {symbol} {timeframe}")
            return pd.DataFrame()
        
        # Use the first matching file (should only be one)
        filepath = files[0]
        
        logger.debug(f"Loading {filepath.name}")
        
        # Read CSV
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        
        # Filter by date range if specified
        if start_date is not None:
            df = df[df.index >= start_date]
        
        if end_date is not None:
            df = df[df.index <= end_date]
        
        logger.debug(f"Loaded {len(df)} candles for {symbol} {timeframe}")
        
        return df
    
    def load_all_data(
        self,
        symbols: List[str],
        timeframes: List[str],
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Load data for multiple symbols and timeframes
        
        Args:
            symbols: List of trading pairs
            timeframes: List of intervals
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            Dict[symbol][timeframe] = DataFrame
        """
        all_data = {}
        
        for symbol in symbols:
            logger.info(f"Loading {symbol} data...")
            all_data[symbol] = {}
            
            for timeframe in timeframes:
                df = self.load_symbol_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if not df.empty:
                    all_data[symbol][timeframe] = df
                    logger.info(f"  {timeframe}: {len(df)} candles")
                else:
                    logger.warning(f"  {timeframe}: No data")
        
        return all_data


# For backward compatibility with existing backtest scripts
class HistoricalDataFetcher:
    """Compatibility wrapper - now loads from Binance files instead of fetching from API"""
    
    def __init__(self):
        self.loader = BinanceDataLoader()
        logger.info("Using Binance historical data (downloaded CSV files)")
    
    def fetch_all_data(
        self,
        symbols: list,
        start_date: datetime,
        end_date: datetime,
        timeframes: list,
        force_refresh: bool = False
    ) -> dict:
        """Load data (compatible with old API)"""
        logger.info(f"Loading data from {start_date.date()} to {end_date.date()}")
        
        return self.loader.load_all_data(
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date
        )
    
    def fetch_all_symbols(
        self,
        timeframes: list,
        force_refresh: bool = False
    ) -> dict:
        """Load data for all symbols (compatible with old API)"""
        from backtest.config import BacktestConfig
        
        logger.info(f"Loading data from {BacktestConfig.START_DATE.date()} to {BacktestConfig.END_DATE.date()}")
        
        return self.loader.load_all_data(
            symbols=BacktestConfig.SYMBOLS,
            timeframes=timeframes,
            start_date=BacktestConfig.START_DATE,
            end_date=BacktestConfig.END_DATE
        )
