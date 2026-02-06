"""
Check Paper Trading Status

Quick utility to view paper trading account status and performance.
"""

import json
import os
from datetime import datetime
from pathlib import Path

def load_json(file_path):
    """Load JSON file safely"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

def format_currency(amount):
    """Format currency with color"""
    if amount > 0:
        return f"${amount:+,.2f}"
    elif amount < 0:
        return f"${amount:,.2f}"
    else:
        return f"${amount:,.2f}"

def main():
    print("=" * 80)
    print("📊 PAPER TRADING STATUS")
    print("=" * 80)
    
    # Check if paper trading is enabled
    paper_account_file = "data/paper_account.json"
    
    if not os.path.exists(paper_account_file):
        print("\n⚠️  Paper trading account not initialized yet.")
        print("Run the bot with PAPER_TRADING_ENABLED=true to start paper trading.\n")
        return
    
    # Load paper account
    account = load_json(paper_account_file)
    
    if not account:
        print("\n❌ Could not load paper account data.\n")
        return
    
    # Display account summary
    print("\n💰 ACCOUNT SUMMARY")
    print("-" * 80)
    
    balance = account.get('balance', 0)
    initial = account.get('initial_capital', 0)
    total_pnl = account.get('total_realized_pnl', 0)
    fees_paid = account.get('total_fees_paid', 0)
    funding_costs = account.get('total_funding_costs', 0)
    
    # Calculate equity (would need to add unrealized PnL from open positions)
    equity = balance
    total_return = ((equity - initial) / initial * 100) if initial > 0 else 0
    
    print(f"Initial Capital:      ${initial:,.2f}")
    print(f"Current Balance:      ${balance:,.2f}")
    print(f"Current Equity:       ${equity:,.2f}")
    print(f"Total Return:         {format_currency(equity - initial)} ({total_return:+.2f}%)")
    print(f"")
    print(f"Realized P&L:         {format_currency(total_pnl)}")
    print(f"Fees Paid:            ${fees_paid:,.2f}")
    print(f"Funding Costs:        ${funding_costs:,.2f}")
    print(f"Net P&L:              {format_currency(total_pnl - fees_paid - funding_costs)}")
    
    # Trading stats
    print(f"\n📊 TRADING STATISTICS")
    print("-" * 80)
    
    positions_opened = account.get('positions_count', 0)
    trades_closed = account.get('trades_count', 0)
    
    print(f"Total Positions Opened:  {positions_opened}")
    print(f"Total Trades Closed:     {trades_closed}")
    
    if trades_closed > 0:
        avg_pnl = total_pnl / trades_closed
        print(f"Average P&L per Trade:   {format_currency(avg_pnl)}")
    
    # Equity curve
    equity_curve = account.get('equity_curve', [])
    if len(equity_curve) > 1:
        print(f"\n📈 EQUITY CURVE")
        print("-" * 80)
        print(f"Snapshots Recorded:      {len(equity_curve)}")
        
        latest = equity_curve[-1]
        print(f"\nLatest Snapshot ({latest.get('timestamp', 'N/A')}):")
        print(f"  Equity:                ${latest.get('equity', 0):,.2f}")
        print(f"  Balance:               ${latest.get('balance', 0):,.2f}")
        print(f"  Unrealized P&L:        {format_currency(latest.get('unrealized_pnl', 0))}")
        print(f"  Open Positions:        {latest.get('open_positions', 0)}")
    
    # Load active signals to see paper trading positions
    signals_file = "data/signals_active.json"
    if os.path.exists(signals_file):
        signals = load_json(signals_file)
        if signals:
            paper_signals = {k: v for k, v in signals.items() if v.get('paper_trading', False)}
            
            if paper_signals:
                print(f"\n📋 ACTIVE PAPER POSITIONS")
                print("-" * 80)
                
                for symbol, signal in paper_signals.items():
                    direction = signal.get('direction', 'N/A').upper()
                    exec_state = signal.get('execution_state', 'unknown')
                    entry = signal.get('entry_price', 0)
                    current = signal.get('current_price', 0)
                    remaining = signal.get('remaining_percent', 100)
                    realized_pnl = signal.get('realized_pnl', 0)
                    fees = signal.get('fees_paid', 0)
                    
                    print(f"\n{symbol} ({direction}):")
                    print(f"  Status:                {exec_state}")
                    print(f"  Entry Price:           ${entry:,.2f}")
                    print(f"  Current Price:         ${current:,.2f}")
                    print(f"  Remaining:             {remaining}%")
                    print(f"  Realized P&L:          {format_currency(realized_pnl)}")
                    print(f"  Fees Paid:             ${fees:.2f}")
            else:
                print(f"\n✅ No active paper trading positions")
    
    # Last updated
    last_updated = account.get('last_updated', 'Unknown')
    print(f"\n")
    print("-" * 80)
    print(f"Last Updated: {last_updated}")
    print("=" * 80)
    print()

if __name__ == "__main__":
    main()
