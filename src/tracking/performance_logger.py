import json
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path
from loguru import logger
from src.core.config import Config

class PerformanceLogger:
    """Log and analyze trading performance metrics"""
    
    def __init__(self):
        self.trades: List[Dict] = []
        self._load_trades()
    
    def log_trade(
        self,
        signal_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        exit_reason: str
    ) -> None:
        """Log completed trade"""
        try:
            trade = {
                'signal_id': signal_id,
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_percent': (pnl / (entry_price * 0.01)) if entry_price > 0 else 0,
                'exit_reason': exit_reason,
                'timestamp': datetime.now().isoformat()
            }
            
            self.trades.append(trade)
            self._save_trades()
            
            logger.info(f"📊 Trade logged: {symbol} {direction} | PnL: ${pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error logging trade: {e}")
    
    def get_statistics(self, days: int = 30) -> Dict:
        """Calculate performance statistics"""
        try:
            # Filter trades by date
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_trades = [
                t for t in self.trades 
                if datetime.fromisoformat(t['timestamp']) > cutoff_date
            ]
            
            if not recent_trades:
                return {
                    'total_trades': 0,
                    'win_rate': 0,
                    'avg_win': 0,
                    'avg_loss': 0,
                    'total_pnl': 0,
                    'profit_factor': 0,
                    'expectancy': 0
                }
            
            # Calculate metrics
            total_trades = len(recent_trades)
            wins = [t for t in recent_trades if t['pnl'] > 0]
            losses = [t for t in recent_trades if t['pnl'] < 0]
            
            win_count = len(wins)
            loss_count = len(losses)
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            
            avg_win = sum(t['pnl'] for t in wins) / win_count if win_count > 0 else 0
            avg_loss = sum(t['pnl'] for t in losses) / loss_count if loss_count > 0 else 0
            
            total_pnl = sum(t['pnl'] for t in recent_trades)
            
            gross_profit = sum(t['pnl'] for t in wins)
            gross_loss = abs(sum(t['pnl'] for t in losses))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            expectancy = total_pnl / total_trades if total_trades > 0 else 0
            
            return {
                'period_days': days,
                'total_trades': total_trades,
                'wins': win_count,
                'losses': loss_count,
                'win_rate': round(win_rate, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'total_pnl': round(total_pnl, 2),
                'gross_profit': round(gross_profit, 2),
                'gross_loss': round(gross_loss, 2),
                'profit_factor': round(profit_factor, 2),
                'expectancy': round(expectancy, 2),
                'best_trade': max(t['pnl'] for t in recent_trades) if recent_trades else 0,
                'worst_trade': min(t['pnl'] for t in recent_trades) if recent_trades else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {}
    
    def get_today_statistics(self) -> Dict:
        """Get statistics for today only (since midnight)"""
        try:
            # Get today's date at midnight
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Filter trades from today only
            today_trades = [
                t for t in self.trades 
                if datetime.fromisoformat(t['timestamp']) >= today_start
            ]
            
            if not today_trades:
                return {
                    'total_trades': 0,
                    'win_rate': 0,
                    'avg_win': 0,
                    'avg_loss': 0,
                    'total_pnl': 0,
                    'profit_factor': 0
                }
            
            # Calculate metrics
            total_trades = len(today_trades)
            wins = [t for t in today_trades if t['pnl'] > 0]
            losses = [t for t in today_trades if t['pnl'] < 0]
            
            win_count = len(wins)
            loss_count = len(losses)
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            
            avg_win = sum(t['pnl'] for t in wins) / win_count if win_count > 0 else 0
            avg_loss = sum(t['pnl'] for t in losses) / loss_count if loss_count > 0 else 0
            
            total_pnl = sum(t['pnl'] for t in today_trades)
            
            gross_profit = sum(t['pnl'] for t in wins)
            gross_loss = abs(sum(t['pnl'] for t in losses))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            return {
                'total_trades': total_trades,
                'wins': win_count,
                'losses': loss_count,
                'win_rate': round(win_rate, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'total_pnl': round(total_pnl, 2),
                'gross_profit': round(gross_profit, 2),
                'gross_loss': round(gross_loss, 2),
                'profit_factor': round(profit_factor, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating today's statistics: {e}")
            return {'total_trades': 0, 'win_rate': 0}
    
    def get_daily_pnl(self, days: int = 7) -> List[Dict]:
        """Get daily PnL for last N days"""
        try:
            daily_pnl = {}
            
            for trade in self.trades:
                date = datetime.fromisoformat(trade['timestamp']).date()
                date_str = date.isoformat()
                
                if date_str not in daily_pnl:
                    daily_pnl[date_str] = 0
                
                daily_pnl[date_str] += trade['pnl']
            
            # Get last N days
            result = []
            for i in range(days):
                date = (datetime.now().date() - timedelta(days=i)).isoformat()
                result.append({
                    'date': date,
                    'pnl': round(daily_pnl.get(date, 0), 2)
                })
            
            return list(reversed(result))
            
        except Exception as e:
            logger.error(f"Error getting daily PnL: {e}")
            return []
    
    def _save_trades(self) -> None:
        """Save trades to file"""
        try:
            # Use separate file for trade history
            trades_file = Path(Config.DATA_DIR) / 'trade_history.json'
            
            with open(trades_file, 'w') as f:
                json.dump(self.trades, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving trades: {e}")
    
    def save_daily_report(self) -> Dict:
        """Save daily report to permanent log file and return the stats"""
        try:
            today_stats = self.get_today_statistics()
            
            # Create daily log entry
            daily_log = {
                'date': datetime.now().date().isoformat(),
                'timestamp': datetime.now().isoformat(),
                'total_trades': today_stats.get('total_trades', 0),
                'wins': today_stats.get('wins', 0),
                'losses': today_stats.get('losses', 0),
                'win_rate': today_stats.get('win_rate', 0),
                'avg_win': today_stats.get('avg_win', 0),
                'avg_loss': today_stats.get('avg_loss', 0),
                'total_pnl': today_stats.get('total_pnl', 0),
                'gross_profit': today_stats.get('gross_profit', 0),
                'gross_loss': today_stats.get('gross_loss', 0),
                'profit_factor': today_stats.get('profit_factor', 0)
            }
            
            # Load existing daily logs
            daily_logs_file = Path(Config.DATA_DIR) / 'daily_logs.json'
            daily_logs = []
            
            if daily_logs_file.exists():
                with open(daily_logs_file, 'r') as f:
                    daily_logs = json.load(f)
            
            # Add today's log
            daily_logs.append(daily_log)
            
            # Save updated logs
            with open(daily_logs_file, 'w') as f:
                json.dump(daily_logs, f, indent=2)
            
            logger.info(f"📊 Daily report saved: {today_stats.get('total_trades', 0)} trades, ${today_stats.get('total_pnl', 0):+.2f}")
            
            return today_stats
            
        except Exception as e:
            logger.error(f"Error saving daily report: {e}")
            return {}
    
    def _load_trades(self) -> None:
        """Load trades from file"""
        try:
            trades_file = Path(Config.DATA_DIR) / 'trade_history.json'
            
            if trades_file.exists():
                with open(trades_file, 'r') as f:
                    self.trades = json.load(f)
                logger.info(f"✓ Loaded {len(self.trades)} historical trades")
        except Exception as e:
            logger.warning(f"Could not load trade history: {e}")
            self.trades = []