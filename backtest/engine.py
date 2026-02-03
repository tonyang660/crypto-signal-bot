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
    realized_pnl: float = 0.0
    
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
        
        # Risk management state
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None
        self.last_reset_date: Optional[datetime] = None
        
        # Statistics
        self.total_fees_paid = 0.0
        self.total_slippage_cost = 0.0
        
        logger.info(f"Backtest initialized with ${self.equity:.2f}")
    
    def run(self) -> Dict:
        """
        Run the backtest
        
        Returns:
            Results dictionary with metrics
        """
        logger.info("="*70)
        logger.info("STARTING BACKTEST")
        logger.info("="*70)
        
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
        
        logger.info(f"Backtest period: {start_date} to {end_date}")
        logger.info(f"Total candles: {len(sorted_dates)}")
        
        # Process each candle
        for i, current_time in enumerate(sorted_dates):
            if i % 1000 == 0:
                logger.info(f"Processing: {current_time} ({i}/{len(sorted_dates)})")
            
            # Daily reset
            self._check_daily_reset(current_time)
            
            # Update active positions (check TP/SL)
            self._update_positions(current_time)
            
            # Check if trading allowed
            can_trade, reason = self._can_trade(current_time)
            
            if not can_trade:
                logger.debug(f"{current_time}: Trading disabled - {reason}")
                continue
            
            # Scan for new signals
            self._scan_for_signals(current_time)
            
            # Record equity
            self.equity_curve.append((current_time, self.equity))
        
        # Close any remaining positions at end
        self._close_all_positions(end_date, "backtest_end")
        
        # Calculate results
        results = self._calculate_results()
        
        logger.info("="*70)
        logger.info("BACKTEST COMPLETE")
        logger.info("="*70)
        
        return results
    
    def _update_positions(self, current_time: datetime):
        """Update all active positions - check for TP/SL hits"""
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
                logger.debug(f"{current_time} {symbol}: Both TP and SL hit - assuming SL (conservative)")
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
        """Handle take profit hit"""
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
        portion_contracts = position.contracts * (close_percent / 100)
        
        if position.direction == 'long':
            pnl = (exit_price - position.entry_price) * portion_contracts
        else:
            pnl = (position.entry_price - exit_price) * portion_contracts
        
        # Subtract fees
        exit_value = exit_price * portion_contracts
        fee = exit_value * (BacktestConfig.TAKER_FEE / 100)
        pnl -= fee
        self.total_fees_paid += fee
        
        # Update position
        position.realized_pnl += pnl
        position.remaining_percent -= close_percent
        setattr(position, f'{tp_level}_hit', True)
        
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
        
        logger.debug(f"{current_time} {position.symbol}: {tp_level.upper()} hit | P&L: ${pnl:.2f}")
        
        # If fully closed
        if position.remaining_percent <= 0:
            self._record_trade(position, current_time, exit_price, 'completed')
    
    def _close_position(self, position: Position, exit_time: datetime, exit_price: float, reason: str, sl_hit: bool = False):
        """Close position and record trade"""
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
        
        # Calculate PnL for remaining position
        remaining_contracts = position.contracts * (position.remaining_percent / 100)
        
        if position.direction == 'long':
            pnl = (exit_price - position.entry_price) * remaining_contracts
        else:
            pnl = (position.entry_price - exit_price) * remaining_contracts
        
        # Subtract fees
        exit_value = exit_price * remaining_contracts
        fee = exit_value * (BacktestConfig.TAKER_FEE / 100)
        pnl -= fee
        self.total_fees_paid += fee
        
        # Add to realized PnL
        position.realized_pnl += pnl
        
        # Record trade
        self._record_trade(position, exit_time, exit_price, reason)
    
    def _record_trade(self, position: Position, exit_time: datetime, exit_price: float, reason: str):
        """Record completed trade"""
        duration = (exit_time - position.entry_time).total_seconds() / 3600
        pnl_percent = (position.realized_pnl / (position.entry_price * position.contracts)) * 100
        
        trade = Trade(
            symbol=position.symbol,
            direction=position.direction,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            pnl=position.realized_pnl,
            pnl_percent=pnl_percent,
            exit_reason=reason,
            regime=position.regime,
            score=position.score,
            duration_hours=duration
        )
        
        self.closed_trades.append(trade)
        
        # Update equity
        self.equity += position.realized_pnl
        self.daily_pnl += position.realized_pnl
        self.weekly_pnl += position.realized_pnl
        
        # Track consecutive losses
        if position.realized_pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= BacktestConfig.MAX_CONSECUTIVE_LOSSES:
                self.cooldown_until = exit_time + timedelta(hours=BacktestConfig.COOLDOWN_HOURS)
                logger.info(f"{exit_time}: Cooldown activated until {self.cooldown_until}")
        else:
            self.consecutive_losses = 0
        
        logger.info(f"{exit_time} {position.symbol}: Trade closed | {reason} | P&L: ${position.realized_pnl:+.2f} | Equity: ${self.equity:.2f}")
    
    def _scan_for_signals(self, current_time: datetime):
        """Scan for new trading signals (uses live bot logic)"""
        for symbol in BacktestConfig.SYMBOLS:
            # Skip if position already exists
            if symbol in self.active_positions:
                continue
            
            # Check position limits
            if len(self.active_positions) >= BacktestConfig.MAX_TOTAL_ACTIVE_SIGNALS:
                continue
            
            try:
                # Get multi-timeframe data UP TO current_time (no future data!)
                data = self._get_mtf_data(symbol, current_time)
                
                if not data:
                    continue
                
                # Add indicators
                for tf in data:
                    data[tf] = Indicators.add_all_indicators(data[tf])
                
                # Check regime
                regime = RegimeDetector.detect_regime(data['primary'])
                
                if not RegimeDetector.should_trade_regime(regime):
                    continue
                
                # Check long entry
                long_check = EntryLogic.check_long_entry(data)
                score, _ = SignalScorer.calculate_score_with_breakdown(data, 'long', symbol)
                
                threshold = BacktestConfig.SIGNAL_THRESHOLD_DRAWDOWN if self.equity < self.initial_equity * 0.98 else BacktestConfig.SIGNAL_THRESHOLD_NORMAL
                
                if (long_check['valid'] or score >= 80) and score >= threshold:
                    self._create_position(symbol, 'long', data, current_time, long_check['reason'], score, regime)
                    continue
                
                # Check short entry
                short_check = EntryLogic.check_short_entry(data)
                score, _ = SignalScorer.calculate_score_with_breakdown(data, 'short', symbol)
                
                if (short_check['valid'] or score >= 80) and score >= threshold:
                    self._create_position(symbol, 'short', data, current_time, short_check['reason'], score, regime)
                
            except Exception as e:
                logger.error(f"Error scanning {symbol} at {current_time}: {e}")
    
    def _create_position(self, symbol: str, direction: str, data: Dict, entry_time: datetime, reason: str, score: int, regime: str):
        """Create new position (on candle close)"""
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
        
        # Entry fee
        entry_value = entry_price * contracts
        entry_fee = entry_value * (BacktestConfig.TAKER_FEE / 100)
        self.total_fees_paid += entry_fee
        
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
            realized_pnl=-entry_fee  # Start with negative (entry fee)
        )
        
        self.active_positions[symbol] = position
        
        logger.info(f"{entry_time} {symbol}: {direction.upper()} entry | Price: ${entry_price:.2f} | Score: {score} | Regime: {regime}")
    
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
            logger.error(f"Error getting MTF data for {symbol}: {e}")
            return None
    
    def _can_trade(self, current_time: datetime) -> Tuple[bool, str]:
        """Check if trading allowed (same logic as live bot)"""
        # Check cooldown
        if self.cooldown_until and current_time < self.cooldown_until:
            remaining = (self.cooldown_until - current_time).total_seconds() / 3600
            return False, f"Cooldown active for {remaining:.1f} more hours"
        elif self.cooldown_until and current_time >= self.cooldown_until:
            self.cooldown_until = None
            self.consecutive_losses = 0
        
        # Check weekly loss
        if BacktestConfig.MAX_WEEKLY_LOSS and self.weekly_pnl < 0:
            weekly_loss_pct = abs(self.weekly_pnl / self.equity)
            if weekly_loss_pct >= BacktestConfig.MAX_WEEKLY_LOSS:
                return False, f"Weekly loss limit hit: ${self.weekly_pnl:.2f}"
        
        # Check consecutive losses
        if self.consecutive_losses >= BacktestConfig.MAX_CONSECUTIVE_LOSSES:
            return False, f"{self.consecutive_losses} consecutive losses"
        
        return True, "OK"
    
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
            'avg_duration_hours': round(trades_df['duration_hours'].mean(), 2),
            'trades_by_regime': trades_df.groupby('regime')['pnl'].agg(['count', 'sum', 'mean']).to_dict(),
            'trades_by_symbol': trades_df.groupby('symbol')['pnl'].agg(['count', 'sum', 'mean']).to_dict(),
            'trades_by_exit_reason': trades_df.groupby('exit_reason')['pnl'].agg(['count', 'sum']).to_dict()
        }
        
        return results
