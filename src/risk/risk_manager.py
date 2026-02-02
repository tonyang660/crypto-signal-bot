import json
from datetime import datetime, timedelta
from typing import Tuple, Optional
from pathlib import Path
from loguru import logger
from src.core.config import Config

class RiskManager:
    """Manage trading risk limits and circuit breakers"""
    
    def __init__(self):
        self.equity = Config.INITIAL_CAPITAL
        self.daily_loss = 0.0
        self.weekly_loss = 0.0
        self.daily_pnl = 0.0  # Track all daily PnL (wins and losses)
        self.consecutive_losses = 0
        self.trading_enabled = True
        self.cooldown_until: Optional[datetime] = None
        self.last_reset_date = datetime.now().date()
        self.last_weekly_reset = datetime.now().date()
        
        # Load persisted state
        self._load_state()
        
        # Create initial file if it doesn't exist
        if not Path(Config.PERFORMANCE_FILE).exists():
            self._save_state()
    
    def can_trade(self) -> Tuple[bool, str]:
        """
        Check if trading is allowed
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Auto-reset daily if new day
        self._check_daily_reset()
        
        # Auto-reset weekly if new week
        self._check_weekly_reset()
        
        # Check cooldown
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            remaining = (self.cooldown_until - datetime.now()).total_seconds() / 3600
            return False, f"⏸️ Cooldown active for {remaining:.1f} more hours"
        
        # Check daily loss limit based on NET daily PnL (not just losses)
        # Only stop trading if NET daily PnL is negative and exceeds limit
        if self.daily_pnl < 0:
            daily_loss_pct = abs(self.daily_pnl / self.equity)
            if daily_loss_pct >= Config.MAX_DAILY_LOSS:
                return False, f"🛑 Daily loss limit hit: ${self.daily_pnl:.2f} ({daily_loss_pct*100:.1f}%)"
        
        # Check weekly loss limit based on NET weekly PnL
        if self.weekly_loss < 0:
            weekly_loss_pct = abs(self.weekly_loss / self.equity)
            if weekly_loss_pct >= Config.MAX_WEEKLY_LOSS:
                return False, f"🛑 Weekly loss limit hit: ${self.weekly_loss:.2f} ({weekly_loss_pct*100:.1f}%)"
        
        # Check consecutive losses
        if self.consecutive_losses >= Config.MAX_CONSECUTIVE_LOSSES:
            return False, f"🛑 {self.consecutive_losses} consecutive losses - cooldown required"
        
        # Check weekend (optional - crypto trades 24/7 but can be conservative)
        if self._is_weekend():
            # Could add weekend trading restrictions here
            # For now, allow weekend trading
            pass
        
        return True, "✅ Trading allowed"
    
    def record_trade(self, pnl: float) -> None:
        """Record trade result and update state"""
        try:
            # Update equity
            self.equity += pnl
            
            # Track daily PnL (all trades)
            self.daily_pnl += pnl
            
            if pnl < 0:
                # Record loss
                self.daily_loss += pnl
                self.weekly_loss += pnl
                self.consecutive_losses += 1
                
                logger.warning(f"📉 Loss recorded: ${pnl:.2f} | Consecutive losses: {self.consecutive_losses}")
                
                # Activate cooldown after max consecutive losses
                if self.consecutive_losses >= Config.MAX_CONSECUTIVE_LOSSES:
                    self.cooldown_until = datetime.now() + timedelta(hours=4)
                    logger.warning(f"⏸️ Cooldown activated until {self.cooldown_until.strftime('%Y-%m-%d %H:%M')}")
            
            else:
                # Record win
                self.consecutive_losses = 0  # Reset on win
                logger.info(f"📈 Profit recorded: ${pnl:.2f}")
            
            # Save state
            self._save_state()
            
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
    
    def get_account_state(self) -> str:
        """
        Determine current account state for signal scoring
        
        Returns: 'normal', 'drawdown', or 'hot_streak'
        """
        # Drawdown if NET daily PnL is negative and > 1% of equity
        if self.daily_pnl < 0 and abs(self.daily_pnl / self.equity) > 0.01:
            return 'drawdown'
        
        # Hot streak if NET daily PnL is positive and > 2% of equity
        if self.daily_pnl > 0 and (self.daily_pnl / self.equity) > 0.02:
            return 'hot_streak'
        
        return 'normal'
    
    def get_risk_stats(self) -> dict:
        """Get current risk statistics"""
        return {
            'daily_pnl': self.daily_pnl,  # Include daily PnL (all trades)
            'equity': self.equity,
            'daily_loss': self.daily_loss,  # Keep for tracking purposes
            'daily_pnl_pct': (self.daily_pnl / self.equity) * 100 if self.equity > 0 else 0,  # Net daily P&L percentage
            'weekly_loss': self.weekly_loss,
            'weekly_loss_pct': abs(self.weekly_loss / self.equity) * 100,
            'consecutive_losses': self.consecutive_losses,
            'trading_enabled': self.trading_enabled,
            'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None
        }
    
    def _check_daily_reset(self, skip_reset: bool = False) -> bool:
        """Check if new day and optionally reset daily counters
        
        Args:
            skip_reset: If True, only check without resetting (for pre-reset report generation)
        
        Returns:
            True if it's a new day
        """
        today = datetime.now().date()
        if today > self.last_reset_date:
            if not skip_reset:
                logger.info(f"📅 New day - resetting daily counters")
                self.daily_pnl = 0.0  # Reset daily PnL
                self.daily_loss = 0.0
                self.last_reset_date = today
                
                # Clear cooldown if weekly limit not hit
                if abs(self.weekly_loss / self.equity) < Config.MAX_WEEKLY_LOSS:
                    self.trading_enabled = True
                    self.cooldown_until = None
                
                self._save_state()
            return True
        return False
    
    def _check_weekly_reset(self) -> None:
        """Reset weekly counters if new week (Monday)"""
        today = datetime.now().date()
        
        # Check if it's Monday and last reset was not this week
        if today.weekday() == 0 and today > self.last_weekly_reset:
            logger.info(f"📅 New week - resetting weekly counters")
            self.weekly_loss = 0.0
            self.last_weekly_reset = today
            self.trading_enabled = True
            self.cooldown_until = None
            self._save_state()
    
    def _is_weekend(self) -> bool:
        """Check if current time is weekend"""
        return datetime.now().weekday() >= 5  # Saturday=5, Sunday=6
    
    def _save_state(self) -> None:
        """Persist state to file"""
        try:
            state = {
                'daily_pnl': self.daily_pnl,  # Save daily PnL
                'equity': self.equity,
                'daily_loss': self.daily_loss,
                'weekly_loss': self.weekly_loss,
                'consecutive_losses': self.consecutive_losses,
                'trading_enabled': self.trading_enabled,
                'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None,
                'last_reset_date': self.last_reset_date.isoformat(),
                'last_weekly_reset': self.last_weekly_reset.isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            
            Path(Config.PERFORMANCE_FILE).parent.mkdir(parents=True, exist_ok=True)
            
            with open(Config.PERFORMANCE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving risk manager state: {e}")
    
    def _load_state(self) -> None:
        """Load persisted state from file"""
        try:
            if Path(Config.PERFORMANCE_FILE).exists():
                with open(Config.PERFORMANCE_FILE, 'r') as f:
                    state = json.load(f)
                self.daily_pnl = state.get('daily_pnl', 0.0)  # Load daily PnL
                self.equity = state.get('equity', Config.INITIAL_CAPITAL)
                self.daily_loss = state.get('daily_loss', 0.0)
                self.weekly_loss = state.get('weekly_loss', 0.0)
                self.consecutive_losses = state.get('consecutive_losses', 0)
                self.trading_enabled = state.get('trading_enabled', True)
                
                cooldown_str = state.get('cooldown_until')
                if cooldown_str:
                    self.cooldown_until = datetime.fromisoformat(cooldown_str)
                
                reset_date_str = state.get('last_reset_date')
                if reset_date_str:
                    self.last_reset_date = datetime.fromisoformat(reset_date_str).date()
                
                weekly_reset_str = state.get('last_weekly_reset')
                if weekly_reset_str:
                    self.last_weekly_reset = datetime.fromisoformat(weekly_reset_str).date()
                
                logger.info(f"✓ Risk manager state loaded - Equity: ${self.equity:.2f}")
            
        except Exception as e:
            logger.warning(f"Could not load risk manager state: {e}")