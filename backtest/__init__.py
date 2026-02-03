"""
Backtesting Framework for Signal Bot

Professional-grade backtesting following 12 best-practice principles.
"""

from .config import BacktestConfig
from .data_loader import HistoricalDataFetcher, BinanceDataLoader
from .engine import BacktestEngine, Position, Trade

__all__ = [
    'BacktestConfig',
    'HistoricalDataFetcher',
    'BinanceDataLoader',
    'BacktestEngine',
    'Position',
    'Trade'
]
