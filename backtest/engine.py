"""
Backtesting Engine - Replays historical data candle-by-candle

CRITICAL RULES (from the guidelines):
1. NO future data (no peeking ahead)
2. NO "best price inside candle" cheating
3. Entries only on candle close
4. Conservative execution (worst-case if both TP and SL hit)
5. Include slippage and fees
6. Proper position sizing
7. Log everything
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.indicators import Indicators
from src.analysis.market_structure import MarketStructure
from src.analysis.regime_detector import RegimeDetector
from src.strategy.entry_logic import EntryLogic
from src.strategy.signal_scorer import SignalScorer
from src.strategy.stop_tp_calculator import StopTPCalculator
from src.risk.position_sizer import PositionSizer
from backtest.config import BacktestConfig

@dataclass
class Position:
    """Active position in backtest"""
    symbol: str
    direction: str
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profits: Dict
    position_size: float
    contracts: float
    margin_used: float
    score: int
    regime: str
    entry_reason: str
    
    # Tracking
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    remaining_percent: float = 100.0
    contracts_remaining: float = 0.0  # Track actual asset amount remaining
    realized_pnl: float = 0.0
    
    # Adaptive stop tracking
    entry_atr: float = 0.0
    adaptive_stop_triggered: bool = False
    
@dataclass
class Trade:
    """Completed trade record"""
    symbol: str
    direction: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    pnl: float
    pnl_percent: float
    exit_reason: str
    regime: str
    score: int
    duration_hours: float
    max_drawdown: float = 0.0

class BacktestEngine:
    """Core backtesting engine - candle-by-candle replay"""
    
    def __init__(self, data: Dict[str, Dict[str, pd.DataFrame]]):
        """
        Args:
            data: Dict[symbol][timeframe] = DataFrame
        """
        self.data = data
        self.equity = BacktestConfig.INITIAL_CAPITAL
        self.initial_equity = BacktestConfig.INITIAL_CAPITAL
        
        # Positions and tracking
        self.active_positions: Dict[str, Position] = {}
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        
        # Session tracking
        self.long_trades_count = 0
        self.short_trades_count = 0
        self.long_trades_pnl = 0.0
        self.short_trades_pnl = 0.0
        
        # Risk management state
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None
        self.weekly_cooldown_until: Optional[datetime] = None
        self.last_reset_date: Optional[datetime] = None
        
        # Threshold penalties
        self.daily_threshold_penalty = 0
        self.weekly_threshold_penalty = 0
        
        # Statistics
        self.total_fees_paid = 0.0
        self.total_slippage_cost = 0.0
        self.total_volume_traded = 0.0  # Track total volume (entry + exit values)
        
        if BacktestConfig.ENABLE_LOGGING:
            logger.info(f"Backtest initialized with ${self.equity:.2f}")
    
    def _log(self, level: str, message: str):
        """Conditional logging based on config"""
        if not BacktestConfig.ENABLE_LOGGING:
            return
        
        if level == 'info':
            logger.info(message)
        elif level == 'debug':
            logger.debug(message)
        elif level == 'warning':
            logger.warning(message)
        elif level == 'error':
            logger.error(message)
        elif level == 'success':
            logger.success(message)
    
    def _calculate_fee(self, trade_value: float) -> float:
        """
        Calculate fee based on maker/taker probability
        
        Simulates 70% maker orders (limit orders) and 30% taker orders (market orders)
        Returns weighted average fee
        
        Args:
            trade_value: Total value of the trade
            
        Returns:
            Fee amount in dollars
        """
        maker_prob = BacktestConfig.MAKER_ORDER_PROBABILITY
        taker_prob = 1.0 - maker_prob
        
        # Weighted average fee rate
        avg_fee_rate = (maker_prob * BacktestConfig.MAKER_FEE + 
                       taker_prob * BacktestConfig.TAKER_FEE)
        
        return trade_value * (avg_fee_rate / 100)
    
    def run(self) -> Dict:
        """
        Run the backtest
        
        Returns:
            Results dictionary with metrics
        """
        self._log('info', "="*70)
        self._log('info', "STARTING BACKTEST")
        self._log('info', "="*70)
        
        # Get date range from data
        all_dates = set()
        for symbol in self.data:
            if BacktestConfig.ENTRY_TIMEFRAME in self.data[symbol]:
                all_dates.update(self.data[symbol][BacktestConfig.ENTRY_TIMEFRAME].index)
        
        if not all_dates:
            raise ValueError("No data available for backtesting")
        
        sorted_dates = sorted(all_dates)
        start_date = sorted_dates[0]
        end_date = sorted_dates[-1]
        
        self._log('info', f"Backtest period: {start_date} to {end_date}")
        self._log('info', f"Total candles: {len(sorted_dates)}")
        
        # Apply warmup period if configured
        if hasattr(BacktestConfig, 'WARMUP_DATE'):
            warmup_date = BacktestConfig.WARMUP_DATE
            self._log('info', f"Warmup period: {start_date} to {warmup_date} (indicators only, no trading)")
            self._log('info', f"Trading period: {warmup_date} to {end_date}")
        else:
            warmup_date = start_date
        
        # Process each candle with progress bar
        iterator = enumerate(sorted_dates)
        if BacktestConfig.SHOW_PROGRESS_BAR and TQDM_AVAILABLE:
            iterator = tqdm(iterator, total=len(sorted_dates), desc="Running backtest", unit="candles", leave=True, ncols=100)
        
        for i, current_time in iterator:
            # Daily reset
            self._check_daily_reset(current_time)
            
            # Update active positions (check TP/SL)
            self._update_positions(current_time)
            
            # Skip signal scanning during warmup period
            if current_time < warmup_date:
                self.equity_curve.append((current_time, self.equity))
                continue
            
            # Check if trading allowed
            can_trade, reason = self._can_trade(current_time)
            
            if not can_trade:
                self._log('debug', f"{current_time}: Trading disabled - {reason}")
                continue
            
            # Scan for new signals
            self._scan_for_signals(current_time)
            
            # Record equity
            self.equity_curve.append((current_time, self.equity))
        
        # Close any remaining positions at end
        self._close_all_positions(end_date, "backtest_end")
        
        # Calculate results
        results = self._calculate_results()
        
        self._log('info', "="*70)
        self._log('info', "BACKTEST COMPLETE")
        self._log('info', "="*70)
        
        return results
    
    def _update_positions(self, current_time: datetime):
        """Update all active positions - check for TP/SL hits and adaptive stops"""
        symbols_to_close = []
        
        for symbol, position in self.active_positions.items():
            # Get current candle
            if symbol not in self.data:
                continue
            
            df = self.data[symbol][BacktestConfig.ENTRY_TIMEFRAME]
            
            if current_time not in df.index:
                continue
            
            candle = df.loc[current_time]
            high = candle['high']
            low = candle['low']
            close = candle['close']
            
            # === ADAPTIVE STOP CHECK (before checking TP/SL hits) ===
            # Only check if enabled and position hasn't triggered adaptive stop yet
            if BacktestConfig.ADAPTIVE_STOP_ENABLED and not getattr(position, 'adaptive_stop_triggered', False):
                # Get current market data
                data = self._get_mtf_data(symbol, current_time)
                if data:
                    # Add indicators
                    for tf in data:
                        data[tf] = Indicators.add_all_indicators(data[tf])
                    
                    current_atr = data['primary']['atr'].iloc[-1]
                    current_regime = RegimeDetector.detect_regime(data['primary'])
                    entry_atr = getattr(position, 'entry_atr', 0.0)
                    
                    # Check if adaptive stop should trigger
                    should_trigger, new_stop, reason = self._check_adaptive_stop_trigger(
                        position, close, current_atr, current_regime, entry_atr
                    )
                    
                    if should_trigger and new_stop:
                        self._log('info', f"{current_time} {symbol}: 🛡️ Adaptive stop triggered: {reason} | New SL: ${new_stop:.2f}")
                        
                        # Handle partial vs full protection
                        if BacktestConfig.ADAPTIVE_STOP_PARTIAL_PROTECTION:
                            # Enable partial protection mode - 50% will close at breakeven if stop is hit
                            # Remaining 50% continues with original stop
                            position.stop_loss = new_stop
                            position.adaptive_stop_triggered = True
                            # Note: We set a flag here but don't close position yet
                            # Position will close 50% at breakeven if stop is hit
                            # This matches live bot behavior
                        else:
                            # Full protection: move stop to breakeven
                            position.stop_loss = new_stop
                            position.adaptive_stop_triggered = True
            
            # Check for hits (CONSERVATIVE MODE)
            if position.direction == 'long':
                sl_hit = low <= position.stop_loss
                tp1_hit = not position.tp1_hit and high >= position.take_profits['tp1']['price']
                tp2_hit = not position.tp2_hit and position.tp1_hit and high >= position.take_profits['tp2']['price']
                tp3_hit = not position.tp3_hit and position.tp2_hit and high >= position.take_profits['tp3']['price']
            else:  # short
                sl_hit = high >= position.stop_loss
                tp1_hit = not position.tp1_hit and low <= position.take_profits['tp1']['price']
                tp2_hit = not position.tp2_hit and position.tp1_hit and low <= position.take_profits['tp2']['price']
                tp3_hit = not position.tp3_hit and position.tp2_hit and low <= position.take_profits['tp3']['price']
            
            # Conservative mode: if both SL and TP hit in same candle, assume SL hit first
            if BacktestConfig.CONSERVATIVE_MODE and sl_hit and (tp1_hit or tp2_hit or tp3_hit):
                self._log('debug', f"{current_time} {symbol}: Both TP and SL hit - assuming SL (conservative)")
                self._close_position(position, current_time, position.stop_loss, "stopped", sl_hit=True)
                symbols_to_close.append(symbol)
                continue
            
            # Check TP hits
            if tp3_hit:
                self._handle_tp_hit(position, current_time, 'tp3', position.take_profits['tp3']['price'])
                symbols_to_close.append(symbol)
            elif tp2_hit:
                self._handle_tp_hit(position, current_time, 'tp2', position.take_profits['tp2']['price'])
            elif tp1_hit:
                self._handle_tp_hit(position, current_time, 'tp1', position.take_profits['tp1']['price'])
            
            # Check SL hit
            if sl_hit and symbol not in symbols_to_close:
                self._close_position(position, current_time, position.stop_loss, "stopped", sl_hit=True)
                symbols_to_close.append(symbol)
        
        # Remove closed positions
        for symbol in symbols_to_close:
            if symbol in self.active_positions:
                del self.active_positions[symbol]
    
    def _handle_tp_hit(self, position: Position, current_time: datetime, tp_level: str, tp_price: float):
        """Handle take profit hit
        
        CRITICAL PNL TRACKING:
        - Calculates PnL for this partial exit (after fees and slippage)
        - Adds PnL to position.realized_pnl (accumulates for final trade record)
        - IMMEDIATELY adds PnL to equity (partial exit is realized profit)
        - This matches live bot behavior and prevents duplicate additions
        - When trade fully closes, _record_trade does NOT add to equity again
        """
        # Apply slippage
        if BacktestConfig.USE_MARKET_ORDERS:
            if position.direction == 'long':
                exit_price = tp_price * (1 - BacktestConfig.SLIPPAGE_PERCENT / 100)
            else:
                exit_price = tp_price * (1 + BacktestConfig.SLIPPAGE_PERCENT / 100)
        else:
            exit_price = tp_price
        
        # Calculate PnL for this portion
        close_percent = position.take_profits[tp_level]['close_percent']
        
        # Check if trying to close more than remaining
        if close_percent > position.remaining_percent:
            close_percent = position.remaining_percent
            self._log('debug', f"{current_time} {position.symbol}: {tp_level.upper()} close adjusted from {position.take_profits[tp_level]['close_percent']}% to {close_percent}% (remaining)")
        
        # Use contracts_remaining instead of total contracts
        portion_contracts = position.contracts_remaining * (close_percent / position.remaining_percent)
        
        if position.direction == 'long':
            pnl = (exit_price - position.entry_price) * portion_contracts
        else:
            pnl = (position.entry_price - exit_price) * portion_contracts
        
        # Subtract fees (weighted average of maker/taker)
        exit_value = exit_price * portion_contracts
        fee = self._calculate_fee(exit_value)
        pnl -= fee
        self.total_fees_paid += fee
        self.total_volume_traded += exit_value  # Track volume
        
        # Update position realized PnL (accumulate for final trade record)
        position.realized_pnl += pnl
        position.remaining_percent -= close_percent
        position.contracts_remaining -= portion_contracts
        setattr(position, f'{tp_level}_hit', True)
        
        # ADD PNL TO EQUITY IMMEDIATELY (partial exit is realized profit)
        # This matches live bot behavior and prevents duplicate additions
        self.equity += pnl
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        
        # Extract base asset symbol (remove USDT)
        base_asset = position.symbol[:-4]
        
        self._log('info', f"{current_time} {position.symbol}: {tp_level.upper()} hit | Closed {portion_contracts:.4f} {base_asset} ({close_percent:.1f}%) | P&L: ${pnl:+.2f} | Remaining: {position.contracts_remaining:.4f} {base_asset} ({position.remaining_percent:.1f}%) | Equity: ${self.equity:.2f}")
        
        # Trail stop
        if tp_level == 'tp1':
            # Move to 50% risk
            if position.direction == 'long':
                position.stop_loss = position.stop_loss + (position.entry_price - position.stop_loss) * 0.5
            else:
                position.stop_loss = position.stop_loss - (position.stop_loss - position.entry_price) * 0.5
        elif tp_level == 'tp2':
            # Move to breakeven
            position.stop_loss = position.entry_price
        
        # If fully closed (all TPs hit) or remaining too small, close position
        if position.remaining_percent <= 0:
            self._record_trade(position, current_time, exit_price, 'completed', add_to_equity=False)
        elif position.remaining_percent < 20.0:
            # Auto-close positions with less than 20% remaining
            self._log('info', f"{current_time} {position.symbol}: Auto-closing small remaining position ({position.remaining_percent:.1f}%)")
            self._close_position(position, current_time, exit_price, "auto_close_small_position", sl_hit=False)
    
    def _close_position(self, position: Position, exit_time: datetime, exit_price: float, reason: str, sl_hit: bool = False):
        """Close position and record trade"""
        
        # Check if adaptive stop partial protection should activate
        if (sl_hit and 
            BacktestConfig.ADAPTIVE_STOP_ENABLED and 
            BacktestConfig.ADAPTIVE_STOP_PARTIAL_PROTECTION and 
            getattr(position, 'adaptive_stop_triggered', False)):
            
            # Partial protection: close 50% at breakeven, keep 50% running with original stop
            self._log('info', f"{exit_time} {position.symbol}: ⚡ Partial protection stop hit - exiting 50% at breakeven")
            
            # Exit 50% at breakeven
            entry_price = position.entry_price
            buffer = entry_price * BacktestConfig.ADAPTIVE_STOP_BREAKEVEN_BUFFER
            
            if position.direction == 'long':
                protection_exit_price = entry_price + buffer
            else:
                protection_exit_price = entry_price - buffer
            
            # Calculate 50% portion
            protection_close_pct = 50.0
            partial_contracts = position.contracts_remaining * (protection_close_pct / 100)
            
            # Apply slippage
            if BacktestConfig.USE_MARKET_ORDERS:
                if position.direction == 'long':
                    protection_exit_price = protection_exit_price * (1 - BacktestConfig.SLIPPAGE_PERCENT / 100)
                else:
                    protection_exit_price = protection_exit_price * (1 + BacktestConfig.SLIPPAGE_PERCENT / 100)
            
            # Calculate PnL for partial exit (should be near breakeven)
            if position.direction == 'long':
                partial_pnl = (protection_exit_price - position.entry_price) * partial_contracts
            else:
                partial_pnl = (position.entry_price - protection_exit_price) * partial_contracts
            
            # Subtract fees
            exit_value = protection_exit_price * partial_contracts
            fee = self._calculate_fee(exit_value)
            partial_pnl -= fee
            self.total_fees_paid += fee
            self.total_volume_traded += exit_value
            
            # Update position state
            position.realized_pnl += partial_pnl
            position.remaining_percent -= protection_close_pct
            position.contracts_remaining -= partial_contracts
            
            # Add partial PnL to equity
            self.equity += partial_pnl
            self.daily_pnl += partial_pnl
            self.weekly_pnl += partial_pnl
            
            # Extract base asset symbol
            base_asset = position.symbol[:-4]
            self._log('info', f"{exit_time} {position.symbol}: 🛡️ Partial protection: {partial_contracts:.4f} {base_asset} (50%) closed at ${protection_exit_price:.4f} | P&L: ${partial_pnl:+.2f} | {position.contracts_remaining:.4f} {base_asset} (50%) continues")
            
            # Position continues with remaining 50% - don't close it
            # Reset adaptive stop flag so it won't trigger again
            position.adaptive_stop_triggered = False
            
            # Don't close the position - it continues with 50% remaining
            return
        
        # Normal position close
        # Apply extra slippage on stop losses
        if sl_hit:
            if position.direction == 'long':
                exit_price = exit_price * (1 - BacktestConfig.STOP_LOSS_SLIPPAGE / 100)
            else:
                exit_price = exit_price * (1 + BacktestConfig.STOP_LOSS_SLIPPAGE / 100)
        elif BacktestConfig.USE_MARKET_ORDERS:
            if position.direction == 'long':
                exit_price = exit_price * (1 - BacktestConfig.SLIPPAGE_PERCENT / 100)
            else:
                exit_price = exit_price * (1 + BacktestConfig.SLIPPAGE_PERCENT / 100)
        
        # Use contracts_remaining for accurate tracking
        remaining_contracts = position.contracts_remaining
        
        # Safeguard: if contracts_remaining is 0 or negative, calculate from remaining_percent
        if remaining_contracts <= 0:
            remaining_contracts = position.contracts * (position.remaining_percent / 100)
            self._log('warning', f"{exit_time} {position.symbol}: contracts_remaining was {position.contracts_remaining}, calculated from percent: {remaining_contracts:.4f}")
        
        if position.direction == 'long':
            pnl = (exit_price - position.entry_price) * remaining_contracts
        else:
            pnl = (position.entry_price - exit_price) * remaining_contracts
        
        # Subtract fees (weighted average of maker/taker)
        exit_value = exit_price * remaining_contracts
        fee = self._calculate_fee(exit_value)
        pnl -= fee
        self.total_fees_paid += fee
        self.total_volume_traded += exit_value  # Track volume
        
        # Add remaining position PnL to total realized PnL
        position.realized_pnl += pnl
        
        # ADD REMAINING PNL TO EQUITY IMMEDIATELY
        # (Partial exits already added their PnL, so this only adds the final portion)
        self.equity += pnl
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        
        # Extract base asset symbol
        base_asset = position.symbol[:-4]
        self._log('info', f"{exit_time} {position.symbol}: Position closed ({reason}) | Closed {remaining_contracts:.4f} {base_asset} ({position.remaining_percent:.1f}%) | Exit P&L: ${pnl:+.2f} | Total P&L: ${position.realized_pnl:+.2f} | Equity: ${self.equity:.2f}")
        
        # Record trade WITHOUT adding to equity again (already added incrementally)
        self._record_trade(position, exit_time, exit_price, reason, add_to_equity=False)
    
    def _record_trade(self, position: Position, exit_time: datetime, exit_price: float, reason: str, add_to_equity: bool = True):
        """Record completed trade
        
        Args:
            add_to_equity: If False, equity was already updated incrementally during partial exits.
                          This prevents duplicate PnL additions.
        """
        duration = (exit_time - position.entry_time).total_seconds() / 3600
        pnl_percent = (position.realized_pnl / (position.entry_price * position.contracts)) * 100
        
        trade = Trade(
            symbol=position.symbol,
            direction=position.direction,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            pnl=position.realized_pnl,  # Total PnL including all fees from all exits
            pnl_percent=pnl_percent,
            exit_reason=reason,
            regime=position.regime,
            score=position.score,
            duration_hours=duration
        )
        
        self.closed_trades.append(trade)
        
        # Only add to equity if not already added incrementally
        # (Prevents duplicate additions when partial exits already updated equity)
        if add_to_equity:
            self.equity += position.realized_pnl
            self.daily_pnl += position.realized_pnl
            self.weekly_pnl += position.realized_pnl
        
        # Track consecutive losses (based on TOTAL trade PnL including all fees)
        if position.realized_pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= BacktestConfig.MAX_CONSECUTIVE_LOSSES:
                self.cooldown_until = exit_time + timedelta(hours=4)  # 4-hour cooldown
                self.daily_threshold_penalty = 5  # +5 threshold penalty
                self._log('info', f"{exit_time}: 4-hour cooldown activated until {self.cooldown_until} | Threshold +5")
        else:
            self.consecutive_losses = 0
        
        # Check if weekly loss limit hit - activate 12-hour cooldown
        if BacktestConfig.MAX_WEEKLY_LOSS and self.weekly_pnl < 0:
            weekly_loss_pct = abs(self.weekly_pnl / self.equity)
            if weekly_loss_pct >= BacktestConfig.MAX_WEEKLY_LOSS and not self.weekly_cooldown_until:
                self.weekly_cooldown_until = exit_time + timedelta(hours=12)  # 12-hour cooldown
                self.weekly_threshold_penalty = 5  # +5 threshold penalty
                self._log('info', f"{exit_time}: 12-hour weekly cooldown activated until {self.weekly_cooldown_until} | Threshold +5")
        
        self._log('info', f"{exit_time} {position.symbol}: Trade closed | {reason} | Total P&L: ${position.realized_pnl:+.2f} | Equity: ${self.equity:.2f}")
    
    def _scan_for_signals(self, current_time: datetime):
        """Scan for new trading signals (uses EXACT live bot logic)"""
        # === PHASE 1: BTC REGIME CHECK (Market-wide filter) ===
        # Check BTC conditions BEFORE individual symbol analysis
        btc_threshold_adj = 0
        btc_position_mult = 1.0
        btc_max_signals_adj = 0
        
        if 'BTCUSDT' in self.data:
            try:
                btc_data = self._get_mtf_data('BTCUSDT', current_time)
                if btc_data:
                    # Validate BTC data has enough candles for indicators
                    if len(btc_data['htf']) < 200:
                        self._log('debug', f"{current_time}: Insufficient BTC data for regime check ({len(btc_data['htf'])} candles)")
                        btc_threshold_adj = 5  # Conservative default
                        btc_position_mult = 0.9
                        btc_max_signals_adj = 0
                    else:
                        btc_data['htf'] = Indicators.add_all_indicators(btc_data['htf'])
                        btc_regime_info = RegimeDetector.check_btc_regime(btc_data['htf'])
                        
                        # Apply BTC regime adjustments
                        btc_threshold_adj = btc_regime_info['score_threshold_adj']
                        btc_position_mult = btc_regime_info['position_size_mult']
                        btc_max_signals_adj = btc_regime_info['max_signals_adj']
                        
                        self._log('debug', f"{current_time}: BTC Regime {btc_regime_info['regime']} - Threshold adj: +{btc_threshold_adj}, Position mult: {btc_position_mult:.2f}")
            except Exception as e:
                self._log('warning', f"BTC regime check failed: {e}, proceeding with defaults")
                btc_threshold_adj = 5
                btc_position_mult = 0.9
                btc_max_signals_adj = 0
        
        # Check adjusted max signals limit
        current_signals = len(self.active_positions)
        adjusted_max_signals = max(1, BacktestConfig.MAX_TOTAL_ACTIVE_SIGNALS + btc_max_signals_adj)
        
        if current_signals >= adjusted_max_signals:
            self._log('debug', f"{current_time}: Max signals reached ({current_signals}/{adjusted_max_signals}) due to BTC regime")
            return
        
        # === PHASE 2: SCAN INDIVIDUAL SYMBOLS ===
        # Scan all symbols in the loaded data
        for symbol in self.data.keys():
            # Skip if position already exists
            if symbol in self.active_positions:
                continue
            
            # Check position limits
            if len(self.active_positions) >= adjusted_max_signals:
                continue
            
            try:
                # Get multi-timeframe data UP TO current_time (no future data!)
                data = self._get_mtf_data(symbol, current_time)
                
                if not data:
                    continue
                
                # Validate sufficient data for indicators (need at least 200 candles for EMA200)
                min_candles_needed = 200
                if (len(data['htf']) < min_candles_needed or 
                    len(data['primary']) < min_candles_needed or 
                    len(data['entry']) < min_candles_needed):
                    self._log('debug', f"{current_time} {symbol}: Insufficient data (HTF: {len(data['htf'])}, Primary: {len(data['primary'])}, Entry: {len(data['entry'])})")
                    continue
                
                # Add indicators
                for tf in data:
                    data[tf] = Indicators.add_all_indicators(data[tf])
                
                # Check individual symbol regime
                regime = RegimeDetector.detect_regime(data['primary'])
                
                if not RegimeDetector.should_trade_regime(regime):
                    continue
                
                # Get base score threshold based on equity state
                account_state = 'drawdown' if self.equity < self.initial_equity * 0.98 else 'normal'
                base_threshold = BacktestConfig.SIGNAL_THRESHOLD_DRAWDOWN if account_state == 'drawdown' else BacktestConfig.SIGNAL_THRESHOLD_NORMAL
                
                # Apply BTC regime adjustment to threshold
                threshold = base_threshold + btc_threshold_adj
                
                # Apply cooldown penalty adjustment to threshold
                cooldown_penalty = self.daily_threshold_penalty + self.weekly_threshold_penalty
                if cooldown_penalty > 0:
                    threshold += cooldown_penalty
                    self._log('info', f"{current_time} {symbol}: Cooldown penalty active +{cooldown_penalty}pt | Adjusted threshold: {threshold}")
                
                # Check long entry
                long_check = EntryLogic.check_long_entry(data)
                score, breakdown = SignalScorer.calculate_score_with_breakdown(data, 'long', symbol)
                
                # Allow signal if entry requirements met OR score >= 85 (exceptional score override)
                if (long_check['valid'] or score >= 85) and score >= threshold:
                    reason = long_check['reason'] if long_check['valid'] else f"High score override (85+): {long_check['reason']}"
                    self._create_position(symbol, 'long', data, current_time, reason, score, regime, btc_position_mult)
                    continue
                
                # Check short entry
                short_check = EntryLogic.check_short_entry(data)
                score, breakdown = SignalScorer.calculate_score_with_breakdown(data, 'short', symbol)
                
                # Allow signal if entry requirements met OR score >= 85 (exceptional score override)
                if (short_check['valid'] or score >= 85) and score >= threshold:
                    reason = short_check['reason'] if short_check['valid'] else f"High score override (85+): {short_check['reason']}"
                    self._create_position(symbol, 'short', data, current_time, reason, score, regime, btc_position_mult)
                
            except Exception as e:
                self._log('error', f"Error scanning {symbol} at {current_time}: {e}")
    
    def _create_position(self, symbol: str, direction: str, data: Dict, entry_time: datetime, reason: str, score: int, regime: str, btc_position_mult: float = 1.0):
        """Create new position (on candle close) - MATCHES LIVE BOT LOGIC"""
        entry_price = data['entry']['close'].iloc[-1]
        
        # Apply entry slippage
        if BacktestConfig.USE_MARKET_ORDERS:
            if direction == 'long':
                entry_price = entry_price * (1 + BacktestConfig.SLIPPAGE_PERCENT / 100)
            else:
                entry_price = entry_price * (1 - BacktestConfig.SLIPPAGE_PERCENT / 100)
        
        # Calculate stop loss
        stop_loss = StopTPCalculator.calculate_stop_loss(data, direction, entry_price)
        
        # Calculate take profits (regime-adjusted)
        take_profits = StopTPCalculator.calculate_take_profits(entry_price, stop_loss, direction, regime)
        
        # Calculate position size
        available_margin = self.equity - sum(p.margin_used for p in self.active_positions.values())
        
        position_size_info = PositionSizer.calculate_position_size(
            self.equity,
            entry_price,
            stop_loss,
            symbol,
            available_margin=available_margin
        )
        
        if not position_size_info:
            return
        
        contracts = position_size_info['contracts']
        margin_used = position_size_info['margin_used']
        
        # Apply BTC regime position size adjustment
        if btc_position_mult < 1.0:
            original_contracts = contracts
            contracts = max(1, int(contracts * btc_position_mult))
            margin_used = margin_used * btc_position_mult
            self._log('debug', f"{entry_time} {symbol}: BTC regime adjusted position: {original_contracts} → {contracts} contracts ({btc_position_mult:.1%} multiplier)")
        
        # Entry fee (weighted average of maker/taker)
        entry_value = entry_price * contracts
        entry_fee = self._calculate_fee(entry_value)
        self.total_fees_paid += entry_fee
        self.total_volume_traded += entry_value  # Track volume
        
        # Deduct entry fee from equity immediately (realized cost)
        self.equity -= entry_fee
        self.daily_pnl -= entry_fee
        self.weekly_pnl -= entry_fee
        
        # Get entry ATR for adaptive stop monitoring
        entry_atr = data['primary']['atr'].iloc[-1]
        
        # Create position
        position = Position(
            symbol=symbol,
            direction=direction,
            entry_time=entry_time,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profits=take_profits,
            position_size=entry_value,
            contracts=contracts,
            margin_used=margin_used,
            score=score,
            regime=regime,
            entry_reason=reason,
            contracts_remaining=contracts,  # Initialize with full position
            realized_pnl=-entry_fee  # Start with negative (entry fee)
        )
        
        # Store entry ATR for adaptive stops (add as attribute)
        position.entry_atr = entry_atr
        
        self.active_positions[symbol] = position
        
        # Extract base asset symbol
        base_asset = symbol[:-4]
        self._log('info', f"{entry_time} {symbol}: {direction.upper()} entry | Price: ${entry_price:.2f} | Position: {contracts:.4f} {base_asset} (100%) | Score: {score} | Regime: {regime}")
    
    def _get_mtf_data(self, symbol: str, current_time: datetime) -> Optional[Dict]:
        """Get multi-timeframe data up to current_time (NO FUTURE DATA)"""
        if symbol not in self.data:
            return None
        
        try:
            # Get data for each timeframe
            htf_df = self.data[symbol][BacktestConfig.HTF_TIMEFRAME]
            primary_df = self.data[symbol][BacktestConfig.PRIMARY_TIMEFRAME]
            entry_df = self.data[symbol][BacktestConfig.ENTRY_TIMEFRAME]
            
            # Slice data up to current time (inclusive)
            htf_data = htf_df[htf_df.index <= current_time].tail(200)
            primary_data = primary_df[primary_df.index <= current_time].tail(200)
            entry_data = entry_df[entry_df.index <= current_time].tail(200)
            
            if htf_data.empty or primary_data.empty or entry_data.empty:
                return None
            
            return {
                'htf': htf_data.copy(),
                'primary': primary_data.copy(),
                'entry': entry_data.copy()
            }
            
        except Exception as e:
            self._log('error', f"Error getting MTF data for {symbol}: {e}")
            return None
    
    def _can_trade(self, current_time: datetime) -> Tuple[bool, str]:
        """Check if trading allowed (same logic as live bot)"""
        # Check cooldown expiry
        if self.cooldown_until and current_time < self.cooldown_until:
            remaining = (self.cooldown_until - current_time).total_seconds() / 3600
            return False, f"Cooldown for {remaining:.1f}h more | Threshold +{self.daily_threshold_penalty}"
        elif self.cooldown_until and current_time >= self.cooldown_until:
            self.cooldown_until = None
            self.consecutive_losses = 0
            self.daily_threshold_penalty = 0  # Clear penalty when cooldown expires
            self._log('info', f"{current_time}: Cooldown expired - Clearing threshold penalty")
        
        # Check weekly cooldown expiry
        if self.weekly_cooldown_until and current_time < self.weekly_cooldown_until:
            remaining = (self.weekly_cooldown_until - current_time).total_seconds() / 3600
            return False, f"Weekly cooldown for {remaining:.1f}h more | Threshold +{self.weekly_threshold_penalty}"
        elif self.weekly_cooldown_until and current_time >= self.weekly_cooldown_until:
            self.weekly_cooldown_until = None
            self.weekly_threshold_penalty = 0  # Clear penalty when cooldown expires
            self._log('info', f"{current_time}: Weekly cooldown expired - Clearing threshold penalty")
        
        # Check weekly loss
        if BacktestConfig.MAX_WEEKLY_LOSS and self.weekly_pnl < 0:
            weekly_loss_pct = abs(self.weekly_pnl / self.equity)
            if weekly_loss_pct >= BacktestConfig.MAX_WEEKLY_LOSS:
                return False, f"Weekly loss limit hit: ${self.weekly_pnl:.2f}"
        
        # Check consecutive losses
        if self.consecutive_losses >= BacktestConfig.MAX_CONSECUTIVE_LOSSES:
            return False, f"{self.consecutive_losses} consecutive losses"
        
        return True, "OK"
    
    def _check_adaptive_stop_trigger(
        self,
        position: Position,
        current_price: float,
        current_atr: float,
        current_regime: str,
        entry_atr: float
    ) -> Tuple[bool, Optional[float], str]:
        """
        Check if adaptive stop protection should be triggered
        
        Mirrors the logic from SignalTracker.check_adaptive_stop_trigger
        
        Returns:
            (should_trigger, new_stop_level, reason)
        """
        # Calculate profit in R multiples
        entry = position.entry_price
        original_stop = position.stop_loss  # Use current stop as original (we don't modify during trailing)
        direction = position.direction
        
        if direction == 'long':
            stop_distance = entry - original_stop
            profit_distance = current_price - entry
        else:  # short
            stop_distance = original_stop - entry
            profit_distance = entry - current_price
        
        # Avoid division by zero
        if stop_distance <= 0:
            return (False, None, "invalid stop distance")
        
        profit_r = profit_distance / stop_distance
        
        # Must be profitable enough
        if profit_r < BacktestConfig.ADAPTIVE_STOP_MIN_PROFIT_R:
            return (False, None, f"profit {profit_r:.2f}R below threshold")
        
        # Check for trigger conditions
        entry_regime = position.regime
        
        trigger_reason = ""
        
        # Condition 1: Volatility spike
        if entry_atr > 0 and current_atr > entry_atr * BacktestConfig.ADAPTIVE_STOP_VOLATILITY_SPIKE:
            spike_pct = ((current_atr / entry_atr) - 1) * 100
            trigger_reason = f"volatility spike +{spike_pct:.1f}%"
        
        # Condition 2: Regime deterioration
        if BacktestConfig.ADAPTIVE_STOP_REGIME_CHANGE:
            if entry_regime in ['trending', 'strong_trend'] and current_regime in ['choppy', 'ranging', 'low_volatility']:
                if trigger_reason:
                    trigger_reason += f" + regime {entry_regime}→{current_regime}"
                else:
                    trigger_reason = f"regime change {entry_regime}→{current_regime}"
        
        if not trigger_reason:
            return (False, None, "no trigger conditions met")
        
        # Calculate new stop: breakeven + small buffer
        buffer = entry * BacktestConfig.ADAPTIVE_STOP_BREAKEVEN_BUFFER
        
        if direction == 'long':
            new_stop = entry + buffer
            # Only tighten, never widen
            if new_stop <= position.stop_loss:
                return (False, None, "would widen stop")
        else:  # short
            new_stop = entry - buffer
            # Only tighten, never widen
            if new_stop >= position.stop_loss:
                return (False, None, "would widen stop")
        
        return (True, new_stop, trigger_reason)
    
    def _check_daily_reset(self, current_time: datetime):
        """Reset daily counters"""
        if self.last_reset_date is None:
            self.last_reset_date = current_time.date()
            return
        
        if current_time.date() > self.last_reset_date:
            self.daily_pnl = 0.0
            self.last_reset_date = current_time.date()
            
            # Weekly reset (Monday)
            if current_time.weekday() == 0:
                self.weekly_pnl = 0.0
                self.weekly_cooldown_until = None
                self.weekly_threshold_penalty = 0
    
    def _close_all_positions(self, end_time: datetime, reason: str):
        """Close all remaining positions at end of backtest"""
        for symbol in list(self.active_positions.keys()):
            position = self.active_positions[symbol]
            
            # Get last available price
            df = self.data[symbol][BacktestConfig.ENTRY_TIMEFRAME]
            last_price = df.loc[end_time, 'close'] if end_time in df.index else position.entry_price
            
            self._close_position(position, end_time, last_price, reason)
            del self.active_positions[symbol]
    
    def _calculate_results(self) -> Dict:
        """Calculate comprehensive backtest metrics"""
        if not self.closed_trades:
            return {'error': 'No trades executed'}
        
        # Convert trades to DataFrame for analysis
        trades_df = pd.DataFrame([vars(t) for t in self.closed_trades])
        
        # Basic metrics
        total_trades = len(self.closed_trades)
        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] <= 0]
        
        # Directional bias tracking
        long_trades = trades_df[trades_df['direction'] == 'long']
        short_trades = trades_df[trades_df['direction'] == 'short']
        
        long_count = len(long_trades)
        short_count = len(short_trades)
        long_pnl = long_trades['pnl'].sum() if len(long_trades) > 0 else 0
        short_pnl = short_trades['pnl'].sum() if len(short_trades) > 0 else 0
        
        long_win_rate = (len(long_trades[long_trades['pnl'] > 0]) / long_count * 100) if long_count > 0 else 0
        short_win_rate = (len(short_trades[short_trades['pnl'] > 0]) / short_count * 100) if short_count > 0 else 0
        
        long_avg_pnl = long_trades['pnl'].mean() if len(long_trades) > 0 else 0
        short_avg_pnl = short_trades['pnl'].mean() if len(short_trades) > 0 else 0
        
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        # P&L metrics
        total_pnl = trades_df['pnl'].sum()
        gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
        
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy
        expectancy = total_pnl / total_trades if total_trades > 0 else 0
        
        # Equity curve analysis
        equity_df = pd.DataFrame(self.equity_curve, columns=['time', 'equity'])
        equity_df.set_index('time', inplace=True)
        
        # Drawdown calculation
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
        # Returns
        final_equity = self.equity
        total_return = ((final_equity - self.initial_equity) / self.initial_equity) * 100
        
        # Sharpe ratio (simplified - assumes daily data)
        equity_df['returns'] = equity_df['equity'].pct_change()
        sharpe_ratio = (equity_df['returns'].mean() / equity_df['returns'].std() * np.sqrt(252)) if equity_df['returns'].std() > 0 else 0
        
        # Longest losing streak
        streak = 0
        max_streak = 0
        for trade in self.closed_trades:
            if trade.pnl < 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        
        results = {
            'total_trades': total_trades,
            'wins': win_count,
            'losses': loss_count,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'total_return_pct': round(total_return, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'expectancy': round(expectancy, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'longest_losing_streak': max_streak,
            'initial_equity': self.initial_equity,
            'final_equity': round(final_equity, 2),
            'total_fees_paid': round(self.total_fees_paid, 2),
            'total_volume_traded': round(self.total_volume_traded, 2),
            'effective_fee_rate': round((self.total_fees_paid / self.total_volume_traded * 100), 4) if self.total_volume_traded > 0 else 0,
            'avg_duration_hours': round(trades_df['duration_hours'].mean(), 2),
            # Session tracking - directional bias
            'long_trades': long_count,
            'short_trades': short_count,
            'long_short_ratio': round(long_count / short_count, 2) if short_count > 0 else float('inf'),
            'long_pnl': round(long_pnl, 2),
            'short_pnl': round(short_pnl, 2),
            'long_win_rate': round(long_win_rate, 2),
            'short_win_rate': round(short_win_rate, 2),
            'long_avg_pnl': round(long_avg_pnl, 2),
            'short_avg_pnl': round(short_avg_pnl, 2),
            'trades_by_regime': trades_df.groupby('regime')['pnl'].agg(['count', 'sum', 'mean']).to_dict(),
            'trades_by_symbol': trades_df.groupby('symbol')['pnl'].agg(['count', 'sum', 'mean']).to_dict(),
            'trades_by_exit_reason': trades_df.groupby('exit_reason')['pnl'].agg(['count', 'sum']).to_dict()
        }
        
        return results
