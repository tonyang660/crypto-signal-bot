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
        self.signal_tracker = SignalTracker()
        self.performance_logger = PerformanceLogger()
        self.discord = DiscordNotifier()
        
        # Initialize risk manager with performance logger (for daily report saving)
        self.risk_manager = RiskManager(performance_logger=self.performance_logger, discord=self.discord)
        
        logger.info("✓ All components initialized")
        
        # Send startup notification with combined stats
        risk_stats = self.risk_manager.get_risk_stats()
        today_stats = self.performance_logger.get_today_statistics()
        
        combined_stats = {
            'equity': risk_stats['equity'],
            'daily_pnl': risk_stats['daily_pnl'],  # Use daily_pnl which includes all wins and losses
            'win_rate': today_stats.get('win_rate', 0)  # Today's win rate only
        }
        
        self.discord.send_status_update(
            "🤖 Signal Bot Online",
            combined_stats
        )
    
    def scan_markets(self):
        """Main market scanning loop"""
        try:
            logger.info("=" * 70)
            logger.info(f"🔍 Scanning markets at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 70)
            
            # Get active symbols (do this BEFORE trading check to monitor existing signals)
            active_symbols = self.signal_tracker.get_active_symbols()
            
            # ALWAYS update existing signals first (even if trading is disabled)
            if active_symbols:
                logger.info(f"📊 Monitoring {len(active_symbols)} active signal(s): {', '.join(active_symbols)}")
                for symbol in active_symbols:
                    try:
                        self._update_active_signal(symbol)
                    except Exception as e:
                        logger.error(f"Error updating {symbol}: {e}")
            
            # Check if trading is allowed for NEW signals
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                logger.warning(f"Trading disabled for new signals: {reason}")
                if active_symbols:
                    logger.info(f"✓ Continuing to monitor {len(active_symbols)} existing signal(s)")
                return
            
            # Log total exposure
            total_margin = self.signal_tracker.get_total_margin_used()
            available_margin = self.signal_tracker.get_available_margin(self.risk_manager.equity)
            exposure_pct = (total_margin / self.risk_manager.equity) * 100 if self.risk_manager.equity > 0 else 0
            logger.info(f"💼 Total margin used: ${total_margin:.2f} ({exposure_pct:.1f}%) | Available: ${available_margin:.2f}")
            
            # Scan each pair for NEW signals
            for symbol in Config.TRADING_PAIRS:
                try:
                    # Skip if signal already exists (already updated above)
                    if symbol in active_symbols:
                        logger.debug(f"{symbol}: Active signal already being monitored")
                        continue
                    
                    # Check if new signal can be created
                    can_create, reason = self.signal_tracker.can_create_signal(symbol)
                    
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
            
            # Show detailed active signals summary if any exist
            if active_count > 0:
                summary = self.signal_tracker.get_active_signals_summary()
                logger.info(summary)
            
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
            
            # Get score threshold based on regime
            account_state = self.risk_manager.get_account_state()
            threshold = Config.SIGNAL_THRESHOLD_DRAWDOWN if account_state == 'drawdown' else Config.SIGNAL_THRESHOLD_NORMAL
            
            if not RegimeDetector.should_trade_regime(regime):
                logger.info(f"{symbol}: ❌ Unfavorable regime ({regime}) | Min threshold: {threshold}")
                return
            
            # Check for extreme volatility (likely news event)
            is_extreme, vol_reason = self.risk_manager.check_extreme_volatility(symbol, data)
            if is_extreme:
                logger.warning(f"{symbol}: {vol_reason}")
                
                # Alert Discord only once per hour to avoid spam
                now = datetime.now()
                if (self.risk_manager.last_volatility_alert is None or 
                    (now - self.risk_manager.last_volatility_alert).total_seconds() > 3600):
                    self.discord.send_error(vol_reason)
                    self.risk_manager.last_volatility_alert = now
                
                return  # Skip this symbol

            logger.info(f"{symbol}: ✓ Regime check passed ({regime}) | Min threshold: {threshold}")
            
            # Check for long entry
            long_check = EntryLogic.check_long_entry(data)
            
            # Calculate score first
            score, breakdown = SignalScorer.calculate_score_with_breakdown(data, 'long', symbol)
            
            # Allow signal if entry requirements met OR score >= 85
            if long_check['valid'] or score >= 85:
                if not long_check['valid']:
                    logger.warning(f"{symbol}: ⚠️  LONG entry requirements not fully met, but score is high ({score}/100) - Creating signal with override")
                    reason = f"High score override (85+): {long_check['reason']}"
                else:
                    logger.info(f"{symbol}: ✅ LONG entry conditions met | Score: {score}/100 (threshold: {threshold}) - {long_check['reason']}")
                    reason = long_check['reason']
                
                self._create_signal_with_score(symbol, 'long', data, reason, score, breakdown)
                return
            else:
                logger.info(f"{symbol}: ❌ Long entry failed | Score: {score}/100 (threshold: {threshold}) - {long_check['reason']}")
            
            # Check for short entry
            short_check = EntryLogic.check_short_entry(data)
            
            # Calculate score first
            score, breakdown = SignalScorer.calculate_score_with_breakdown(data, 'short', symbol)
            
            # Allow signal if entry requirements met OR score >= 85
            if short_check['valid'] or score >= 85:
                if not short_check['valid']:
                    logger.warning(f"{symbol}: ⚠️  SHORT entry requirements not fully met, but score is high ({score}/100) - Creating signal with override")
                    reason = f"High score override (85+): {short_check['reason']}"
                else:
                    logger.info(f"{symbol}: ✅ SHORT entry conditions met | Score: {score}/100 (threshold: {threshold}) - {short_check['reason']}")
                    reason = short_check['reason']
                
                self._create_signal_with_score(symbol, 'short', data, reason, score, breakdown)
                return
            else:
                logger.info(f"{symbol}: ❌ Short entry failed | Score: {score}/100 (threshold: {threshold}) - {short_check['reason']}")
            
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
            
            # Detect market regime for adaptive TP targets
            regime = RegimeDetector.detect_regime(data['primary'])
            logger.info(f"{symbol}: Market regime detected: {regime}")
            
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
            
            # Calculate take profits (regime-adjusted)
            take_profits = StopTPCalculator.calculate_take_profits(
                current_price, stop_loss, direction, regime
            )
            
            # Get available margin (accounting for existing positions)
            available_margin = self.signal_tracker.get_available_margin(self.risk_manager.equity)
            
            # Calculate position size with margin constraint
            position_size = PositionSizer.calculate_position_size(
                self.risk_manager.equity,
                current_price,
                stop_loss,
                symbol,
                available_margin=available_margin
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
                entry_reason=entry_reason,
                regime=regime  # Add regime for tracking
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
                # Signal data is included in hit_info
                signal = hit_info['signal']
                
                if hit_info['type'] == 'tp_hit':
                    # Send TP notification
                    self.discord.send_tp_hit(
                        symbol=symbol,
                        direction=signal['direction'],
                        tp_level=hit_info['level'],
                        price=current_price,
                        pnl=hit_info['pnl'],
                        total_pnl=hit_info['total_pnl'],
                        remaining_percent=hit_info['remaining_percent'],
                        new_stop_loss=hit_info.get('new_stop_loss')
                    )
                    
                    # Record partial profit immediately (affects daily PnL)
                    self.risk_manager.record_trade(hit_info['pnl'])
                    
                    # Log full trade if position fully closed
                    if hit_info['remaining_percent'] == 0:
                        # Calculate duration
                        entry_time = datetime.fromisoformat(signal.get('entry_time', signal.get('created_at', datetime.now().isoformat())))
                        duration = (datetime.now() - entry_time).total_seconds() / 3600
                        
                        self.performance_logger.log_trade(
                            signal_id=signal['signal_id'],
                            symbol=symbol,
                            direction=signal['direction'],
                            entry_price=signal['entry_price'],
                            exit_price=current_price,
                            pnl=hit_info['total_pnl'],
                            exit_reason='completed',
                            regime=signal.get('regime', 'unknown'),
                            score=signal.get('score', 0),
                            duration_hours=duration
                        )
                
                elif hit_info['type'] == 'stop_hit':
                    # Send stop loss notification
                    self.discord.send_stop_hit(
                        symbol=symbol,
                        direction=signal['direction'],
                        price=current_price,
                        total_pnl=hit_info['total_pnl']
                    )
                    
                    # Calculate duration
                    entry_time = datetime.fromisoformat(signal.get('entry_time', signal.get('created_at', datetime.now().isoformat())))
                    duration = (datetime.now() - entry_time).total_seconds() / 3600
                    
                    # Record trade
                    self.performance_logger.log_trade(
                        signal_id=signal['signal_id'],
                        symbol=symbol,
                        direction=signal['direction'],
                        entry_price=signal['entry_price'],
                        exit_price=current_price,
                        pnl=hit_info['total_pnl'],
                        exit_reason='stopped',
                        regime=signal.get('regime', 'unknown'),
                        score=signal.get('score', 0),
                        duration_hours=duration
                    )
                    self.risk_manager.record_trade(hit_info['total_pnl'])
            
        except Exception as e:
            logger.error(f"Error updating signal for {symbol}: {e}")
    
    def send_daily_report(self):
        """Send daily performance report (called BEFORE daily reset)"""
        try:
            # Save report to permanent log first
            today_stats = self.performance_logger.save_daily_report()
            risk_stats = self.risk_manager.get_risk_stats()
            
            # Combine stats for Discord display
            combined_stats = {
                'equity': risk_stats['equity'],
                'daily_pnl': risk_stats['daily_pnl'],  # Shows actual daily P/L from risk manager
                'win_rate': today_stats.get('win_rate', 0)  # Today's win rate only
            }
            
            message = f"""
**Daily Performance Report**

Trades: {today_stats.get('total_trades', 0)}
Win Rate: {today_stats.get('win_rate', 0):.1f}%
Total PnL: ${today_stats.get('total_pnl', 0):+.2f}

Account Equity: ${risk_stats['equity']:.2f}
Daily PnL: ${risk_stats['daily_pnl']:+.2f}
"""
            
            self.discord.send_status_update(message, combined_stats)
            logger.info("📊 Daily report sent and saved to logs")
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
    
    def run(self):
        """Start the bot"""
        logger.info("🤖 Bot is now running...")
        logger.info(f"⏱️  Scan interval: {Config.SCAN_INTERVAL_SECONDS} seconds")
        
        # Schedule tasks
        schedule.every(Config.SCAN_INTERVAL_SECONDS).seconds.do(self.scan_markets)
        # Note: Daily report is now auto-sent by risk_manager when new day is detected
        
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
        
        # Note: scan_markets() now handles daily report generation automatically
        # when a new day is detected (before reset)
        bot.scan_markets()
        
        logger.info("✅ Single scan complete, exiting")
    else:
        # Normal continuous mode
        bot.run()