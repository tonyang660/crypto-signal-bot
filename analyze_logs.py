import json
from datetime import datetime
from collections import defaultdict
import statistics

# Load the trade history
with open('/Users/tonyyang/Downloads/Signalbot Trade History.json', 'r') as f:
    trades = json.load(f)

# Load active positions
with open('/Users/tonyyang/Downloads/Signalbot State Active Paper.json', 'r') as f:
    active_positions = json.load(f)

print("=" * 80)
print("TRADING BOT PERFORMANCE ANALYSIS")
print("=" * 80)

# Overall Statistics
total_trades = len(trades)
wins = [t for t in trades if t['pnl'] > 0]
losses = [t for t in trades if t['pnl'] < 0]
win_count = len(wins)
loss_count = len(losses)
win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

total_pnl = sum(t['pnl'] for t in trades)
total_wins = sum(t['pnl'] for t in wins)
total_losses = abs(sum(t['pnl'] for t in losses))
profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf')

avg_win = statistics.mean([t['pnl'] for t in wins]) if wins else 0
avg_loss = statistics.mean([t['pnl'] for t in losses]) if losses else 0
avg_trade = total_pnl / total_trades if total_trades > 0 else 0

print(f"\n📊 OVERALL PERFORMANCE")
print(f"{'─' * 80}")
print(f"Total Trades:        {total_trades}")
print(f"Wins:                {win_count} ({win_rate:.1f}%)")
print(f"Losses:              {loss_count} ({100-win_rate:.1f}%)")
print(f"Total P&L:           ${total_pnl:+,.2f}")
print(f"Profit Factor:       {profit_factor:.2f}")
print(f"Average Win:         ${avg_win:+,.2f}")
print(f"Average Loss:        ${avg_loss:+,.2f}")
print(f"Average Trade:       ${avg_trade:+,.2f}")
print(f"Win/Loss Ratio:      {abs(avg_win/avg_loss):.2f}x" if avg_loss != 0 else "N/A")

# Best and Worst Trades
best_trade = max(trades, key=lambda x: x['pnl'])
worst_trade = min(trades, key=lambda x: x['pnl'])

print(f"\n🏆 BEST TRADE:  {best_trade['symbol']} {best_trade['direction']} | ${best_trade['pnl']:+,.2f}")
print(f"💀 WORST TRADE: {worst_trade['symbol']} {worst_trade['direction']} | ${worst_trade['pnl']:+,.2f}")

# Performance by Symbol
print(f"\n📈 PERFORMANCE BY SYMBOL")
print(f"{'─' * 80}")
symbol_stats = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0})
for t in trades:
    symbol_stats[t['symbol']]['trades'] += 1
    symbol_stats[t['symbol']]['pnl'] += t['pnl']
    if t['pnl'] > 0:
        symbol_stats[t['symbol']]['wins'] += 1

# Sort by total PnL
sorted_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)
print(f"{'Symbol':<12} {'Trades':>7} {'Wins':>6} {'Win%':>6} {'Total P&L':>12}")
print(f"{'─' * 80}")
for symbol, stats in sorted_symbols[:15]:  # Top 15
    wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
    print(f"{symbol:<12} {stats['trades']:>7} {stats['wins']:>6} {wr:>5.1f}% ${stats['pnl']:>10,.2f}")

# Performance by Direction
long_trades = [t for t in trades if t['direction'] == 'long']
short_trades = [t for t in trades if t['direction'] == 'short']

long_pnl = sum(t['pnl'] for t in long_trades)
short_pnl = sum(t['pnl'] for t in short_trades)
long_wr = (len([t for t in long_trades if t['pnl'] > 0]) / len(long_trades) * 100) if long_trades else 0
short_wr = (len([t for t in short_trades if t['pnl'] > 0]) / len(short_trades) * 100) if short_trades else 0

print(f"\n📊 PERFORMANCE BY DIRECTION")
print(f"{'─' * 80}")
print(f"LONG:  {len(long_trades):>3} trades | Win Rate: {long_wr:>5.1f}% | P&L: ${long_pnl:+,.2f}")
print(f"SHORT: {len(short_trades):>3} trades | Win Rate: {short_wr:>5.1f}% | P&L: ${short_pnl:+,.2f}")

# Performance by Exit Reason
print(f"\n🎯 PERFORMANCE BY EXIT REASON")
print(f"{'─' * 80}")
exit_stats = defaultdict(lambda: {'count': 0, 'pnl': 0})
for t in trades:
    exit_stats[t['exit_reason']]['count'] += 1
    exit_stats[t['exit_reason']]['pnl'] += t['pnl']

