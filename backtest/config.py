"""
Backtesting configuration - separate from live trading config
"""
from datetime import datetime, timedelta

class BacktestConfig:
    """Configuration for backtesting"""
    
    # ==================== BACKTEST PERIOD ====================
    # Historical data from Binance: 2021-2024 (4 years)
    START_DATE = datetime(2023, 1, 1)  # Start date
    END_DATE = datetime(2024, 12, 31)  # End date
    
    # ==================== INITIAL CONDITIONS ====================
    INITIAL_CAPITAL = 2000.0
    
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
    # Test on same pairs as live trading
    SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'XLMUSDT', 'ADAUSDT', 'DOGEUSDT', 'SUIUSDT', 'HBARUSDT', 'HYPEUSDT', 'XMRUSDT', 'LINKUSDT', 'AVAXUSDT', 'PEPEUSDT']

    # ==================== TIMEFRAMES ====================
    # Must match live bot
    HTF_TIMEFRAME = '4h'
    PRIMARY_TIMEFRAME = '15m'
    ENTRY_TIMEFRAME = '5m'
    
    # ==================== WALK-FORWARD TESTING ====================
    # Split data for validation
    TRAIN_SPLIT = 0.7  # 70% for optimization/training
    TEST_SPLIT = 0.3   # 30% for validation
    
    ENABLE_WALK_FORWARD = True
    
    # ==================== RISK MANAGEMENT ====================
    # Use same parameters as live bot
    RISK_PER_TRADE = 0.01  # 1%
    MAX_DAILY_LOSS = None  # Disabled (using consecutive loss instead)
    MAX_WEEKLY_LOSS = 0.06  # 6%
    MAX_CONSECUTIVE_LOSSES = 3
    COOLDOWN_HOURS = 4
    
    # ==================== POSITION LIMITS ====================
    MAX_TOTAL_ACTIVE_SIGNALS = 3
    MAX_SIGNALS_PER_PAIR = 1
    MAX_BTC_SIGNALS = 1
    
    # ==================== SIGNAL SCORING ====================
    SIGNAL_THRESHOLD_NORMAL = 70
    SIGNAL_THRESHOLD_DRAWDOWN = 85
    
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
