"""
Import historical data from downloaded CSV files and convert to backtest format

This script converts daily historical crypto data from various sources
(CoinGecko, CryptoDataDownload, etc.) into the format needed for backtesting.
"""

import pandas as pd
from pathlib import Path
from loguru import logger
import sys

class HistoricalDataImporter:
    """Import and convert historical CSV data for backtesting"""
    
    def __init__(self, downloads_dir: str = None):
        if downloads_dir is None:
            downloads_dir = Path.home() / "Downloads"
        self.downloads_dir = Path(downloads_dir)
        self.output_dir = Path("backtest/data_historical")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def import_coin_csv(self, filename: str, symbol: str) -> pd.DataFrame:
        """
        Import a coin_*.csv file and convert to backtest format
        
        Args:
            filename: Name of CSV file (e.g., 'coin_Bitcoin.csv')
            symbol: Symbol to use (e.g., 'BTCUSDT')
        
        Returns:
            DataFrame with OHLCV data
        """
        filepath = self.downloads_dir / filename
        
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return None
        
        logger.info(f"Importing {filename} as {symbol}")
        
        # Read CSV
        df = pd.read_csv(filepath)
        
        # Convert Date column to datetime and set as index
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        
        # Select and rename columns to match backtest format
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Ensure numeric types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remove any NaN values
        df = df.dropna()
        
        # Sort by date (ascending)
        df = df.sort_index()
        
        logger.info(f"✓ Loaded {len(df)} daily candles from {df.index.min().date()} to {df.index.max().date()}")
        
        return df
    
    def save_to_backtest_format(self, df: pd.DataFrame, symbol: str, timeframe: str = '1d'):
        """Save DataFrame in backtest-ready format"""
        start_date = df.index.min().strftime('%Y%m%d')
        end_date = df.index.max().strftime('%Y%m%d')
        
        filename = f"{symbol}_{timeframe}_{start_date}_{end_date}.csv"
        filepath = self.output_dir / filename
        
        df.to_csv(filepath)
        logger.info(f"✓ Saved to {filepath}")
        
        return filepath
    
    def import_all(self):
        """Import all available coin CSV files"""
        
        # Mapping of CSV files to trading symbols
        coin_mapping = {
            'coin_Bitcoin.csv': 'BTCUSDT',
            'coin_Ethereum.csv': 'ETHUSDT',
            'coin_ChainLink.csv': 'LINKUSDT',
            'coin_Cardano.csv': 'ADAUSDT',
            # Add more as you download them
        }
        
        imported = []
        
        for filename, symbol in coin_mapping.items():
            df = self.import_coin_csv(filename, symbol)
            if df is not None:
                filepath = self.save_to_backtest_format(df, symbol, timeframe='1d')
                imported.append((symbol, len(df), df.index.min(), df.index.max()))
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("IMPORT SUMMARY")
        logger.info("="*70)
        for symbol, count, start, end in imported:
            logger.info(f"{symbol:10} {count:5} candles  {start.date()} to {end.date()}")
        
        logger.info(f"\n✅ Imported {len(imported)} symbols")
        logger.info(f"📁 Data saved to: {self.output_dir}")
        
        logger.info("\n" + "="*70)
        logger.info("IMPORTANT NOTE: This is DAILY data")
        logger.info("="*70)
        logger.info("The imported data is daily candles, but your strategy uses intraday")
        logger.info("timeframes (4h, 15m, 5m). For proper backtesting, you would need:")
        logger.info("  1. Intraday historical data from Binance or other sources")
        logger.info("  2. Or adjust strategy to work with daily timeframe")
        logger.info("  3. Or use this data for high-level validation only")

def main():
    """Import historical data from downloads"""
    logger.info("="*70)
    logger.info("HISTORICAL DATA IMPORT")
    logger.info("="*70)
    
    importer = HistoricalDataImporter()
    importer.import_all()

if __name__ == "__main__":
    main()
