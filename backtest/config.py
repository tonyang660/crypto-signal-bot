"""
Backtesting configuration - imports from live trading config for consistency
"""
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Import live bot config
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.config import Config

class BacktestConfig:
    """Configuration for backtesting - inherits from live Config"""
    
    # ==================== BACKTEST PERIOD ====================
    # Historical data from Binance: 2021-2024 (4 years)
    # For 15-20 minute backtest, use 6 months of data
    # Add 1 month warmup period for indicators (200+ candles needed for EMA200)
    START_DATE = datetime(2025, 5, 1)  # Start 1 month earlier for warmup
    WARMUP_DATE = datetime(2025, 6, 1)  # Begin actual backtest here (after warmup)
    END_DATE = datetime(2025, 8, 1)
    
    # ==================== INITIAL CONDITIONS ====================
    INITIAL_CAPITAL = Config.INITIAL_CAPITAL  # Use live bot capital
    
    # ==================== EXECUTION SIMULATION ====================
    # Realistic execution parameters
    SLIPPAGE_PERCENT = 0.05  # 0.05% slippage on market orders
    TAKER_FEE = 0.055  # 0.055% Bitget taker fee
    MAKER_FEE = 0.045  # 0.045% Bitget maker fee
    
    # Order execution assumptions
    USE_MARKET_ORDERS = True  # True = market (guaranteed fill, more slippage)
    STOP_LOSS_SLIPPAGE = 0.1  # Extra slippage on stop losses (0.1%)
    
    # Conservative execution - if candle hits both TP and SL
    CONSERVATIVE_MODE = True  # True = assume SL hit first (worst case)
    
    # ==================== TRADING PAIRS ====================
    # Dynamically determined based on available data for date range
    # Set to None to auto-detect all available symbols, or provide a list to filter
    SYMBOLS = None  # Auto-detect all available symbols
    
    # Optional: Restrict to specific symbols (None = use all available)
    SYMBOL_FILTER = None  # e.g., ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'] or None for all
    
    # Cache for dynamically loaded symbols
    _symbols_cache = None
    
    @classmethod
    def get_symbols(cls):
        """Get list of symbols with complete data coverage for backtest period"""
        # Return cached value if already computed
        if cls._symbols_cache is not None:
            return cls._symbols_cache
        
        # If SYMBOLS is explicitly set (not None), use it
        if cls.SYMBOLS is not None:
            cls._symbols_cache = cls.SYMBOLS
            return cls._symbols_cache
        
        # Dynamically determine available symbols
        try:
            from backtest.check_data_availability import DataAvailabilityChecker
            checker = DataAvailabilityChecker()
            
            available_symbols = checker.get_available_symbols_for_range(
                start_date=cls.START_DATE,
                end_date=cls.END_DATE,
                timeframes=[
                    cls.HTF_TIMEFRAME,
                    cls.PRIMARY_TIMEFRAME,
                    cls.ENTRY_TIMEFRAME
                ]
            )
            
            # Apply filter if specified
            if cls.SYMBOL_FILTER is not None:
                available_symbols = [s for s in cls.SYMBOL_FILTER if s in available_symbols]
            
            cls._symbols_cache = available_symbols
            return cls._symbols_cache
            
        except Exception as e:
            # Fallback to a default list if checker fails
            print(f"Warning: Could not auto-detect symbols ({e}), using fallback list")
            fallback = [
                'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 
                'ADAUSDT', 'LINKUSDT', 'AVAXUSDT', 'DOGEUSDT', 'HBARUSDT',
                'XLMUSDT', 'SUIUSDT'
            ]
            cls._symbols_cache = fallback
            return cls._symbols_cache
    
    # ==================== TIMEFRAMES ====================
    # Must match live bot
    HTF_TIMEFRAME = Config.HTF_TIMEFRAME
    PRIMARY_TIMEFRAME = Config.PRIMARY_TIMEFRAME
    ENTRY_TIMEFRAME = Config.ENTRY_TIMEFRAME
    
    # ==================== STRATEGY PARAMETERS ====================
    # Import all strategy parameters from live config
    SIGNAL_THRESHOLD_NORMAL = Config.SIGNAL_THRESHOLD_NORMAL
    SIGNAL_THRESHOLD_DRAWDOWN = Config.SIGNAL_THRESHOLD_DRAWDOWN
    
    # ==================== RISK MANAGEMENT ====================
    # Use same parameters as live bot
    RISK_PER_TRADE = Config.RISK_PER_TRADE
    MAX_DAILY_LOSS = Config.MAX_DAILY_LOSS
    MAX_WEEKLY_LOSS = Config.MAX_WEEKLY_LOSS
    MAX_CONSECUTIVE_LOSSES = Config.MAX_CONSECUTIVE_LOSSES
    MAX_TOTAL_ACTIVE_SIGNALS = 4  # Same as live bot
    COOLDOWN_HOURS = 12  # After max consecutive losses
    
    # ==================== ADAPTIVE STOP PARAMETERS ====================
    # Import adaptive stop settings from live config
    ADAPTIVE_STOP_ENABLED = Config.ADAPTIVE_STOP_ENABLED
    ADAPTIVE_STOP_MIN_PROFIT_R = Config.ADAPTIVE_STOP_MIN_PROFIT_R
    ADAPTIVE_STOP_VOLATILITY_SPIKE = Config.ADAPTIVE_STOP_VOLATILITY_SPIKE
    ADAPTIVE_STOP_REGIME_CHANGE = Config.ADAPTIVE_STOP_REGIME_CHANGE
    ADAPTIVE_STOP_BREAKEVEN_BUFFER = Config.ADAPTIVE_STOP_BREAKEVEN_BUFFER
    ADAPTIVE_STOP_PARTIAL_PROTECTION = Config.ADAPTIVE_STOP_PARTIAL_PROTECTION
    
    # ==================== WALK-FORWARD TESTING ====================
    # Split data for validation
    TRAIN_SPLIT = 0.7  # 70% for optimization/training
    TEST_SPLIT = 0.3   # 30% for validation
    
    ENABLE_WALK_FORWARD = False  # Disabled by default
    
    # ==================== LOGGING ====================
    ENABLE_LOGGING = False  # Set to False to disable all logging for faster backtest
    LOG_LEVEL = 'INFO'  # 'DEBUG' for detailed candle-by-candle
    SAVE_EQUITY_CURVE = True
    SAVE_TRADE_LOG = True
    SAVE_METRICS = True
    SHOW_PROGRESS_BAR = True  # Show progress bar during backtest
    
    # ==================== OUTPUT ====================
    RESULTS_DIR = 'backtest/results'
    DATA_DIR = 'backtest/data'
    
    @classmethod
    def get_date_range_string(cls):
        """Get formatted date range for filenames"""
        return f"{cls.START_DATE.strftime('%Y%m%d')}_{cls.END_DATE.strftime('%Y%m%d')}"
