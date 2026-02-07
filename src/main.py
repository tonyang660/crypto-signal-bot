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
from src.execution.paper_engine import PaperTradingEngine
from src.execution.paper_account import PaperAccount

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
        
        # Initialize paper trading if enabled
        self.paper_trading_enabled = Config.PAPER_TRADING_ENABLED
        if self.paper_trading_enabled:
            self.paper_account = PaperAccount(
                initial_capital=Config.INITIAL_CAPITAL,
                state_file=Config.PAPER_ACCOUNT_FILE
            )
            self.paper_engine = PaperTradingEngine(
                bitget_client=self.data_manager.client,
                paper_account=self.paper_account
            )
            logger.info("📊 Paper Trading Engine: ENABLED")
        else:
            self.paper_account = None
            self.paper_engine = None
            logger.info("📝 Paper Trading Engine: DISABLED (signal-only mode)")
        
        # Initialize risk manager with performance logger and paper_account
        self.risk_manager = RiskManager(
            performance_logger=self.performance_logger, 
            discord=self.discord,
            paper_account=self.paper_account
        )
        
        logger.info("✓ All components initialized")
        
        # Send startup notification with combined stats
        risk_stats = self.risk_manager.get_risk_stats()
        today_stats = self.performance_logger.get_today_statistics()
        
        combined_stats = {
            'equity': risk_stats['equity'],
            'daily_pnl': risk_stats['daily_pnl'],  # Use daily_pnl which includes all wins and losses
            'win_rate': today_stats.get('win_rate', 0)  # Today's win rate only
        }
        
        # Add paper trading status to notification
        status_msg = "🤖 Signal Bot Online"
        if self.paper_trading_enabled:
            status_msg += " 📊 (Paper Trading Enabled)"
        
        self.discord.send_status_update(
            status_msg,
            combined_stats
        )
    
    def scan_markets(self):
        """Main market scanning loop"""
        try:
            logger.info("=" * 70)
            logger.info(f"🔍 Scanning markets at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 70)
            
            # Get active symbols upfront for use throughout scan
            active_symbols = self.signal_tracker.get_active_symbols()
            
            # Paper trading mode: Handle order execution and position monitoring
            if self.paper_trading_enabled and self.paper_engine:
                # In paper trading, paper engine handles all position monitoring
                if active_symbols:
                    logger.info(f"📊 Paper Trading: Monitoring {len(active_symbols)} position(s): {', '.join(active_symbols)}")
                
                # Log pending orders status
                pending_count = len(self.paper_engine.pending_orders)
                if pending_count > 0:
                    logger.info(f"⏳ Checking {pending_count} pending limit order(s) for fills...")
                    for order_id, order in self.paper_engine.pending_orders.items():
                        if order['status'] == 'pending':
                            try:
                                ticker = self.data_manager.client.get_ticker(order['symbol'])
                                if order['side'] == 'long':
                                    price_info = f"Ask: ${ticker['ask']:,.4f} | Limit: ${order['limit_price']:,.4f}"
                                    will_fill = ticker['ask'] <= order['limit_price']
                                else:  # short
                                    price_info = f"Bid: ${ticker['bid']:,.4f} | Limit: ${order['limit_price']:,.4f}"
                                    will_fill = ticker['bid'] >= order['limit_price']
                                
                                status = "✅ READY TO FILL" if will_fill else "⏳ Waiting"
                                logger.info(f"   {order['symbol']} {order['side'].upper()}: {price_info} - {status}")
                            except Exception as e:
                                logger.warning(f"   {order['symbol']}: Could not check price - {e}")
                
                try:
                    # Check if any pending limit orders should fill
                    filled_orders = self.paper_engine.check_pending_orders()
                    
                    if filled_orders:
                        logger.info(f"🎯 {len(filled_orders)} order(s) filled this scan!")
                    elif pending_count > 0:
                        logger.info(f"⏳ No fills yet - orders still waiting for target price")
                    
                    for fill_data in filled_orders:
                        symbol = fill_data['symbol']
                        
                        # Get signal creation data from fill
                        signal_creation_data = fill_data.get('signal_creation_data')
                        if not signal_creation_data:
                            logger.error(f"No signal creation data for filled order {symbol}")
                            continue
                        
                        # NOW create the signal (only after fill)
                        execution_data = {
                            'entry_order_id': fill_data['order_id'],
                            'liquidation_price': None,  # Will be calculated by margin_calculator
                            'margin_used': signal_creation_data['position_size'].get('margin_used', 0)
                        }
                        
                        signal_id = self.signal_tracker.create_signal(
                            symbol=signal_creation_data['symbol'],
                            direction=signal_creation_data['direction'],
                            entry_price=fill_data['fill_price'],  # Use actual fill price
                            stop_loss=signal_creation_data['stop_loss'],
                            take_profits=signal_creation_data['take_profits'],
                            position_size=signal_creation_data['position_size'],
                            score=signal_creation_data['score'],
                            entry_reason=signal_creation_data['entry_reason'],
                            regime=signal_creation_data['regime'],
                            atr=signal_creation_data['atr'],
                            execution_data=execution_data
                        )
                        
                        if not signal_id:
                            logger.error(f"Failed to create signal for {symbol} after fill")
                            continue
                        
                        # Get the created signal
                        signal = self.signal_tracker.active_signals.get(symbol)
                        if not signal:
                            logger.error(f"Signal not found after creation for {symbol}")
                            continue
                        
                        # Update with fill details
                        signal['filled_at'] = fill_data['filled_at']
                        signal['fill_price'] = fill_data['fill_price']
                        signal['fees_paid'] = fill_data['fee']
                        signal['entry_slippage'] = fill_data['slippage']
                        signal['execution_state'] = 'filled'
                        self.signal_tracker._save_active_signals()
                        
                        # Create position and place SL/TP orders
                        position = self.paper_engine.add_position(fill_data, signal)
                        
                        # Update execution state to position_open
                        signal['execution_state'] = 'position_open'
                        self.signal_tracker._save_active_signals()
                        
                        # Send Discord notification for new signal (now filled)
                        self.discord.send_new_signal(
                            symbol=symbol,
                            direction=signal['direction'],
                            entry_price=fill_data['fill_price'],
                            stop_loss=signal['stop_loss'],
                            take_profits=signal['take_profits'],
                            position_size=signal['position_size'],
                            score=signal['score'],
                            reason=signal['entry_reason']
                        )
                        
                        logger.success(f"✅ Signal created & position opened: {symbol} @ ${fill_data['fill_price']:,.2f}")
                    
                    # Check exit conditions for open positions
                    for symbol in active_symbols:
                        signal = self.signal_tracker.active_signals.get(symbol)
                        if signal and signal.get('execution_state') == 'position_open':
                            # Get position from paper account
                            positions = [p for p in self.paper_account.get_open_positions() if p['symbol'] == symbol]
                            if positions:
                                position = positions[0]
                                exit_data = self.paper_engine.check_exit_conditions(position, signal)
                                
                                if exit_data:
                                    # Update signal with exit information
                                    exit_type = exit_data['exit_type']
                                    
                                    # Mark TP/SL as hit
                                    if exit_type == 'tp1':
                                        signal['tp1_hit'] = True
                                    elif exit_type == 'tp2':
                                        signal['tp2_hit'] = True
                                    elif exit_type == 'tp3':
                                        signal['tp3_hit'] = True
                                    elif exit_type in ['stop_loss', 'liquidation']:
                                        signal['stop_hit'] = True
                                    
                                    # Update remaining percent
                                    signal['remaining_percent'] -= exit_data['percent_closed']
                                    signal['realized_pnl'] += exit_data['realized_pnl']
                                    signal['fees_paid'] += exit_data.get('fee', 0)
                                    
                                    # Update execution state
                                    if signal['remaining_percent'] <= 0:
                                        self.signal_tracker.update_execution_state(symbol, 'fully_closed')
                                    else:
                                        self.signal_tracker.update_execution_state(symbol, 'partially_closed')
                                    
                                    # Send Discord notification
                                    self.discord.send_exit_notification(symbol, exit_type, exit_data, signal)
                                    
                                    logger.info(f"📉 Exit: {symbol} - {exit_type} | P&L: ${exit_data['realized_pnl']:.2f}")
                    
                    # Update equity curve
                    self.paper_account.update_equity_curve()
                    
                    # Save paper account state
                    self.paper_account.save_state()
                    
                except Exception as e:
                    logger.error(f"Error in paper trading execution: {e}")
            
            # Signal-only mode: Update existing signals with old system
            else:
                if active_symbols:
                    logger.info(f"📊 Signal-Only Mode: Monitoring {len(active_symbols)} signal(s): {', '.join(active_symbols)}")
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
                    
                    # Paper trading: Also skip if pending order exists
                    if self.paper_trading_enabled and self.paper_engine:
                        has_pending_order = any(
                            order['symbol'] == symbol and order['status'] == 'pending'
                            for order in self.paper_engine.pending_orders.values()
                        )
                        if has_pending_order:
                            logger.debug(f"{symbol}: Pending limit order already exists")
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
            # === PHASE 1: BTC REGIME CHECK (Market-wide filter) ===
            # Check BTC conditions BEFORE individual symbol analysis
            # Only affects NEW signal creation, never touches existing positions
            if symbol != 'BTCUSDT':  # Skip for BTC itself to avoid circular dependency
                try:
                    btc_data = self.data_manager.get_multi_timeframe_data('BTCUSDT')
                    if not any(df.empty for df in btc_data.values()):
                        btc_data['htf'] = Indicators.add_all_indicators(btc_data['htf'])
                        btc_regime_info = RegimeDetector.check_btc_regime(btc_data['htf'])
                        
                        logger.info(f"🔍 BTC Regime: {btc_regime_info['regime']} - {btc_regime_info['reason']}")
                        
                        # Apply BTC regime adjustments to this scan
                        btc_threshold_adj = btc_regime_info['score_threshold_adj']
                        btc_position_mult = btc_regime_info['position_size_mult']
                        btc_max_signals_adj = btc_regime_info['max_signals_adj']
                    else:
                        logger.warning("Could not fetch BTC data for regime check")
                        btc_threshold_adj = 5  # Default: slightly conservative
                        btc_position_mult = 0.9
                        btc_max_signals_adj = 0
                except Exception as e:
                    logger.warning(f"BTC regime check failed: {e}, proceeding with defaults")
                    btc_threshold_adj = 5
                    btc_position_mult = 0.9
                    btc_max_signals_adj = 0
            else:
                # For BTC itself, no adjustment
                btc_threshold_adj = 0
                btc_position_mult = 1.0
                btc_max_signals_adj = 0
            
            # Check if we should create new signals based on BTC regime
            current_signals = len(self.signal_tracker.get_all_active_signals())
            adjusted_max_signals = max(1, Config.MAX_TOTAL_ACTIVE_SIGNALS + btc_max_signals_adj)
            
            if current_signals >= adjusted_max_signals:
                logger.info(f"{symbol}: Max signals reached ({current_signals}/{adjusted_max_signals}) due to BTC regime")
                return
            
            # Fetch multi-timeframe data
            data = self.data_manager.get_multi_timeframe_data(symbol)
            
            # Check if data is valid
            if any(df.empty for df in data.values()):
                logger.warning(f"Missing data for {symbol}")
                return
            
            # Add indicators to all timeframes
            for timeframe in data:
                data[timeframe] = Indicators.add_all_indicators(data[timeframe])
            
            # Check market regime (individual symbol)
            regime = RegimeDetector.detect_regime(data['primary'])
            
            # Get base score threshold
            account_state = self.risk_manager.get_account_state()
            base_threshold = Config.SIGNAL_THRESHOLD_DRAWDOWN if account_state == 'drawdown' else Config.SIGNAL_THRESHOLD_NORMAL
            
            # Apply BTC regime adjustment to threshold
            threshold = base_threshold + btc_threshold_adj
            
            if not RegimeDetector.should_trade_regime(regime):
                logger.info(f"{symbol}: ❌ Unfavorable regime ({regime}) | Threshold: {threshold} (base: {base_threshold} + BTC adj: {btc_threshold_adj})")
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
            
            # Allow signal if entry requirements met OR score >= 80 (with minimum threshold check)
            if long_check['valid'] or (score >= 80 and score >= threshold):
                if not long_check['valid']:
                    logger.warning(f"{symbol}: ⚠️  LONG entry requirements not fully met, but score is exceptional ({score}/100) - Creating signal with override")
                    reason = f"High score override (80+): {long_check['reason']}"
                else:
                    logger.info(f"{symbol}: ✅ LONG entry conditions met | Score: {score}/100 (threshold: {threshold}) - {long_check['reason']}")
                    reason = long_check['reason']
                
                self._create_signal_with_score(symbol, 'long', data, reason, score, breakdown, btc_position_mult)
                return
            else:
                logger.info(f"{symbol}: ❌ Long entry failed | Score: {score}/100 (threshold: {threshold}) - {long_check['reason']}")
            
            # Check for short entry
            short_check = EntryLogic.check_short_entry(data)
            
            # Calculate score first
            score, breakdown = SignalScorer.calculate_score_with_breakdown(data, 'short', symbol)
            
            # Allow signal if entry requirements met OR score >= 80 (with minimum threshold check)
            if short_check['valid'] or (score >= 80 and score >= threshold):
                if not short_check['valid']:
                    logger.warning(f"{symbol}: ⚠️  SHORT entry requirements not fully met, but score is exceptional ({score}/100) - Creating signal with override")
                    reason = f"High score override (80+): {short_check['reason']}"
                else:
                    logger.info(f"{symbol}: ✅ SHORT entry conditions met | Score: {score}/100 (threshold: {threshold}) - {short_check['reason']}")
                    reason = short_check['reason']
                
                self._create_signal_with_score(symbol, 'short', data, reason, score, breakdown, btc_position_mult)
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
        breakdown: dict,
        btc_position_mult: float = 1.0
    ):
        """Create new trading signal with pre-calculated score and BTC regime adjustment"""
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
            
            # Get ATR for adaptive stop monitoring
            entry_atr = data['primary']['atr'].iloc[-1]
            
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
            
            # Apply BTC regime position size adjustment
            if btc_position_mult < 1.0:
                original_contracts = position_size['contracts']
                position_size['contracts'] = max(1, int(position_size['contracts'] * btc_position_mult))
                position_size['total_value'] = position_size['contracts'] * current_price
                logger.info(f"{symbol}: BTC regime adjusted position: {original_contracts} → {position_size['contracts']} contracts ({btc_position_mult:.1%} multiplier)")
            
            # Validate position size
            market_info = self.data_manager.client.get_market_info(symbol)
            if not PositionSizer.validate_position_size(position_size, market_info):
                logger.warning(f"{symbol}: Position size validation failed")
                return
            
            # Paper trading: Place order ONLY (signal created after fill)
            if self.paper_trading_enabled and self.paper_engine:
                try:
                    # Generate signal ID
                    signal_id = f"{symbol}_{direction}_{int(datetime.now().timestamp())}"
                    
                    # Prepare complete signal data for order
                    signal_data = {
                        'signal_id': signal_id,
                        'symbol': symbol,
                        'direction': direction,
                        'entry_price': current_price,
                        'stop_loss': stop_loss,
                        'take_profits': take_profits,
                        'position_size': position_size,
                        'score': score,
                        'entry_reason': entry_reason,
                        'regime': regime,
                        'atr': entry_atr
                    }
                    
                    # Place limit order (signal will be created on fill)
                    order_id = self.paper_engine.place_limit_order(signal_data)
                    
                    logger.success(f"📊 Paper Trading: Limit order {order_id} placed for {symbol} | "
                                 f"Signal will be created on fill | Score: {score}")
                    
                    # Send Discord notification for order placement
                    self.discord.send_status_update(
                        f"📝 **Limit Order Placed - {symbol}**\n\n"
                        f"Direction: {direction.upper()}\n"
                        f"Entry Price: ${current_price:.4f}\n"
                        f"Size: ${position_size['notional_usd']:.2f}\n"
                        f"Leverage: {position_size['leverage']:.1f}×\n"
                        f"Score: {score}/100\n\n"
                        f"⏱️ Order will fill when price reaches entry level"
                    )
                    
                    return  # Done - signal will be created on fill
                    
                except Exception as e:
                    logger.error(f"❌ Error placing paper trading order for {symbol}: {e}")
                    import traceback
                    traceback.print_exc()
                    return
            
            # Signal-only mode: Create signal immediately (old behavior)
            signal_id = self.signal_tracker.create_signal(
                symbol=symbol,
                direction=direction,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profits=take_profits,
                position_size=position_size,
                score=score,
                entry_reason=entry_reason,
                regime=regime,  # Add regime for tracking
                atr=entry_atr  # Add entry ATR for adaptive stops
            )
            
            if signal_id:
                # Send Discord notification (signal-only mode)
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
            
            # Get current market data for adaptive stop check
            data = self.data_manager.get_multi_timeframe_data(symbol)
            if not any(df.empty for df in data.values()):
                # Add indicators
                for timeframe in data:
                    data[timeframe] = Indicators.add_all_indicators(data[timeframe])
                
                # Check for adaptive stop trigger
                current_atr = data['primary']['atr'].iloc[-1]
                current_regime = RegimeDetector.detect_regime(data['primary'])
                
                should_trigger, new_stop, reason = self.signal_tracker.check_adaptive_stop_trigger(
                    symbol, current_price, current_atr, current_regime
                )
                
                if should_trigger and new_stop is not None:
                    # Adaptive stop triggered - update stop loss
                    signal = self.signal_tracker.active_signals.get(symbol)
                    if signal:
                        old_stop = signal['stop_loss']
                        signal['stop_loss'] = new_stop
                        signal['adaptive_stop_triggered'] = True
                        
                        # Enable partial protection mode if configured
                        protection_mode = "partial" if Config.ADAPTIVE_STOP_PARTIAL_PROTECTION else "full"
                        if Config.ADAPTIVE_STOP_PARTIAL_PROTECTION:
                            signal['partial_protection_active'] = True
                        
                        self.signal_tracker._save_active_signals()
                        
                        logger.info(f"🛡️ Adaptive stop triggered for {symbol}: {reason} (mode: {protection_mode})")
                        
                        # Send Discord notification
                        protection_desc = (
                            "50% of position protected at breakeven.\n"
                            "Remaining 50% continues with original stop."
                            if Config.ADAPTIVE_STOP_PARTIAL_PROTECTION else
                            "Full position protected at breakeven."
                        )
                        
                        self.discord.send_status_update(
                            f"🛡️ **Adaptive Stop Protection - {symbol}**\n\n"
                            f"Market conditions worsened while in profit.\n"
                            f"{protection_desc}\n\n"
                            f"**Details:**\n"
                            f"Direction: {signal['direction'].upper()}\n"
                            f"Reason: {reason}\n"
                            f"Old Stop: ${old_stop:.4f}\n"
                            f"New Stop: ${new_stop:.4f}\n"
                            f"Protection: Breakeven + buffer"
                        )
            
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
                        total_pnl=hit_info['remaining_pnl']  # P&L from remaining position only
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
                        pnl=hit_info['remaining_pnl'],  # Only record P&L from remaining position (partial TPs already recorded)
                        exit_reason='stopped',
                        regime=signal.get('regime', 'unknown'),
                        score=signal.get('score', 0),
                        duration_hours=duration
                    )
                    self.risk_manager.record_trade(hit_info['remaining_pnl'])  # Only record remaining position P&L (partial TPs already recorded)
                
                elif hit_info['type'] == 'partial_protection_exit':
                    # Partial protection triggered - 50% exited at breakeven
                    self.discord.send_status_update(
                        f"⚡ **Partial Protection Exit - {symbol}**\n\n"
                        f"50% of position exited at breakeven.\n"
                        f"Remaining 50% continues with original stop.\n\n"
                        f"**Details:**\n"
                        f"Direction: {signal['direction'].upper()}\n"
                        f"Exit Price: ${hit_info['price']:.4f}\n"
                        f"Partial PnL: ${hit_info['partial_pnl']:+.2f}\n"
                        f"Remaining: {hit_info['percent_remaining']:.0f}%\n"
                        f"New Stop: ${hit_info['new_stop']:.4f} (original)\n\n"
                        f"✅ Protected from full loss while keeping upside potential."
                    )
                    
                    # Record the partial exit PnL
                    self.risk_manager.record_trade(hit_info['partial_pnl'])
            
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