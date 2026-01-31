import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Central configuration management"""
    
    # ==================== API CREDENTIALS ====================
    BITGET_API_KEY = os.getenv('BITGET_API_KEY')
    BITGET_SECRET_KEY = os.getenv('BITGET_SECRET_KEY')
    BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
    
    # Discord
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
    
    # ==================== CAPITAL & RISK ====================
    INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '2000') or 2000)
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.01') or 0.01)  # 1%
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '0.02') or 0.02)  # 2%
    MAX_WEEKLY_LOSS = float(os.getenv('MAX_WEEKLY_LOSS', '0.06') or 0.06)  # 6%
    MAX_LEVERAGE = float(os.getenv('MAX_LEVERAGE', '15.0') or 15.0)
    MAX_CONSECUTIVE_LOSSES = 3
    
    # ==================== TRADING PAIRS ====================
    TRADING_PAIRS: List[str] = os.getenv(
        'TRADING_PAIRS', 
        'BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT'
    ).split(',')
    
    # BitGet specific symbol format
    @classmethod
    def format_symbol(cls, symbol: str) -> str:
        """Convert standard symbol to BitGet format"""
        # BitGet uses format like 'BTCUSDT_UMCBL' for perpetual futures
        if not symbol.endswith('_UMCBL'):
            return f"{symbol}_UMCBL"
        return symbol
    
    # ==================== TIMEFRAMES ====================
    PRIMARY_TIMEFRAME = os.getenv('PRIMARY_TIMEFRAME', '15m')
    HTF_TIMEFRAME = os.getenv('HTF_TIMEFRAME', '4h')
    ENTRY_TIMEFRAME = os.getenv('ENTRY_TIMEFRAME', '5m')
    
    # BitGet timeframe mapping
    TIMEFRAME_MAP = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1H',
        '4h': '4H',
        '1d': '1D'
    }
    
    # ==================== STRATEGY PARAMETERS ====================
    # Indicators
    ATR_PERIOD = 14
    ATR_STOP_MULTIPLIER = 1.5
    EMA_FAST = 21
    EMA_MEDIUM = 50
    EMA_SLOW = 200
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    RSI_PERIOD = 14
    
    # Signal Quality
    SIGNAL_THRESHOLD_NORMAL = 70
    SIGNAL_THRESHOLD_DRAWDOWN = 85
    SIGNAL_THRESHOLD_HOT_STREAK = 65
    
    # Take Profit Ratios (as Risk multiples)
    TP1_RATIO = 1.5
    TP1_CLOSE_PERCENT = 50  # Close 50% at TP1
    TP2_RATIO = 2.5
    TP2_CLOSE_PERCENT = 30  # Close 30% at TP2
    TP3_RATIO = 3.5
    TP3_CLOSE_PERCENT = 20  # Trail remaining 20%
    
    # Volatility Filters
    VOLATILITY_MIN_RATIO = 0.7
    VOLATILITY_MAX_RATIO = 2.0
    
    # ==================== SIGNAL MANAGEMENT ====================
    MAX_ACTIVE_SIGNALS_PER_PAIR = 1
    MAX_ACTIVE_BTC_SIGNALS = 1  # Only 1 BTC signal at a time
    MAX_TOTAL_ACTIVE_SIGNALS = 3
    
    # ==================== SCANNING ====================
    SCAN_INTERVAL_SECONDS = int(os.getenv('SCAN_INTERVAL_SECONDS', 300))  # 5 minutes
    
    # ==================== FILE PATHS ====================
    DATA_DIR = 'data'
    ACTIVE_SIGNALS_FILE = os.path.join(DATA_DIR, 'signals_active.json')
    HISTORY_SIGNALS_FILE = os.path.join(DATA_DIR, 'signals_history.json')
    PERFORMANCE_FILE = os.path.join(DATA_DIR, 'performance.json')
    LOG_FILE = 'logs/bot.log'
    
    # ==================== ENVIRONMENT ====================
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # ==================== VALIDATION ====================
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        errors = []
        
        if not cls.BITGET_API_KEY:
            errors.append("BITGET_API_KEY not set")
        if not cls.BITGET_SECRET_KEY:
            errors.append("BITGET_SECRET_KEY not set")
        if not cls.BITGET_PASSPHRASE:
            errors.append("BITGET_PASSPHRASE not set")
        if not cls.DISCORD_WEBHOOK_URL:
            errors.append("DISCORD_WEBHOOK_URL not set")
        
        if not (0 < cls.RISK_PER_TRADE <= 0.02):
            errors.append("RISK_PER_TRADE must be between 0 and 2%")
        
        if cls.MAX_LEVERAGE > 15:
            errors.append("MAX_LEVERAGE should not exceed 15×")
        
        if len(cls.TRADING_PAIRS) == 0:
            errors.append("No trading pairs specified")
        
        # Ensure data directory exists
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
        
        print("✓ Configuration validated successfully")
        print(f"  - Trading pairs: {', '.join(cls.TRADING_PAIRS)}")
        print(f"  - Risk per trade: {cls.RISK_PER_TRADE * 100}%")
        print(f"  - Max leverage: {cls.MAX_LEVERAGE}×")