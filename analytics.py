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

# Detect mode from paper_account existence
PAPER_MODE = (DATA_DIR / 'paper_account.json').exists()

TRADE_HISTORY_FILE = DATA_DIR / ('trade_history_paper.json' if PAPER_MODE else 'trade_history.json')
PAPER_ACCOUNT_FILE = DATA_DIR / 'paper_account.json'
SIGNALS_HISTORY_FILE = DATA_DIR / ('signals_history_paper.json' if PAPER_MODE else 'signals_history.json')

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
    
    def analyze_paper_trading(self):
        """Analyze paper trading performance with execution costs"""
        print("\n" + "="*80)
        print("📊 PAPER TRADING PERFORMANCE")
        print("="*80 + "\n")
        
        # Load paper account data
        try:
            if PAPER_ACCOUNT_FILE.exists():
                with open(PAPER_ACCOUNT_FILE, 'r') as f:
                    account = json.load(f)
            else:
                print("⚠️  Paper trading account not found. Enable paper trading to see stats.\n")
                return
        except Exception as e:
            logger.error(f"Error loading paper account: {e}")
            return
        
        # Load signal history for paper trading specific data
        paper_signals = []
        try:
            if SIGNALS_HISTORY_FILE.exists():
                with open(SIGNALS_HISTORY_FILE, 'r') as f:
                    all_signals = json.load(f)
                    # Filter for paper trading signals
                    paper_signals = [s for s in all_signals if s.get('paper_trading', False)]
        except Exception as e:
            logger.error(f"Error loading signals history: {e}")
        
        # Account summary
        initial = account.get('initial_capital', 0)
        balance = account.get('balance', 0)
        total_pnl = account.get('total_realized_pnl', 0)
        fees_paid = account.get('total_fees_paid', 0)
        funding_costs = account.get('total_funding_costs', 0)
        trades_count = account.get('trades_count', 0)
        
        total_return = ((balance - initial) / initial * 100) if initial > 0 else 0
        net_pnl = total_pnl - fees_paid - funding_costs
        
        print("💰 ACCOUNT SUMMARY")
        print("-" * 40)
        print(f"Initial Capital:        ${initial:,.2f}")
        print(f"Current Balance:        ${balance:,.2f}")
        print(f"Total Return:           ${balance - initial:+,.2f} ({total_return:+.2f}%)")
        print()
        
        print("📈 P&L BREAKDOWN")
        print("-" * 40)
        print(f"Gross P&L:              ${total_pnl:+,.2f}")
        print(f"Trading Fees:           -${fees_paid:,.2f}")
        print(f"Funding Costs:          -${funding_costs:,.2f}")
        print(f"Net P&L:                ${net_pnl:+,.2f}")
        print()
        
        if trades_count > 0:
            avg_pnl = net_pnl / trades_count
            avg_fees = fees_paid / trades_count
            fee_impact_pct = (fees_paid / abs(total_pnl) * 100) if total_pnl != 0 else 0
            
            print("💸 COST ANALYSIS")
            print("-" * 40)
            print(f"Total Trades:           {trades_count}")
            print(f"Avg P&L per Trade:      ${avg_pnl:+,.2f}")
            print(f"Avg Fee per Trade:      ${avg_fees:.2f}")
            print(f"Fee Impact on P&L:      {fee_impact_pct:.1f}%")
            print()
        
        # Slippage analysis from paper trading signals
        if paper_signals:
            slippages = [s.get('entry_slippage', 0) for s in paper_signals if 'entry_slippage' in s]
            if slippages:
                avg_slippage = sum(slippages) / len(slippages) * 100
                max_slippage = max(slippages) * 100
                
                print("📉 EXECUTION QUALITY")
                print("-" * 40)
                print(f"Signals with Execution: {len(slippages)}")
                print(f"Avg Entry Slippage:     {avg_slippage:.3f}%")
                print(f"Max Entry Slippage:     {max_slippage:.3f}%")
                print()
        
        # Equity curve overview
        equity_curve = account.get('equity_curve', [])
        if len(equity_curve) > 1:
            peak_equity = max(e.get('equity', 0) for e in equity_curve)
            current_equity = equity_curve[-1].get('equity', 0)
            drawdown = ((peak_equity - current_equity) / peak_equity * 100) if peak_equity > 0 else 0
            
            print("📊 EQUITY CURVE")
            print("-" * 40)
            print(f"Peak Equity:            ${peak_equity:,.2f}")
            print(f"Current Equity:         ${current_equity:,.2f}")
            print(f"Drawdown from Peak:     {drawdown:.2f}%")
            print(f"Total Snapshots:        {len(equity_curve)}")
            print()
        
        # Compare simulated vs execution-adjusted performance
        if paper_signals and trades_count > 0:
            # Calculate what P&L would have been without fees/slippage
            theoretical_pnl = total_pnl + fees_paid + funding_costs
            execution_cost = fees_paid + funding_costs
            
            print("🔬 SIMULATION VS REALITY")
            print("-" * 40)
            print(f"Theoretical P&L:        ${theoretical_pnl:+,.2f} (no costs)")
            print(f"Execution Costs:        -${execution_cost:,.2f}")
            print(f"Actual P&L:             ${total_pnl:+,.2f}")
            print(f"Cost Impact:            {(execution_cost/abs(theoretical_pnl)*100):.1f}% of gross P&L")
            print()
    
    def generate_summary(self):
        """Generate overall summary"""
        if not self.trades:
            print("\n⚠️  No trade data available for analysis\n")
            # Still show paper trading stats if available
            self.analyze_paper_trading()
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
        
        # Paper trading specific analysis
        self.analyze_paper_trading()
        
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
