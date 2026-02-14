"""
Main Backtest Runner

Usage:
    python backtest/run_backtest.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from datetime import datetime
import json

from backtest.config import BacktestConfig
from backtest.data_loader import HistoricalDataFetcher
from backtest.engine import BacktestEngine
from backtest.check_data_availability import DataAvailabilityChecker

def main():
    """Run complete backtest"""
    # Configure logging based on ENABLE_LOGGING setting
    if not BacktestConfig.ENABLE_LOGGING:
        # Remove all handlers and disable logging completely
        logger.remove()
        # Add a sink that does nothing (suppresses all logs)
        logger.add(lambda msg: None, level="CRITICAL")
    
    # Get symbols with complete data coverage
    symbols_to_use = BacktestConfig.get_symbols()
    
    # Always print initial backtest summary (regardless of ENABLE_LOGGING)
    print("\n" + "="*80)
    print("SIGNAL BOT BACKTEST")
    print("="*80)
    print(f"Period:           {BacktestConfig.START_DATE.strftime('%Y-%m-%d')} to {BacktestConfig.END_DATE.strftime('%Y-%m-%d')}")
    print(f"Symbols:          {len(symbols_to_use)} symbols with complete data")
    print(f"Symbol List:      {', '.join(symbols_to_use)}")
    print(f"Initial Capital:  ${BacktestConfig.INITIAL_CAPITAL:,.0f}")
    print(f"Conservative:     {BacktestConfig.CONSERVATIVE_MODE}")
    print(f"Logging Enabled:  {BacktestConfig.ENABLE_LOGGING}")
    print("="*80 + "\n")
    
    if not symbols_to_use:
        print("ERROR: No symbols with complete data coverage - aborting backtest")
        return
    
    # Step 1: Fetch historical data
    if BacktestConfig.ENABLE_LOGGING:
        logger.info("\n[STEP 1/3] Fetching historical data...")
    fetcher = HistoricalDataFetcher()
    
    data = fetcher.fetch_all_data(
        symbols=symbols_to_use,  # Use filtered symbols
        start_date=BacktestConfig.START_DATE,
        end_date=BacktestConfig.END_DATE,
        timeframes=[
            BacktestConfig.HTF_TIMEFRAME,
            BacktestConfig.PRIMARY_TIMEFRAME,
            BacktestConfig.ENTRY_TIMEFRAME
        ]
    )
    
    if not data:
        if BacktestConfig.ENABLE_LOGGING:
            logger.error("Failed to fetch data - aborting backtest")
        return
    
    if BacktestConfig.ENABLE_LOGGING:
        logger.success("Data fetched successfully")
    
    # Step 2: Run backtest
    if BacktestConfig.ENABLE_LOGGING:
        logger.info("\n[STEP 2/3] Running backtest engine...")
    engine = BacktestEngine(data)
    results = engine.run()
    
    # Step 3: Display and save results
    if BacktestConfig.ENABLE_LOGGING:
        logger.info("\n[STEP 3/3] Processing results...")
    
    if 'error' in results:
        if BacktestConfig.ENABLE_LOGGING:
            logger.error(f"Backtest error: {results['error']}")
        return
    
    # Display results
    print_results(results, engine)
    
    # Save results
    save_results(results, engine, symbols_to_use)
    
    if BacktestConfig.ENABLE_LOGGING:
        logger.success("\nBacktest complete!")

def print_results(results: dict, engine: BacktestEngine):
    """Print formatted results"""
    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)
    
    # Performance
    print("\n📊 PERFORMANCE:")
    print(f"  Initial Equity:     ${results['initial_equity']:,.2f}")
    print(f"  Final Equity:       ${results['final_equity']:,.2f}")
    print(f"  Total Return:       {results['total_return_pct']:+.2f}%")
    print(f"  Total P&L:          ${results['total_pnl']:+,.2f}")
    print(f"  Fees Paid:          ${results['total_fees_paid']:,.2f}")
    
    # Trade stats
    print("\n📈 TRADE STATISTICS:")
    print(f"  Total Trades:       {results['total_trades']}")
    print(f"  Wins:               {results['wins']} ({results['win_rate']:.1f}%)")
    print(f"  Losses:             {results['losses']} ({100-results['win_rate']:.1f}%)")
    print(f"  Win Rate:           {results['win_rate']:.2f}%")
    
    # Quality metrics
    print("\n⚡ QUALITY METRICS:")
    print(f"  Profit Factor:      {results['profit_factor']:.2f}")
    print(f"  Expectancy:         ${results['expectancy']:+.2f} per trade")
    print(f"  Sharpe Ratio:       {results['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown:       {results['max_drawdown_pct']:.2f}%")
    print(f"  Longest Streak:     {results['longest_losing_streak']} losses")
    
    # Win/Loss breakdown
    print("\n💰 WIN/LOSS BREAKDOWN:")
    print(f"  Gross Profit:       ${results['gross_profit']:,.2f}")
    print(f"  Gross Loss:         ${results['gross_loss']:,.2f}")
    print(f"  Average Win:        ${results['avg_win']:,.2f}")
    print(f"  Average Loss:       ${results['avg_loss']:,.2f}")
    print(f"  Avg Duration:       {results['avg_duration_hours']:.1f} hours")
    
    # By regime
    if 'trades_by_regime' in results and results['trades_by_regime']:
        print("\n🌊 PERFORMANCE BY REGIME:")
        regime_data = results['trades_by_regime']
        for regime in regime_data.get('count', {}).keys():
            count = regime_data['count'][regime]
            total = regime_data['sum'][regime]
            avg = regime_data['mean'][regime]
            print(f"  {regime:15} {count:3.0f} trades | ${total:+8,.2f} | Avg: ${avg:+6,.2f}")
    
    # By symbol
    if 'trades_by_symbol' in results and results['trades_by_symbol']:
        print("\n📍 PERFORMANCE BY SYMBOL:")
        symbol_data = results['trades_by_symbol']
        for symbol in symbol_data.get('count', {}).keys():
            count = symbol_data['count'][symbol]
            total = symbol_data['sum'][symbol]
            avg = symbol_data['mean'][symbol]
            print(f"  {symbol:10} {count:3.0f} trades | ${total:+8,.2f} | Avg: ${avg:+6,.2f}")
    
    # Exit reasons
    if 'trades_by_exit_reason' in results and results['trades_by_exit_reason']:
        print("\n🚪 EXIT REASONS:")
        exit_data = results['trades_by_exit_reason']
        for reason in exit_data.get('count', {}).keys():
            count = exit_data['count'][reason]
            total = exit_data['sum'][reason]
            print(f"  {reason:15} {count:3.0f} trades | ${total:+8,.2f}")
    
    print("\n" + "="*80)

def save_results(results: dict, engine: BacktestEngine, symbols: list):
    """Save results to JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backtest_{timestamp}.json"
    filepath = Path(__file__).parent / 'results' / filename
    
    # Prepare data for JSON
    output = {
        'config': {
            'start_date': str(BacktestConfig.START_DATE),
            'end_date': str(BacktestConfig.END_DATE),
            'symbols': symbols,
            'initial_capital': BacktestConfig.INITIAL_CAPITAL,
            'conservative_mode': BacktestConfig.CONSERVATIVE_MODE,
            'slippage': BacktestConfig.SLIPPAGE_PERCENT,
            'fees': BacktestConfig.TAKER_FEE
        },
        'results': results,
        'trades': [
            {
                'symbol': t.symbol,
                'direction': t.direction,
                'entry_time': str(t.entry_time),
                'entry_price': t.entry_price,
                'exit_time': str(t.exit_time),
                'exit_price': t.exit_price,
                'pnl': t.pnl,
                'pnl_percent': t.pnl_percent,
                'exit_reason': t.exit_reason,
                'regime': t.regime,
                'score': t.score,
                'duration_hours': t.duration_hours
            }
            for t in engine.closed_trades
        ],
        'equity_curve': [
            {'time': str(time), 'equity': equity}
            for time, equity in engine.equity_curve
        ]
    }
    
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)
    
    if BacktestConfig.ENABLE_LOGGING:
        logger.info(f"Results saved to: {filepath}")
    
    # Also save a CSV of trades for easy analysis
    import pandas as pd
    trades_df = pd.DataFrame(output['trades'])
    csv_path = filepath.with_suffix('.csv')
    trades_df.to_csv(csv_path, index=False)
    if BacktestConfig.ENABLE_LOGGING:
        logger.info(f"Trades CSV saved to: {csv_path}")

if __name__ == '__main__':
    main()
