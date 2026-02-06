"""
Paper Trading Virtual Account

Tracks virtual trading balance, equity, positions, and P&L
for self-hosted paper trading simulation.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class PaperAccount:
    """
    Virtual trading account for paper trading simulation.
    Tracks balance, equity, positions, fees, and performance metrics.
    """
    
    def __init__(self, initial_capital: float, state_file: str = None):
        """
        Initialize paper trading account
        
        Args:
            initial_capital: Starting balance in USD
            state_file: Path to JSON file for persisting account state
        """
        self.state_file = state_file or 'data/paper_account.json'
        
        # Load existing state or initialize new
        if os.path.exists(self.state_file):
            self.load_state()
            logger.info(f"📊 Loaded paper account: ${self.balance:.2f} balance, "
                       f"${self.get_equity():.2f} equity")
        else:
            self.balance = initial_capital
            self.initial_capital = initial_capital
            self.total_realized_pnl = 0.0
            self.total_fees_paid = 0.0
            self.total_funding_costs = 0.0
            self.positions_count = 0
            self.trades_count = 0
            
            # Active positions (references, not stored in account state)
            self.open_positions: List[Dict] = []
            
            # Equity curve tracking
            self.equity_curve: List[Dict] = [{
                'timestamp': datetime.utcnow().isoformat(),
                'equity': initial_capital,
                'balance': initial_capital,
                'unrealized_pnl': 0.0,
                'open_positions': 0
            }]
            
            logger.info(f"📊 New paper account initialized: ${initial_capital:.2f}")
            self.save_state()
    
    def get_balance(self) -> float:
        """Get current cash balance (excluding unrealized PnL)"""
        return self.balance
    
    def get_equity(self) -> float:
        """
        Get total equity (balance + unrealized PnL from open positions)
        
        Returns:
            equity: Total account value
        """
        unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in self.open_positions)
        equity = self.balance + unrealized_pnl
        return equity
    
    def get_unrealized_pnl(self) -> float:
        """Get total unrealized PnL from all open positions"""
        return sum(pos.get('unrealized_pnl', 0) for pos in self.open_positions)
    
    def get_available_margin(self) -> float:
        """
        Get available margin for new positions
        
        Returns:
            available: Equity minus margin used by open positions
        """
        equity = self.get_equity()
        used_margin = sum(pos.get('margin_used', 0) for pos in self.open_positions)
        available = equity - used_margin
        return available
    
    def deduct_fees(self, fee_amount: float):
        """
        Deduct trading fees from balance
        
        Args:
            fee_amount: Fee amount in USD
        """
        self.balance -= fee_amount
        self.total_fees_paid += fee_amount
        logger.debug(f"💸 Fee deducted: ${fee_amount:.2f} | Balance: ${self.balance:.2f}")
    
    def deduct_funding(self, funding_cost: float):
        """
        Deduct perpetual futures funding rate from balance
        
        Args:
            funding_cost: Funding cost in USD (negative = pay, positive = receive)
        """
        self.balance -= funding_cost
        self.total_funding_costs += funding_cost
        
        if funding_cost > 0:
            logger.debug(f"💸 Funding paid: ${funding_cost:.2f}")
        else:
            logger.debug(f"💰 Funding received: ${-funding_cost:.2f}")
    
    def add_realized_pnl(self, pnl_amount: float):
        """
        Add realized P&L to balance (from closed positions)
        
        Args:
            pnl_amount: P&L amount (positive = profit, negative = loss)
        """
        self.balance += pnl_amount
        self.total_realized_pnl += pnl_amount
        self.trades_count += 1
        
        if pnl_amount > 0:
            logger.info(f"✅ Realized profit: +${pnl_amount:.2f} | Balance: ${self.balance:.2f}")
        else:
            logger.info(f"❌ Realized loss: ${pnl_amount:.2f} | Balance: ${self.balance:.2f}")
    
    def add_position(self, position: Dict):
        """
        Track a new open position
        
        Args:
            position: Position dict
        """
        self.open_positions.append(position)
        self.positions_count += 1
        logger.debug(f"📈 Position tracked: {position['symbol']} {position['side']} "
                    f"(Total open: {len(self.open_positions)})")
    
    def close_position(self, position: Dict):
        """
        Remove a closed position from tracking
        
        Args:
            position: Position dict to remove
        """
        if position in self.open_positions:
            self.open_positions.remove(position)
            logger.debug(f"📉 Position closed: {position['symbol']} "
                        f"(Remaining open: {len(self.open_positions)})")
    
    def get_open_positions(self) -> List[Dict]:
        """Get list of all open positions"""
        return self.open_positions
    
    def update_equity_curve(self):
        """
        Add current equity snapshot to equity curve
        Should be called periodically (e.g., on each scan)
        """
        snapshot = {
            'timestamp': datetime.utcnow().isoformat(),
            'equity': self.get_equity(),
            'balance': self.balance,
            'unrealized_pnl': self.get_unrealized_pnl(),
            'open_positions': len(self.open_positions)
        }
        
        self.equity_curve.append(snapshot)
        
        # Keep last 10,000 snapshots (prevent unbounded growth)
        if len(self.equity_curve) > 10000:
            self.equity_curve = self.equity_curve[-10000:]
    
    def get_performance_summary(self) -> Dict:
        """
        Get account performance summary
        
        Returns:
            summary: Dict with key metrics
        """
        equity = self.get_equity()
        total_return = ((equity - self.initial_capital) / self.initial_capital) * 100
        
        # Calculate win rate (simplified - need trades data for accurate calc)
        wins = sum(1 for trade in self.equity_curve if trade.get('unrealized_pnl', 0) > 0)
        total_trades = self.trades_count if self.trades_count > 0 else 1
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        summary = {
            'initial_capital': self.initial_capital,
            'current_balance': self.balance,
            'current_equity': equity,
            'total_return': total_return,
            'total_return_usd': equity - self.initial_capital,
            'total_realized_pnl': self.total_realized_pnl,
            'unrealized_pnl': self.get_unrealized_pnl(),
            'total_fees_paid': self.total_fees_paid,
            'total_funding_costs': self.total_funding_costs,
            'net_pnl': self.total_realized_pnl + self.get_unrealized_pnl() - self.total_fees_paid - self.total_funding_costs,
            'open_positions': len(self.open_positions),
            'total_positions_opened': self.positions_count,
            'total_trades_closed': self.trades_count,
            'win_rate': win_rate,
            'available_margin': self.get_available_margin()
        }
        
        return summary
    
    def save_state(self):
        """Save account state to JSON file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            
            state = {
                'balance': self.balance,
                'initial_capital': self.initial_capital,
                'total_realized_pnl': self.total_realized_pnl,
                'total_fees_paid': self.total_fees_paid,
                'total_funding_costs': self.total_funding_costs,
                'positions_count': self.positions_count,
                'trades_count': self.trades_count,
                'equity_curve': self.equity_curve[-1000:],  # Save last 1000 points
                'last_updated': datetime.utcnow().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.debug(f"💾 Account state saved: {self.state_file}")
            
        except Exception as e:
            logger.error(f"Failed to save paper account state: {e}")
    
    def load_state(self):
        """Load account state from JSON file"""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.balance = state.get('balance', 0)
            self.initial_capital = state.get('initial_capital', 0)
            self.total_realized_pnl = state.get('total_realized_pnl', 0)
            self.total_fees_paid = state.get('total_fees_paid', 0)
            self.total_funding_costs = state.get('total_funding_costs', 0)
            self.positions_count = state.get('positions_count', 0)
            self.trades_count = state.get('trades_count', 0)
            self.equity_curve = state.get('equity_curve', [])
            self.open_positions = []  # Positions loaded separately by tracker
            
            logger.debug(f"📂 Account state loaded from {self.state_file}")
            
        except Exception as e:
            logger.error(f"Failed to load paper account state: {e}")
            raise
    
    def reset(self):
        """Reset account to initial state (for testing)"""
        self.balance = self.initial_capital
        self.total_realized_pnl = 0.0
        self.total_fees_paid = 0.0
        self.total_funding_costs = 0.0
        self.positions_count = 0
        self.trades_count = 0
        self.open_positions = []
        self.equity_curve = [{
            'timestamp': datetime.utcnow().isoformat(),
            'equity': self.initial_capital,
            'balance': self.initial_capital,
            'unrealized_pnl': 0.0,
            'open_positions': 0
        }]
        
        logger.warning(f"🔄 Paper account reset to ${self.initial_capital:.2f}")
        self.save_state()
