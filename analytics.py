"""
Performance analytics by market regime and other key metrics

Usage:
    python analytics.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<level>{message}</level>")

# File paths
DATA_DIR = Path('data')
TRADE_HISTORY_FILE = DATA_DIR / 'trade_history.json'

class PerformanceAnalytics:
    """Analyze trading performance by regime, time, symbol, etc."""
    
    def __init__(self):
        self.trades = self._load_trades()
    
    def _load_trades(self):
        """Load trade history"""
        try:
            if TRADE_HISTORY_FILE.exists():
                with open(TRADE_HISTORY_FILE, 'r') as f:
                    trades = json.load(f)
                logger.info(f"✓ Loaded {len(trades)} trades")
                return trades
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
        return []
    
    def analyze_by_regime(self):
        """Analyze win rate and profitability by market regime"""
        print("\n" + "="*80)
        print("PERFORMANCE BY MARKET REGIME")
        print("="*80 + "\n")
        
        regime_stats = defaultdict(lambda: {
            'total': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0,
            'avg_win': [],
            'avg_loss': [],
            'avg_duration': []
        })
        
        for trade in self.trades:
            regime = trade.get('regime', 'unknown')
            pnl = trade.get('pnl', 0)
            duration = trade.get('duration_hours', 0)
            
            regime_stats[regime]['total'] += 1
            regime_stats[regime]['total_pnl'] += pnl
            regime_stats[regime]['avg_duration'].append(duration)
            
            if pnl > 0:
                regime_stats[regime]['wins'] += 1
                regime_stats[regime]['avg_win'].append(pnl)
            else:
                regime_stats[regime]['losses'] += 1
                regime_stats[regime]['avg_loss'].append(pnl)
        
        # Sort by total trades
        sorted_regimes = sorted(regime_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        for regime, stats in sorted_regimes:
            total = stats['total']
            wins = stats['wins']
            losses = stats['losses']
            win_rate = (wins / total * 100) if total > 0 else 0
            
            avg_win = sum(stats['avg_win']) / len(stats['avg_win']) if stats['avg_win'] else 0
            avg_loss = sum(stats['avg_loss']) / len(stats['avg_loss']) if stats['avg_loss'] else 0
            avg_duration = sum(stats['avg_duration']) / len(stats['avg_duration']) if stats['avg_duration'] else 0
            
            profit_factor = abs(avg_win * wins / (avg_loss * losses)) if losses > 0 and avg_loss != 0 else float('inf')
            
            emoji = {"trending": "📈", "high_volatility": "⚡", "choppy": "〰️", "low_volatility": "💤"}.get(regime, "❓")
            
            print(f"{emoji} {regime.upper()}")
            print(f"   Trades: {total} ({wins}W / {losses}L)")
            print(f"   Win Rate: {win_rate:.1f}%")
            print(f"   Total P&L: ${stats['total_pnl']:+.2f}")
            print(f"   Avg Win: ${avg_win:.2f} | Avg Loss: ${avg_loss:.2f}")
            print(f"   Profit Factor: {profit_factor:.2f}")
            print(f"   Avg Duration: {avg_duration:.1f} hours")
            print()
    
    def analyze_by_symbol(self):
        """Analyze performance by trading pair"""
        print("\n" + "="*80)
        print("PERFORMANCE BY SYMBOL")
        print("="*80 + "\n")
        
        symbol_stats = defaultdict(lambda: {
            'total': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0
        })
        
        for trade in self.trades:
            symbol = trade.get('symbol', 'unknown')
            pnl = trade.get('pnl', 0)
            
            symbol_stats[symbol]['total'] += 1
            symbol_stats[symbol]['total_pnl'] += pnl
            
            if pnl > 0:
                symbol_stats[symbol]['wins'] += 1
            else:
                symbol_stats[symbol]['losses'] += 1
        
        # Sort by total P&L
        sorted_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['total_pnl'], reverse=True)
        
        for symbol, stats in sorted_symbols:
            total = stats['total']
            wins = stats['wins']
            win_rate = (wins / total * 100) if total > 0 else 0
            
            print(f"💱 {symbol}")
            print(f"   Trades: {total} ({wins}W / {stats['losses']}L)")
            print(f"   Win Rate: {win_rate:.1f}%")
            print(f"   Total P&L: ${stats['total_pnl']:+.2f}")
            print()
    
    def analyze_by_hour(self):
        """Analyze performance by hour of day"""
        print("\n" + "="*80)
        print("PERFORMANCE BY HOUR OF DAY")
        print("="*80 + "\n")
        
        hour_stats = defaultdict(lambda: {
            'total': 0,
            'wins': 0,
            'total_pnl': 0
        })
        
        for trade in self.trades:
            hour = trade.get('hour_of_day', 0)
            pnl = trade.get('pnl', 0)
            
            hour_stats[hour]['total'] += 1
            hour_stats[hour]['total_pnl'] += pnl
            
            if pnl > 0:
                hour_stats[hour]['wins'] += 1
        
        # Show only hours with trades
        active_hours = sorted([h for h in hour_stats.keys() if hour_stats[h]['total'] > 0])
        
        for hour in active_hours:
            stats = hour_stats[hour]
            total = stats['total']
            wins = stats['wins']
            win_rate = (wins / total * 100) if total > 0 else 0
            
            print(f"🕐 {hour:02d}:00 UTC")
            print(f"   Trades: {total} ({wins}W)")
            print(f"   Win Rate: {win_rate:.1f}%")
            print(f"   Total P&L: ${stats['total_pnl']:+.2f}")
            print()
    
    def analyze_by_exit_reason(self):
        """Analyze performance by exit reason"""
        print("\n" + "="*80)
        print("PERFORMANCE BY EXIT REASON")
        print("="*80 + "\n")
        
        exit_stats = defaultdict(lambda: {
            'total': 0,
            'total_pnl': 0,
            'avg_duration': []
        })
        
        for trade in self.trades:
            exit_reason = trade.get('exit_reason', 'unknown')
            pnl = trade.get('pnl', 0)
            duration = trade.get('duration_hours', 0)
            
            exit_stats[exit_reason]['total'] += 1
            exit_stats[exit_reason]['total_pnl'] += pnl
            exit_stats[exit_reason]['avg_duration'].append(duration)
        
        for exit_reason, stats in exit_stats.items():
            total = stats['total']
            avg_duration = sum(stats['avg_duration']) / len(stats['avg_duration']) if stats['avg_duration'] else 0
            
            emoji = {"completed": "🎯", "stopped": "🛑", "manual": "✋"}.get(exit_reason, "❓")
            
            print(f"{emoji} {exit_reason.upper()}")
            print(f"   Trades: {total}")
            print(f"   Total P&L: ${stats['total_pnl']:+.2f}")
            print(f"   Avg P&L: ${stats['total_pnl']/total:+.2f}")
            print(f"   Avg Duration: {avg_duration:.1f} hours")
            print()
    
    def generate_summary(self):
        """Generate overall summary"""
        if not self.trades:
            print("\n⚠️  No trade data available for analysis\n")
            return
        
        print("\n" + "="*80)
        print("📊 TRADING PERFORMANCE ANALYTICS")
        print("="*80)
        
        # Overall stats
        total_trades = len(self.trades)
        wins = len([t for t in self.trades if t.get('pnl', 0) > 0])
        losses = len([t for t in self.trades if t.get('pnl', 0) <= 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(t.get('pnl', 0) for t in self.trades)
        
        print(f"\nTotal Trades: {total_trades}")
        print(f"Wins: {wins} | Losses: {losses}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Total P&L: ${total_pnl:+.2f}")
        
        # Detailed breakdowns
        self.analyze_by_regime()
        self.analyze_by_symbol()
        self.analyze_by_exit_reason()
        self.analyze_by_hour()
        
        print("="*80 + "\n")

def main():
    """Main entry point"""
    analytics = PerformanceAnalytics()
    analytics.generate_summary()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
