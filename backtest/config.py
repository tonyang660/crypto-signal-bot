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
    START_DATE = datetime(2024, 5, 1)  # Start 1 month earlier for warmup
    WARMUP_DATE = datetime(2024, 6, 1)  # Begin actual backtest here (after warmup)
    END_DATE = datetime(2024, 12, 31)
    
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
    # Use only symbols with available data in backtest/data_binance/
    # Missing: AAVEUSDT, UNIUSDT, TRXUSDT, TONUSDT, APTUSDT
    SYMBOLS = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 
        'ADAUSDT', 'LINKUSDT', 'AVAXUSDT', 'DOGEUSDT', 'HBARUSDT',
        'XLMUSDT', 'SUIUSDT'
    ]
    
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
    MAX_TOTAL_ACTIVE_SIGNALS = 3  # Same as live bot
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
    LOG_LEVEL = 'INFO'  # 'DEBUG' for detailed candle-by-candle
    SAVE_EQUITY_CURVE = True
    SAVE_TRADE_LOG = True
    SAVE_METRICS = True
    
    # ==================== OUTPUT ====================
    RESULTS_DIR = 'backtest/results'
    DATA_DIR = 'backtest/data'
    
    @classmethod
    def get_date_range_string(cls):
        """Get formatted date range for filenames"""
        return f"{cls.START_DATE.strftime('%Y%m%d')}_{cls.END_DATE.strftime('%Y%m%d')}"
