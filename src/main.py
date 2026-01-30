import time
import schedule
from datetime import datetime
from loguru import logger
from typing import Dict
import sys

# Configure logger
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/bot.log",
    rotation="1 day",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG"
)

# Import components
from src.core.config import Config
from src.core.data_manager import DataManager
from src.analysis.indicators import Indicators
from src.analysis.market_structure import MarketStructure
from src.analysis.regime_detector import RegimeDetector
from src.strategy.entry_logic import EntryLogic
from src.strategy.signal_scorer import SignalScorer
from src.strategy.stop_tp_calculator import StopTPCalculator
from src.risk.position_sizer import PositionSizer
from src.risk.risk_manager import RiskManager
from src.tracking.signal_tracker import SignalTracker
from src.tracking.performance_logger import PerformanceLogger
from src.notifications.discord_notifier import DiscordNotifier

class SignalBot:
    """Main signal bot orchestrator"""
    
    def __init__(self):
        logger.info("=" * 70)
        logger.info("🚀 BitGet Futures Signal Bot Starting...")
        logger.info("=" * 70)
        
        # Validate configuration
        Config.validate()
        
        # Initialize components
        self.data_manager = DataManager()
        self.risk_manager = RiskManager()
        self.signal_tracker = SignalTracker()
        self.performance_logger = PerformanceLogger()
        self.discord = DiscordNotifier()
        
        logger.info("✓ All components initialized")
        
        # Send startup notification
        self.discord.send_status_update(
            "🤖 Signal Bot Started",
            self.risk_manager.get_risk_stats()
        )
    
    def scan_markets(self):
        """Main market scanning loop"""
        try:
            logger.info("=" * 70)
            logger.info(f"🔍 Scanning markets at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 70)
            
            # Check if trading is allowed
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                logger.warning(f"Trading disabled: {reason}")
                return
            
            # Get active symbols
            active_symbols = self.signal_tracker.get_active_symbols()
            
            # Scan each pair
            for symbol in Config.TRADING_PAIRS:
                try:
                    # Check if signal already exists for this pair
                    can_create, reason = self.signal_tracker.can_create_signal(symbol)
                    
                    if symbol in active_symbols:
                        # Update existing signal
                        self._update_active_signal(symbol)
                        continue
                    
                    if not can_create:
                        logger.debug(f"Skipping {symbol}: {reason}")
                        continue
                    
                    # Scan for new signal
                    self._scan_symbol(symbol)
                    
                except Exception as e:
                    logger.error(f"Error scanning {symbol}: {e}")
                    continue
            
            # Log summary
            active_count = len(self.signal_tracker.get_all_active_signals())
            logger.info(f"✓ Scan complete | Active signals: {active_count}")
            
        except Exception as e:
            logger.error(f"Error in scan_markets: {e}")
            self.discord.send_error(f"Scan error: {str(e)}")
    
    def _scan_symbol(self, symbol: str):
        """Scan individual symbol for entry opportunities"""
        try:
            # Fetch multi-timeframe data
            data = self.data_manager.get_multi_timeframe_data(symbol)
            
            # Check if data is valid
            if any(df.empty for df in data.values()):
                logger.warning(f"Missing data for {symbol}")
                return
            
            # Add indicators to all timeframes
            for timeframe in data:
                data[timeframe] = Indicators.add_all_indicators(data[timeframe])
            
            # Check market regime
            regime = RegimeDetector.detect_regime(data['primary'])
            
            if not RegimeDetector.should_trade_regime(regime):
                logger.info(f"{symbol}: ❌ Unfavorable regime ({regime})")
                return
            
            logger.info(f"{symbol}: ✓ Regime check passed ({regime})")
            
            # Check for long entry
            long_check = EntryLogic.check_long_entry(data)
            if long_check['valid']:
                logger.info(f"{symbol}: ✅ LONG entry conditions met - {long_check['reason']}")
                # Calculate score with breakdown
                score, breakdown = SignalScorer.calculate_score_with_breakdown(data, 'long', symbol)
                self._create_signal_with_score(symbol, 'long', data, long_check['reason'], score, breakdown)
                return
            else:
                logger.info(f"{symbol}: ❌ Long entry failed - {long_check['reason']}")
            
            # Check for short entry
            short_check = EntryLogic.check_short_entry(data)
            if short_check['valid']:
                logger.info(f"{symbol}: ✅ SHORT entry conditions met - {short_check['reason']}")
                # Calculate score with breakdown
                score, breakdown = SignalScorer.calculate_score_with_breakdown(data, 'short', symbol)
                self._create_signal_with_score(symbol, 'short', data, short_check['reason'], score, breakdown)
                return
            else:
                logger.info(f"{symbol}: ❌ Short entry failed - {short_check['reason']}")
            
            logger.debug(f"{symbol}: No entry conditions met")
            
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
    
    def _create_signal_with_score(
        self,
        symbol: str,
        direction: str,
        data: Dict,
        entry_reason: str,
        score: int,
        breakdown: dict
    ):
        """Create new trading signal with pre-calculated score"""
        try:
            # Get current price
            current_price = data['entry']['close'].iloc[-1]
            
            # Check score threshold
            account_state = self.risk_manager.get_account_state()
            threshold = Config.SIGNAL_THRESHOLD_DRAWDOWN if account_state == 'drawdown' else Config.SIGNAL_THRESHOLD_NORMAL
            
            if score < threshold:
                logger.warning(f"{symbol}: ⚠️  Score {score}/100 below threshold {threshold} - Signal rejected")
                return
            
            logger.success(f"{symbol}: ✅ Score {score}/100 exceeds threshold {threshold}")
            
            # Calculate stop loss
            stop_loss = StopTPCalculator.calculate_stop_loss(
                data, direction, current_price
            )
            
            # Calculate take profits
            take_profits = StopTPCalculator.calculate_take_profits(
                current_price, stop_loss, direction
            )
            
            # Calculate position size
            position_size = PositionSizer.calculate_position_size(
                self.risk_manager.equity,
                current_price,
                stop_loss,
                symbol
            )
            
            if not position_size:
                logger.error(f"{symbol}: Could not calculate position size")
                return
            
            # Validate position size
            market_info = self.data_manager.client.get_market_info(symbol)
            if not PositionSizer.validate_position_size(position_size, market_info):
                logger.warning(f"{symbol}: Position size validation failed")
                return
            
            # Create signal
            signal_id = self.signal_tracker.create_signal(
                symbol=symbol,
                direction=direction,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profits=take_profits,
                position_size=position_size,
                score=score,
                entry_reason=entry_reason
            )
            
            if signal_id:
                # Send Discord notification
                self.discord.send_new_signal(
                    symbol=symbol,
                    direction=direction,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profits=take_profits,
                    position_size=position_size,
                    score=score,
                    reason=entry_reason
                )
                
                logger.success(f"✅ {direction.upper()} signal created for {symbol} | Score: {score}")
            
        except Exception as e:
            logger.error(f"Error creating signal for {symbol}: {e}")
    
    def _update_active_signal(self, symbol: str):
        """Update active signal with current price"""
        try:
            # Get current price
            current_price = self.data_manager.client.get_current_price(symbol)
            
            if current_price == 0:
                logger.warning(f"Could not get price for {symbol}")
                return
            
            # Update signal
            hit_info = self.signal_tracker.update_signal_price(symbol, current_price)
            
            if hit_info:
                signal = self.signal_tracker.get_active_signal(symbol)
                
                if hit_info['type'] == 'tp_hit':
                    # Send TP notification
                    self.discord.send_tp_hit(
                        symbol=symbol,
                        direction=signal['direction'],
                        tp_level=hit_info['level'],
                        price=current_price,
                        pnl=hit_info['pnl'],
                        total_pnl=hit_info['total_pnl'],
                        remaining_percent=hit_info['remaining_percent']
                    )
                    
                    # Record trade if fully closed
                    if hit_info['remaining_percent'] == 0:
                        self.performance_logger.log_trade(
                            signal_id=signal['signal_id'],
                            symbol=symbol,
                            direction=signal['direction'],
                            entry_price=signal['entry_price'],
                            exit_price=current_price,
                            pnl=hit_info['total_pnl'],
                            exit_reason='completed'
                        )
                        self.risk_manager.record_trade(hit_info['total_pnl'])
                
                elif hit_info['type'] == 'stop_hit':
                    # Send stop loss notification
                    self.discord.send_stop_hit(
                        symbol=symbol,
                        direction=signal['direction'],
                        price=current_price,
                        total_pnl=hit_info['total_pnl']
                    )
                    
                    # Record trade
                    self.performance_logger.log_trade(
                        signal_id=signal['signal_id'],
                        symbol=symbol,
                        direction=signal['direction'],
                        entry_price=signal['entry_price'],
                        exit_price=current_price,
                        pnl=hit_info['total_pnl'],
                        exit_reason='stopped'
                    )
                    self.risk_manager.record_trade(hit_info['total_pnl'])
            
        except Exception as e:
            logger.error(f"Error updating signal for {symbol}: {e}")
    
    def send_daily_report(self):
        """Send daily performance report"""
        try:
            stats = self.performance_logger.get_statistics(days=1)
            risk_stats = self.risk_manager.get_risk_stats()
            
            message = f"""
**Daily Performance Report**

Trades: {stats.get('total_trades', 0)}
Win Rate: {stats.get('win_rate', 0):.1f}%
Total PnL: ${stats.get('total_pnl', 0):+.2f}

Account Equity: ${risk_stats['equity']:.2f}
Daily Loss: ${risk_stats['daily_loss']:+.2f}
"""
            
            self.discord.send_status_update(message, stats)
            logger.info("📊 Daily report sent")
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
    
    def run(self):
        """Start the bot"""
        logger.info("🤖 Bot is now running...")
        logger.info(f"⏱️  Scan interval: {Config.SCAN_INTERVAL_SECONDS} seconds")
        
        # Schedule tasks
        schedule.every(Config.SCAN_INTERVAL_SECONDS).seconds.do(self.scan_markets)
        schedule.every().day.at("00:00").do(self.send_daily_report)
        
        # Run initial scan
        self.scan_markets()
        
        # Main loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("👋 Bot stopped by user")
            self.discord.send_status_update("🛑 Bot Stopped")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            self.discord.send_error(f"Fatal error: {str(e)}")

# Entry point
if __name__ == "__main__":
    import sys
    
    bot = SignalBot()
    
    if '--single-run' in sys.argv:
        # Run once then exit (for GitHub Actions)
        logger.info("🔄 Running in single-scan mode (GitHub Actions)")
        bot.scan_markets()
        
        # Check if daily report should be sent (at midnight UTC)
        current_hour = datetime.now().hour
        if current_hour == 0:
            bot.send_daily_report()
        
        logger.info("✅ Single scan complete, exiting")
    else:
        # Normal continuous mode
        bot.run()