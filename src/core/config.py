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
    ACTIVE_POSITIONS_WEBHOOK_URL = os.getenv('ACTIVE_POSITIONS_WEBHOOK_URL')
    
    # ==================== TIMEZONE ====================
    # Timezone for logs and reports (defaults to US Eastern)
    TIMEZONE = os.getenv('TIMEZONE', 'America/New_York')
    
    # ==================== CAPITAL & RISK ====================
    INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '2000') or 2000)
    
    # Dynamic risk management based on capital tiers
    # These are baseline values - actual values are calculated dynamically
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.01') or 0.01)  # Baseline: 1%
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '0.02') or 0.02)  # Baseline: 2%
    MAX_WEEKLY_LOSS = float(os.getenv('MAX_WEEKLY_LOSS', '0.06') or 0.06)  # Baseline: 6%
    MAX_LEVERAGE = float(os.getenv('MAX_LEVERAGE', '15.0') or 15.0)
    MAX_CONSECUTIVE_LOSSES = 3
    
    @staticmethod
    def get_dynamic_risk_params(equity: float) -> dict:
        """
        Calculate dynamic risk parameters based on capital tier
        
        Equity <3000$: 1.0% risk/trade, 2.0% daily loss, 6.0% weekly loss
        3000-5000$: 0.8% risk/trade, 1.6% daily loss, 5.0% weekly loss
        5000-7000$: 0.7% risk/trade, 1.4% daily loss, 4.5% weekly loss
        7000-10,000$: 0.6% risk/trade, 1.2% daily loss, 4.2% weekly loss
        10,000-20,000$: 0.5% risk/trade, 1.0% daily loss, 3.9% weekly loss
        20,000+: 0.4% risk/trade, 1.0% daily loss, 3.6% weekly loss
        
        Returns:
            dict with 'risk_per_trade', 'max_daily_loss', 'max_weekly_loss'
        """
        if equity < 3000:
            return {
                'risk_per_trade': 0.010,  # 1.0%
                'max_daily_loss': 0.020,  # 2.0%
                'max_weekly_loss': 0.060  # 6.0%
            }
        elif equity < 5000:
            return {
                'risk_per_trade': 0.008,  # 0.8%
                'max_daily_loss': 0.016,  # 1.6%
                'max_weekly_loss': 0.050  # 5.0%
            }
        elif equity < 7000:
            return {
                'risk_per_trade': 0.007,  # 0.7%
                'max_daily_loss': 0.014,  # 1.4%
                'max_weekly_loss': 0.045  # 4.5%
            }
        elif equity < 10000:
            return {
                'risk_per_trade': 0.006,  # 0.6%
                'max_daily_loss': 0.012,  # 1.2%
                'max_weekly_loss': 0.042  # 4.2%
            }
        elif equity < 20000:
            return {
                'risk_per_trade': 0.005,  # 0.5%
                'max_daily_loss': 0.010,  # 1.0%
                'max_weekly_loss': 0.039  # 3.9%
            }
        else:  # 20,000+
            return {
                'risk_per_trade': 0.004,  # 0.4%
                'max_daily_loss': 0.010,  # 1.0%
                'max_weekly_loss': 0.036  # 3.6%
            }
    
    # ==================== TRADING PAIRS ====================
    TRADING_PAIRS: List[str] = os.getenv(
        'TRADING_PAIRS', 
        'BTCUSDT,ETHUSDT,BNBUSDT,XRPUSDT,SOLUSDT,DOGEUSDT,ADAUSDT,HYPEUSDT,LINKUSDT,XLMUSDT,LTCUSDT,AVAXUSDT,SUIUSDT,ZECUSDT,HBARUSDT,SHIBUSDT,CROUSDT,DOTUSDT,UNIUSDT,BGBUSDT,TAOUSDT,AAVEUSDT,PEPEUSDT,ONDOUSDT,POLUSDT,APTUSDT,QNTUSDT,FILUSDT,RENDERUSDT,VETUSDT,ARBUSDT,XDCUSDT,JUPUSDT,NEARUSDT,SEIUSDT'
    ).split(',')
    
    # ==================== CORRELATION GROUPS ====================
    # Group pairs by correlation to prevent overexposure
    CORRELATION_GROUPS = {
        'btc_followers': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'LTCUSDT'],  # High BTC correlation 0.85+
        'major_alts': ['SOLUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT', 'UNIUSDT'],  # Major altcoins
        'layer1': ['APTUSDT', 'SUIUSDT', 'HBARUSDT', 'ARBUSDT', 'NEARUSDT', 'SEIUSDT'],  # L1 platforms
        'defi': ['AAVEUSDT', 'UNIUSDT', 'JUPUSDT', 'RENDERUSDT'],  # DeFi sector
        'meme': ['DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT'],  # Meme coins
        'privacy': ['ZECUSDT'],  # Privacy coins
        'ai_sector': ['TAOUSDT', 'RENDERUSDT', 'HYPEUSDT'],  # AI/ML sector
        'gaming_rwa': ['ONDOUSDT', 'BGBUSDT', 'FILUSDT', 'QNTUSDT'],  # Gaming & RWA
        'independent': ['XRPUSDT', 'XLMUSDT', 'CROUSDT', 'POLUSDT', 'VETUSDT', 'XDCUSDT']  # Lower correlation
    }
    
    # Maximum concurrent signals per correlation group
    MAX_CORRELATED_SIGNALS = 2  # Prevent too many correlated positions
    
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
    ATR_STOP_MULTIPLIER = 2.5  # Crypto-appropriate (was 2.0 - too tight for volatility)
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

    # Execution cost model for paper/live signal PnL tracking.
    # Percent values use exchange-style percent notation: 0.02 = 0.02%.
    MAKER_FEE_PERCENT = float(os.getenv('MAKER_FEE_PERCENT', '0.02') or 0.02)
    TAKER_FEE_PERCENT = float(os.getenv('TAKER_FEE_PERCENT', '0.06') or 0.06)
    MIN_SPREAD_PERCENT = float(os.getenv('MIN_SPREAD_PERCENT', '0.02') or 0.02)
    ENTRY_ORDER_TYPE = os.getenv('ENTRY_ORDER_TYPE', 'maker').lower()
    TAKE_PROFIT_ORDER_TYPE = os.getenv('TAKE_PROFIT_ORDER_TYPE', 'maker').lower()
    STOP_LOSS_ORDER_TYPE = os.getenv('STOP_LOSS_ORDER_TYPE', 'taker').lower()
    
    # BTC-specific thresholds (BTC needs higher quality due to high volatility)
    BTC_SCORE_THRESHOLD = 80  # Higher quality required for BTC
    BTC_ATR_MULTIPLIER = 2.0  # Tighter stops for BTC (vs 2.5 for alts)
    BTC_SKIP_CHOPPY_REGIMES = True  # Only trade BTC in trending markets
    
    # Take Profit Ratios (as Risk multiples)
    TP1_RATIO = 1.5
    TP1_CLOSE_PERCENT = 50  # Close 50% at TP1
    TP2_RATIO = 2.5
    TP2_CLOSE_PERCENT = 30  # Close 30% at TP2
    TP3_RATIO = 3.5
    TP3_CLOSE_PERCENT = 20  # Trail remaining 20%
    
    # Near-TP Protection: Lock in profit if price gets very close to TP
    NEAR_TP_THRESHOLD = 0.92  # Trigger at 92% of distance to TP (adjustable: 0.90-0.95)
    NEAR_TP_ENABLED = True  # Set to False to disable this feature
    
    # Adaptive Stop Protection: Protect profits when market conditions worsen
    ADAPTIVE_STOP_ENABLED = True  # Tighten stops on regime/volatility changes
    ADAPTIVE_STOP_MIN_PROFIT_R = 0.4  # Only activate if position is up 0.4R or more
    ADAPTIVE_STOP_VOLATILITY_SPIKE = 1.6  # Tighten if ATR increases by 60%
    ADAPTIVE_STOP_REGIME_CHANGE = True  # Tighten if regime changes to choppy
    ADAPTIVE_STOP_BREAKEVEN_BUFFER = 0.0015  # 0.15% buffer above breakeven (prevents stop hunt)
    ADAPTIVE_STOP_PARTIAL_PROTECTION = True  # Exit 50% at breakeven, let 50% run to original stop
    
    # Volatility Filters
    VOLATILITY_MIN_RATIO = 0.7
    VOLATILITY_MAX_RATIO = 2.0
    EXTREME_VOLATILITY_MULTIPLIER = 3.0  # Suspend trading if ATR is 3x normal (likely news event)
    
    # ==================== SIGNAL MANAGEMENT ====================
    MAX_ACTIVE_SIGNALS_PER_PAIR = 1
    MAX_ACTIVE_BTC_SIGNALS = 1  # Only 1 BTC signal at a time
    MAX_TOTAL_ACTIVE_SIGNALS = 4 
    
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
        
        # Note: RISK_PER_TRADE is now dynamic based on equity, so we validate the baseline value
        if not (0 < cls.RISK_PER_TRADE <= 0.02):
            errors.append("Base RISK_PER_TRADE must be between 0 and 2% (dynamic calculation applies)")
        
        if cls.MAX_LEVERAGE > 15:
            errors.append(f"MAX_LEVERAGE should not exceed 15× (currently: {cls.MAX_LEVERAGE})")
        
        if len(cls.TRADING_PAIRS) == 0:
            errors.append("No trading pairs specified")
        
        # Ensure data directory exists
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
        
        # Display configuration
        print("✓ Configuration validated successfully")
        print(f"  - Trading pairs: {', '.join(cls.TRADING_PAIRS)}")
        print(f"  - Initial capital: ${cls.INITIAL_CAPITAL:,.2f}")
        print(f"\nFixed Risk Management:")
        print(f"  Risk per trade: {cls.RISK_PER_TRADE*100:.1f}%")
        print(f"  Max daily loss: {cls.MAX_DAILY_LOSS*100:.1f}%")
        print(f"  Max weekly loss: {cls.MAX_WEEKLY_LOSS*100:.1f}%")
        print(f"  Max leverage: {cls.MAX_LEVERAGE}×")