sorted_exits = sorted(exit_stats.items(), key=lambda x: x[1]['count'], reverse=True)
print(f"{'Exit Reason':<20} {'Count':>7} {'Total P&L':>12} {'Avg P&L':>10}")
print(f"{'─' * 80}")
for reason, stats in sorted_exits:
    avg = stats['pnl'] / stats['count'] if stats['count'] > 0 else 0
    print(f"{reason:<20} {stats['count']:>7} ${stats['pnl']:>10,.2f} ${avg:>8,.2f}")

# Performance by Hour of Day
print(f"\n⏰ PERFORMANCE BY HOUR (Top 10)")
print(f"{'─' * 80}")
hour_stats = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0})
for t in trades:
    hour = t['hour_of_day']
    hour_stats[hour]['trades'] += 1
    hour_stats[hour]['pnl'] += t['pnl']
    if t['pnl'] > 0:
        hour_stats[hour]['wins'] += 1

sorted_hours = sorted(hour_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)
print(f"{'Hour':>4} {'Trades':>7} {'Wins':>6} {'Win%':>6} {'Total P&L':>12}")
print(f"{'─' * 80}")
for hour, stats in sorted_hours[:10]:
    wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
    print(f"{hour:>4} {stats['trades']:>7} {stats['wins']:>6} {wr:>5.1f}% ${stats['pnl']:>10,.2f}")

# Performance by Regime
print(f"\n🌊 PERFORMANCE BY MARKET REGIME")
print(f"{'─' * 80}")
regime_stats = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0})
for t in trades:
    regime = t.get('regime', 'unknown')
    regime_stats[regime]['trades'] += 1
    regime_stats[regime]['pnl'] += t['pnl']
    if t['pnl'] > 0:
        regime_stats[regime]['wins'] += 1

sorted_regimes = sorted(regime_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)
print(f"{'Regime':<15} {'Trades':>7} {'Wins':>6} {'Win%':>6} {'Total P&L':>12}")
print(f"{'─' * 80}")
for regime, stats in sorted_regimes:
    wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
    print(f"{regime:<15} {stats['trades']:>7} {stats['wins']:>6} {wr:>5.1f}% ${stats['pnl']:>10,.2f}")

# Consecutive Wins/Losses Analysis
print(f"\n🔥 STREAK ANALYSIS")
print(f"{'─' * 80}")
max_win_streak = 0
max_loss_streak = 0
current_streak = 0
streak_type = None

for t in trades:
    if t['pnl'] > 0:
        if streak_type == 'win':
            current_streak += 1
        else:
            current_streak = 1
            streak_type = 'win'
        max_win_streak = max(max_win_streak, current_streak)
    else:
        if streak_type == 'loss':
            current_streak += 1
        else:
            current_streak = 1
            streak_type = 'loss'
        max_loss_streak = max(max_loss_streak, current_streak)

print(f"Max Winning Streak:  {max_win_streak} trades")
print(f"Max Losing Streak:   {max_loss_streak} trades")

# Active Positions Analysis
print(f"\n📍 ACTIVE POSITIONS")
print(f"{'─' * 80}")
total_unrealized = 0
open_positions = 0
for symbol, pos in active_positions.items():
    if pos.get('execution_state') == 'position_open':
        open_positions += 1
        unrealized = pos.get('unrealized_pnl', 0)
        total_unrealized += unrealized
        print(f"{symbol:<12} {pos['direction']:<6} Entry: ${pos['entry_price']:<10} "
              f"Current: ${pos['current_price']:<10} P&L: ${unrealized:+,.2f}")

print(f"\nOpen Positions: {open_positions}")
print(f"Total Unrealized P&L: ${total_unrealized:+,.2f}")

# Recent Performance (Last 20 trades)
print(f"\n📅 RECENT PERFORMANCE (Last 20 Trades)")
print(f"{'─' * 80}")
recent_trades = trades[-20:]
recent_pnl = sum(t['pnl'] for t in recent_trades)
recent_wins = len([t for t in recent_trades if t['pnl'] > 0])
recent_wr = (recent_wins / len(recent_trades) * 100) if recent_trades else 0
print(f"Trades: {len(recent_trades)} | Win Rate: {recent_wr:.1f}% | P&L: ${recent_pnl:+,.2f}")

print("\nLast 10 Trades:")
print(f"{'Symbol':<12} {'Dir':<6} {'P&L':>10} {'Exit Reason':<15}")
print(f"{'─' * 80}")
for t in trades[-10:]:
    print(f"{t['symbol']:<12} {t['direction']:<6} ${t['pnl']:>8,.2f} {t['exit_reason']:<15}")

print("\n" + "=" * 80)
print("END OF ANALYSIS")
print("=" * 80)
