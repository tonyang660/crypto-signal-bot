import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger
from src.core.config import Config

class SignalTracker:
    """
    Track active and historical signals
    
    Critical Rules:
    - Max 1 active signal per pair
    - Max 1 BTC signal at a time
    - Max 3 total active signals
    """
    
    def __init__(self):
        self.active_signals: Dict[str, Dict] = {}
        self.history: List[Dict] = []
        
        # Ensure data directory exists
        Path(Config.ACTIVE_SIGNALS_FILE).parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing signals
        self._load_active_signals()
        self._load_history()
        
        # Create initial files if they don't exist
        if not Path(Config.ACTIVE_SIGNALS_FILE).exists():
            self._save_active_signals()
        if not Path(Config.HISTORY_SIGNALS_FILE).exists():
            self._save_history()
    
    def get_total_margin_used(self) -> float:
        """Calculate total margin currently used by all active signals"""
        total_margin = 0.0
        
        for signal in self.active_signals.values():
            # Get margin for remaining position percentage
            position_size = signal.get('position_size', {})
            margin_used = position_size.get('margin_used', 0)
            remaining_pct = signal.get('remaining_percent', 100) / 100
            
            # Only count margin for the remaining open position
            total_margin += margin_used * remaining_pct
        
        return total_margin
    
    def get_available_margin(self, total_equity: float) -> float:
        """Calculate available margin for new positions"""
        used_margin = self.get_total_margin_used()
        available = total_equity - used_margin
        
        logger.debug(f"Margin: Total equity ${total_equity:.2f} | Used ${used_margin:.2f} | Available ${available:.2f}")
        
        return available
    
    def can_create_signal(self, symbol: str) -> Tuple[bool, str]:
        """
        Check if new signal can be created for symbol
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Check if signal already exists for this pair
        if symbol in self.active_signals:
            return False, f"Signal already exists for {symbol}"
        
        # Check BTC restriction (only 1 BTC signal at a time)
        if symbol == 'BTCUSDT':
            btc_signals = [s for s in self.active_signals.keys() if s == 'BTCUSDT']
            if btc_signals:
                return False, "BTC signal already active"
        
        # Check max total active signals
        if len(self.active_signals) >= Config.MAX_TOTAL_ACTIVE_SIGNALS:
            return False, f"Max active signals ({Config.MAX_TOTAL_ACTIVE_SIGNALS}) reached"
        
        # Check correlation group limits (Phase 3)
        symbol_group = None
        for group_name, pairs in Config.CORRELATION_GROUPS.items():
            if symbol in pairs:
                symbol_group = group_name
                break
        
        if symbol_group:
            # Count how many active signals are in this correlation group
            group_signals = 0
            for active_symbol in self.active_signals.keys():
                if active_symbol in Config.CORRELATION_GROUPS[symbol_group]:
                    group_signals += 1
            
            if group_signals >= Config.MAX_CORRELATED_SIGNALS:
                return False, f"Max correlated signals ({Config.MAX_CORRELATED_SIGNALS}) reached for group '{symbol_group}'"
        
        return True, "Can create signal"
    
    def create_signal(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profits: Dict,
        position_size: Dict,
        score: int,
        entry_reason: str,
        regime: str = 'unknown',
        atr: float = 0.0
    ) -> str:
        """
        Create new signal
        
        Args:
            regime: Market regime at entry (for analytics)
        
        Returns:
            Signal ID
        """
        try:
            # Generate unique signal ID
            signal_id = f"{symbol}_{direction}_{int(datetime.now().timestamp())}"
            
            signal = {
                'signal_id': signal_id,
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'original_stop_loss': stop_loss,  # Store original for R calculation
                'take_profits': take_profits,
                'position_size': position_size,
                'score': score,
                'entry_reason': entry_reason,
                'regime': regime,  # Store regime for analytics
                'status': 'active',
                'entry_time': datetime.now().isoformat(),  # Use entry_time for consistency
                'tp1_hit': False,
                'tp2_hit': False,
                'tp3_hit': False,
                'stop_hit': False,
                'remaining_percent': 100,
                'realized_pnl': 0.0,
                'current_price': entry_price,
                'best_price': entry_price,  # Track best price achieved
                'entry_atr': atr,  # Store entry ATR for adaptive stop comparison
                'entry_regime': regime,  # Store entry regime for change detection
                'adaptive_stop_triggered': False,  # Track if adaptive protection activated
                'partial_protection_active': False  # Track if 50% protected at breakeven, 50% running
            }
            
            # Add to active signals
            self.active_signals[symbol] = signal
            
            # Save to file
            self._save_active_signals()
            
            logger.info(f"✅ Signal created: {signal_id}")
            
            return signal_id
            
        except Exception as e:
            logger.error(f"Error creating signal: {e}")
            return ""
    
    def update_signal_price(self, symbol: str, current_price: float) -> Optional[Dict]:
        """
        Update signal with current price and check for TP/SL hits
        
        Returns:
            Dict with hit information if TP or SL triggered, else None
        """
        if symbol not in self.active_signals:
            return None
        
        signal = self.active_signals[symbol]
        signal['current_price'] = current_price
        
        direction = signal['direction']
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        tps = signal['take_profits']
        
        # Track best price achieved
        if 'best_price' not in signal:
            signal['best_price'] = entry_price
        
        if direction == 'long':
            signal['best_price'] = max(signal['best_price'], current_price)
        else:
            signal['best_price'] = min(signal['best_price'], current_price)
        
        hit_info = None
        
        # Check for hits based on direction
        if direction == 'long':
            # Check stop loss
            if current_price <= stop_loss and not signal['stop_hit']:
                hit_info = self._handle_stop_loss_hit(symbol)
            
            # Check TP levels (in order)
            elif current_price >= tps['tp1']['price'] and not signal['tp1_hit']:
                hit_info = self._handle_tp_hit(symbol, 'tp1')
            
            elif current_price >= tps['tp2']['price'] and not signal['tp2_hit'] and signal['tp1_hit']:
                hit_info = self._handle_tp_hit(symbol, 'tp2')
            
            elif current_price >= tps['tp3']['price'] and not signal['tp3_hit'] and signal['tp2_hit']:
                hit_info = self._handle_tp_hit(symbol, 'tp3')
            
            # Near-TP protection: Check if price got very close but is reversing
            elif Config.NEAR_TP_ENABLED and not signal['stop_hit']:
                hit_info = self._check_near_tp_reversal(signal, symbol)
        
        else:  # short
            # Check stop loss
            if current_price >= stop_loss and not signal['stop_hit']:
                hit_info = self._handle_stop_loss_hit(symbol)
            
            # Check TP levels
            elif current_price <= tps['tp1']['price'] and not signal['tp1_hit']:
                hit_info = self._handle_tp_hit(symbol, 'tp1')
            
            elif current_price <= tps['tp2']['price'] and not signal['tp2_hit'] and signal['tp1_hit']:
                hit_info = self._handle_tp_hit(symbol, 'tp2')
            
            elif current_price <= tps['tp3']['price'] and not signal['tp3_hit'] and signal['tp2_hit']:
                hit_info = self._handle_tp_hit(symbol, 'tp3')
            
            # Near-TP protection: Check if price got very close but is reversing
            elif Config.NEAR_TP_ENABLED and not signal['stop_hit']:
                hit_info = self._check_near_tp_reversal(signal, symbol)
        
        # Save updated state
        self._save_active_signals()
        
        return hit_info
    
    def _check_near_tp_reversal(self, signal: Dict, symbol: str) -> Optional[Dict]:
        """
        Check if price got very close to next TP but is now reversing.
        This prevents frustrating situations where price almost hits TP but reverses to SL.
        
        Logic:
        - Determine which TP level is next
        - Calculate if best_price achieved >= X% of distance to that TP
        - If yes, and price has pulled back, trigger TP early to lock in profit
        """
        direction = signal['direction']
        entry = signal['entry_price']
        current = signal['current_price']
        best = signal['best_price']
        tps = signal['take_profits']
        
        # Determine next TP level
        if not signal['tp1_hit']:
            next_tp_level = 'tp1'
        elif not signal['tp2_hit']:
            next_tp_level = 'tp2'
        elif not signal['tp3_hit']:
            next_tp_level = 'tp3'
        else:
            return None  # All TPs already hit
        
        next_tp_price = tps[next_tp_level]['price']
        
        # Calculate progress toward TP
        if direction == 'long':
            distance_to_tp = next_tp_price - entry
            best_progress = best - entry
            progress_pct = best_progress / distance_to_tp if distance_to_tp > 0 else 0
            
            # Check if price achieved threshold and is now pulling back
            if progress_pct >= Config.NEAR_TP_THRESHOLD:
                pullback_pct = (best - current) / best if best > 0 else 0
                # Trigger if pulled back more than 0.5% from best
                if pullback_pct >= 0.005:
                    logger.warning(f"{symbol}: Near-TP protection triggered! Best: ${best:.4f} ({progress_pct*100:.1f}% to {next_tp_level.upper()}), Current: ${current:.4f} - Taking profit early")
                    return self._handle_tp_hit(symbol, next_tp_level, early_exit=True)
        else:
            distance_to_tp = entry - next_tp_price
            best_progress = entry - best
            progress_pct = best_progress / distance_to_tp if distance_to_tp > 0 else 0
            
            # Check if price achieved threshold and is now pulling back
            if progress_pct >= Config.NEAR_TP_THRESHOLD:
                pullback_pct = (current - best) / best if best > 0 else 0
                # Trigger if pulled back more than 0.5% from best
                if pullback_pct >= 0.005:
                    logger.warning(f"{symbol}: Near-TP protection triggered! Best: ${best:.4f} ({progress_pct*100:.1f}% to {next_tp_level.upper()}), Current: ${current:.4f} - Taking profit early")
                    return self._handle_tp_hit(symbol, next_tp_level, early_exit=True)
        
        return None
    
    def _calculate_trailing_stop(self, signal: Dict, tp_level: str) -> float:
        """
        Calculate new stop loss based on trailing strategy
        
        Strategy:
        - After TP1: Move SL to 50% of original risk (halfway to entry)
        - After TP2: Move SL to breakeven (entry price)
        - After TP3: Keep at breakeven or trail slightly
        """
        entry_price = signal['entry_price']
        original_stop = signal['stop_loss']
        direction = signal['direction']
        
        if tp_level == 'tp1':
            # Move to 50% of original risk
            if direction == 'long':
                # Entry above stop, move stop halfway up
                new_stop = original_stop + (entry_price - original_stop) * 0.5
            else:  # short
                # Entry below stop, move stop halfway down
                new_stop = original_stop - (original_stop - entry_price) * 0.5
            
            logger.debug(f"TP1 trailing: Moving stop to 50% risk level")
            return new_stop
        
        elif tp_level == 'tp2':
            # Move to breakeven
            logger.debug(f"TP2 trailing: Moving stop to breakeven")
            return entry_price
        
        elif tp_level == 'tp3':
            # Keep at breakeven (already moved after TP2)
            # Could implement ATR trailing here in the future
            return signal['stop_loss']  # Keep current stop
        
        return signal['stop_loss']  # Default: keep current
    
    def _handle_tp_hit(self, symbol: str, tp_level: str, early_exit: bool = False) -> Dict:
        """Handle take profit hit
        
        Args:
            symbol: Trading pair symbol
            tp_level: TP level hit (tp1, tp2, tp3)
            early_exit: If True, this is a near-TP protection trigger (not exact TP hit)
        """
        signal = self.active_signals[symbol]
        
        # Mark TP as hit
        signal[f'{tp_level}_hit'] = True
        
        # Calculate closed percentage
        close_percent = signal['take_profits'][tp_level]['close_percent']
        
        # Calculate PnL for this portion
        entry_price = signal['entry_price']
        current_price = signal['current_price']
        direction = signal['direction']
        contracts = signal['position_size']['contracts']
        
        portion_contracts = contracts * (close_percent / 100)
        
        if direction == 'long':
            pnl = (current_price - entry_price) * portion_contracts
        else:
            pnl = (entry_price - current_price) * portion_contracts
        
        # Update signal
        signal['realized_pnl'] += pnl
        signal['remaining_percent'] -= close_percent
        
        # Apply trailing stop strategy
        old_stop = signal['stop_loss']
        new_stop = self._calculate_trailing_stop(signal, tp_level)
        
        if new_stop != old_stop:
            signal['stop_loss'] = new_stop
            logger.info(f"📈 Stop loss adjusted for {symbol}: ${old_stop:.4f} → ${new_stop:.4f} (Trailing after {tp_level.upper()})")
        
        hit_info = {
            'type': 'tp_hit',
            'level': tp_level,
            'price': current_price,
            'close_percent': close_percent,
            'pnl': pnl,
            'total_pnl': signal['realized_pnl'],
            'remaining_percent': signal['remaining_percent'],
            'new_stop_loss': new_stop,
            'signal': signal.copy()  # Include signal data
        }
        
        logger.info(f"🎯 {tp_level.upper()} hit for {symbol} | PnL: ${pnl:.2f}")
        
        # If all position closed, move to history
        if signal['remaining_percent'] <= 0:
            self._close_signal(symbol, 'completed')
        
        return hit_info
    
    def _handle_stop_loss_hit(self, symbol: str) -> Dict:
        """Handle stop loss hit"""
        signal = self.active_signals[symbol]
        
        # Check if partial protection is active (50% at breakeven, 50% at original stop)
        if signal.get('partial_protection_active', False):
            logger.info(f"⚡ Partial protection stop hit for {symbol} - exiting 50% at breakeven")
            
            # Exit 50% of remaining position at breakeven
            entry_price = signal['entry_price']
            buffer = entry_price * Config.ADAPTIVE_STOP_BREAKEVEN_BUFFER
            direction = signal['direction']
            
            if direction == 'long':
                exit_price = entry_price + buffer
            else:
                exit_price = entry_price - buffer
            
            contracts = signal['position_size']['contracts']
            remaining_contracts = contracts * (signal['remaining_percent'] / 100)
            partial_contracts = remaining_contracts * 0.5  # Exit 50%
            
            # Calculate PnL for this partial exit (should be near breakeven)
            if direction == 'long':
                partial_pnl = (exit_price - entry_price) * partial_contracts
            else:
                partial_pnl = (entry_price - exit_price) * partial_contracts
            
            # Update signal state
            signal['realized_pnl'] += partial_pnl
            signal['remaining_percent'] *= 0.5  # 50% remains
            signal['stop_loss'] = signal['original_stop_loss']  # Restore original stop for remaining 50%
            signal['partial_protection_active'] = False  # Deactivate partial protection
            
            self._save_active_signals()
            
            hit_info = {
                'type': 'partial_protection_exit',
                'price': exit_price,
                'partial_pnl': partial_pnl,
                'percent_exited': 50,
                'percent_remaining': signal['remaining_percent'],
                'new_stop': signal['stop_loss'],
                'signal': signal.copy()
            }
            
            logger.success(
                f"✅ {symbol} Partial protection: 50% exited at ${exit_price:.4f} "
                f"(PnL: ${partial_pnl:.2f}), 50% continues with stop at ${signal['stop_loss']:.4f}"
            )
            
            return hit_info
        
        # Normal full stop loss hit
        signal['stop_hit'] = True
        
        # Calculate loss
        entry_price = signal['entry_price']
        stop_price = signal['stop_loss']
        contracts = signal['position_size']['contracts']
        direction = signal['direction']
        
        # Account for any already realized profits from TPs
        remaining_contracts = contracts * (signal['remaining_percent'] / 100)
        
        if direction == 'long':
            loss = (stop_price - entry_price) * remaining_contracts
        else:
            loss = (entry_price - stop_price) * remaining_contracts
        
        total_pnl = signal['realized_pnl'] + loss
        
        hit_info = {
            'type': 'stop_hit',
            'price': stop_price,  # Use actual SL price, not current market price (simulates real order execution)
            'loss': loss,
            'total_pnl': total_pnl,
            'signal': signal.copy()  # Include signal data before closing
        }
        
        logger.warning(f"🛑 Stop loss hit for {symbol} | Loss: ${loss:.2f} | Total PnL: ${total_pnl:.2f}")
        
        # Close signal
        self._close_signal(symbol, 'stopped')
        
        return hit_info
    
    def _close_signal(self, symbol: str, status: str) -> None:
        """Move signal from active to history"""
        if symbol not in self.active_signals:
            return
        
        signal = self.active_signals[symbol]
        signal['status'] = status
        signal['closed_at'] = datetime.now().isoformat()
        
        # Add to history
        self.history.append(signal)
        
        # Remove from active
        del self.active_signals[symbol]
        
        # Save both files
        self._save_active_signals()
        self._save_history()
        
        logger.info(f"📋 Signal closed: {symbol} | Status: {status}")
    
    def get_active_signal(self, symbol: str) -> Optional[Dict]:
        """Get active signal for symbol"""
        return self.active_signals.get(symbol)
    
    def get_all_active_signals(self) -> Dict[str, Dict]:
        """Get all active signals"""
        return self.active_signals
    
    def get_active_symbols(self) -> List[str]:
        """Get list of symbols with active signals"""
        return list(self.active_signals.keys())
    
    def get_active_signals_summary(self) -> str:
        """Get a formatted summary of all active signals with current status"""
        if not self.active_signals:
            return "No active signals"
        
        summary = []
        summary.append(f"\n{'='*70}")
        summary.append(f"ACTIVE SIGNALS ({len(self.active_signals)})")
        summary.append(f"{'='*70}\n")
        
        for symbol, signal in self.active_signals.items():
            direction_emoji = "🟢" if signal['direction'] == 'long' else "🔴"
            regime = signal.get('regime', 'unknown')
            regime_emoji = {"trending": "📈", "high_volatility": "⚡", "choppy": "〰️", "low_volatility": "💤"}.get(regime, "❓")
            
            summary.append(f"{direction_emoji} {symbol} - {signal['direction'].upper()} | {regime_emoji} {regime}")
            summary.append(f"   Entry: ${signal['entry_price']:.4f}")
            summary.append(f"   Current: ${signal.get('current_price', 0):.4f}")
            summary.append(f"   Stop Loss: ${signal['stop_loss']:.4f}")
            
            # Show TP status
            tp_status = []
            for tp in ['tp1', 'tp2', 'tp3']:
                if signal.get(f'{tp}_hit'):
                    tp_status.append(f"✅{tp.upper()}")
                else:
                    price = signal['take_profits'][tp]['price']
                    tp_status.append(f"⏳{tp.upper()}(${price:.4f})")
            summary.append(f"   TPs: {' | '.join(tp_status)}")
            
            # Show position status
            summary.append(f"   Position: {signal['remaining_percent']:.0f}% open")
            summary.append(f"   Realized P&L: ${signal['realized_pnl']:+.2f}")
            
            # Calculate unrealized P&L
            current_price = signal.get('current_price', signal['entry_price'])
            remaining_contracts = signal['position_size']['contracts'] * (signal['remaining_percent'] / 100)
            if signal['direction'] == 'long':
                unrealized = (current_price - signal['entry_price']) * remaining_contracts
            else:
                unrealized = (signal['entry_price'] - current_price) * remaining_contracts
            summary.append(f"   Unrealized P&L: ${unrealized:+.2f}")
            summary.append(f"   Total P&L: ${signal['realized_pnl'] + unrealized:+.2f}")
            
            # Time info - handle both 'entry_time' and 'created_at'
            time_key = 'entry_time' if 'entry_time' in signal else 'created_at'
            if time_key in signal:
                entry_time = datetime.fromisoformat(signal[time_key])
                duration = datetime.now() - entry_time
                hours = duration.total_seconds() / 3600
                summary.append(f"   Duration: {hours:.1f} hours")
            summary.append("")
        
        summary.append(f"{'='*70}\n")
        return "\n".join(summary)
    
    def manually_close_signal(self, symbol: str, reason: str = "manual") -> bool:
        """Manually close a signal"""
        if symbol in self.active_signals:
            self._close_signal(symbol, reason)
            return True
        return False
    
    def check_adaptive_stop_trigger(
        self,
        symbol: str,
        current_price: float,
        current_atr: float,
        current_regime: str
    ) -> Tuple[bool, Optional[float], str]:
        """
        Check if adaptive stop protection should be triggered
        
        Triggers when position is profitable AND market conditions worsen:
        - Volatility spike detected (ATR increased significantly)
        - Regime changed to choppy/ranging
        
        Returns:
            (should_trigger, new_stop_level, reason)
        """
        if not Config.ADAPTIVE_STOP_ENABLED:
            return (False, None, "")
        
        if symbol not in self.active_signals:
            return (False, None, "")
        
        signal = self.active_signals[symbol]
        
        # Only trigger once
        if signal.get('adaptive_stop_triggered', False):
            return (False, None, "already triggered")
        
        # Calculate profit in R multiples
        entry = signal['entry_price']
        original_stop = signal['original_stop_loss']
        direction = signal['direction']
        
        if direction == 'LONG':
            stop_distance = entry - original_stop
            profit_distance = current_price - entry
        else:  # SHORT
            stop_distance = original_stop - entry
            profit_distance = entry - current_price
        
        # Avoid division by zero
        if stop_distance <= 0:
            return (False, None, "invalid stop distance")
        
        profit_r = profit_distance / stop_distance
        
        # Must be profitable enough
        if profit_r < Config.ADAPTIVE_STOP_MIN_PROFIT_R:
            return (False, None, f"profit {profit_r:.2f}R below threshold")
        
        # Check for trigger conditions
        entry_atr = signal.get('entry_atr', 0.0)
        entry_regime = signal.get('entry_regime', 'unknown')
        
        trigger_reason = ""
        
        # Condition 1: Volatility spike
        if entry_atr > 0 and current_atr > entry_atr * Config.ADAPTIVE_STOP_VOLATILITY_SPIKE:
            spike_pct = ((current_atr / entry_atr) - 1) * 100
            trigger_reason = f"volatility spike +{spike_pct:.1f}%"
        
        # Condition 2: Regime deterioration
        if entry_regime in ['trending', 'strong_trend'] and current_regime in ['choppy', 'ranging']:
            if trigger_reason:
                trigger_reason += f" + regime {entry_regime}→{current_regime}"
            else:
                trigger_reason = f"regime change {entry_regime}→{current_regime}"
        
        if not trigger_reason:
            return (False, None, "no trigger conditions met")
        
        # Calculate new stop: breakeven + small buffer
        buffer = entry * Config.ADAPTIVE_STOP_BREAKEVEN_BUFFER
        
        if direction == 'LONG':
            new_stop = entry + buffer
            # Only tighten, never widen
            if new_stop <= signal['stop_loss']:
                return (False, None, "would widen stop")
        else:  # SHORT
            new_stop = entry - buffer
            # Only tighten, never widen
            if new_stop >= signal['stop_loss']:
                return (False, None, "would widen stop")
        
        return (True, new_stop, trigger_reason)
    
    def _save_active_signals(self) -> None:
        """Save active signals to file"""
        try:
            with open(Config.ACTIVE_SIGNALS_FILE, 'w') as f:
                json.dump(self.active_signals, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving active signals: {e}")
    
    def _save_history(self) -> None:
        """Save history to file"""
        try:
            with open(Config.HISTORY_SIGNALS_FILE, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving signal history: {e}")
    
    def _load_active_signals(self) -> None:
        """Load active signals from file"""
        try:
            if Path(Config.ACTIVE_SIGNALS_FILE).exists():
                with open(Config.ACTIVE_SIGNALS_FILE, 'r') as f:
                    self.active_signals = json.load(f)
                logger.info(f"✓ Loaded {len(self.active_signals)} active signals")
        except Exception as e:
            logger.warning(f"Could not load active signals: {e}")
            self.active_signals = {}
    
    def _load_history(self) -> None:
        """Load signal history from file"""
        try:
            if Path(Config.HISTORY_SIGNALS_FILE).exists():
                with open(Config.HISTORY_SIGNALS_FILE, 'r') as f:
                    self.history = json.load(f)
                logger.info(f"✓ Loaded {len(self.history)} historical signals")
        except Exception as e:
            logger.warning(f"Could not load signal history: {e}")
            self.history = []