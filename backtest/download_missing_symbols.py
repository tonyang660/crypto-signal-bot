"""
Download missing data files for specific symbols

Usage:
    python backtest/download_missing_symbols.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.download_binance_data import BinanceDataDownloader
from loguru import logger
import time

def main():
    """Download data only for missing symbols"""
    
    # Symbols that are missing from data_binance
    MISSING_SYMBOLS = [
        'BGBUSDT',      # May have limited availability
        'CROUSDT',
        'NEARUSDT',
        'PEPEUSDT',     # Newer (2023+)
        'SEIUSDT',
        'SHIBUSDT',
        'XDCUSDT',      # May have limited availability
    ]
    
    INTERVALS = ['5m', '15m', '1h', '4h']
    START_YEAR = 2021
    MARKET_TYPE = 'futures'  # Try futures first for better availability
    
    downloader = BinanceDataDownloader()
    
    logger.info("\n" + "="*70)
    logger.info("DOWNLOADING MISSING SYMBOLS DATA")
    logger.info("="*70)
    logger.info(f"Symbols to download: {', '.join(MISSING_SYMBOLS)}")
    logger.info(f"Timeframes: {', '.join(INTERVALS)}")
    logger.info(f"Starting from: {START_YEAR}")
    logger.info(f"Market type: {MARKET_TYPE}")
    logger.info("="*70 + "\n")
    logger.info("⚠️  NOTE: This may take 5-15 minutes depending on data availability")
    logger.info("Press Ctrl+C to cancel\n")
    
    time.sleep(3)
    
    downloader.download_all_for_backtesting(
        symbols=MISSING_SYMBOLS,
        intervals=INTERVALS,
        start_year=START_YEAR,
        market_type=MARKET_TYPE
    )
    
    logger.info("\n" + "="*70)
    logger.info("✅ DOWNLOAD COMPLETE!")
    logger.info("="*70)
    logger.info("Missing symbols data has been downloaded.")
    logger.info("Run 'python backtest/check_missing_data.py' to verify.")


if __name__ == "__main__":
    main()
