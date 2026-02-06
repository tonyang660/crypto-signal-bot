"""
Paper Trading Execution Module

Simulates realistic order execution without actual exchange API calls.
Tracks virtual positions, applies fees, slippage, and funding rates.
"""

from .paper_engine import PaperTradingEngine
from .margin_calculator import MarginCalculator
from .paper_account import PaperAccount

__all__ = ['PaperTradingEngine', 'MarginCalculator', 'PaperAccount']
