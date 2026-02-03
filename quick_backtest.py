"""
Quick Backtest Runner

Usage:
  python quick_backtest.py                    # Full backtest (1-2 years)
  python quick_backtest.py --days 30          # Last 30 days only
  python quick_backtest.py --symbol BTCUSDT   # Single symbol
  python quick_backtest.py --walk-forward     # Walk-forward test
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from backtest.config import BacktestConfig
from backtest.data_fetcher import HistoricalDataFetcher
from backtest.engine import BacktestEngine

def main():
    parser = argparse.ArgumentParser(description='Quick backtest runner')
    parser.add_argument('--days', type=int, help='Number of days to backtest (from today)')
    parser.add_argument('--symbol', type=str, help='Single symbol to test')
    parser.add_argument('--walk-forward', action='store_true', help='Run walk-forward test')
    
    args = parser.parse_args()
    
    # Adjust config based on args
    if args.days:
        BacktestConfig.END_DATE = datetime.now()
        BacktestConfig.START_DATE = BacktestConfig.END_DATE - timedelta(days=args.days)
        logger.info(f"Testing last {args.days} days")
    
    if args.symbol:
        BacktestConfig.SYMBOLS = [args.symbol]
        logger.info(f"Testing single symbol: {args.symbol}")
    
    if args.walk_forward:
        # Run walk-forward test
        from backtest.walk_forward import run_walk_forward
        run_walk_forward()
    else:
        # Run regular backtest
        from backtest.run_backtest import main as run_main
        run_main()

if __name__ == '__main__':
    main()
