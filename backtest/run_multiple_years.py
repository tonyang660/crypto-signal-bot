"""
Run Multiple Year Backtests

Runs backtests for 2023, 2024, and 2025 sequentially.
Results are saved separately for each year.

Usage:
    python backtest/run_multiple_years.py
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

# Define backtest periods for each year
BACKTEST_PERIODS = [
    {
        'name': '2023',
        'start': datetime(2022, 12, 1),   # Start 1 month earlier for warmup
        'warmup': datetime(2023, 1, 1),   # Begin actual backtest here
        'end': datetime(2023, 12, 31)
    },
    {
        'name': '2024',
        'start': datetime(2023, 12, 1),   # Start 1 month earlier for warmup
        'warmup': datetime(2024, 1, 1),   # Begin actual backtest here
        'end': datetime(2024, 12, 31)
    },
    {
        'name': '2025',
        'start': datetime(2024, 12, 1),   # Start 1 month earlier for warmup
        'warmup': datetime(2025, 1, 1),   # Begin actual backtest here
        'end': datetime(2025, 12, 31)
    }
]

def run_backtest_for_period(period: dict) -> dict:
    """Run backtest for a specific period"""
    print("\n" + "="*80)
    print(f"BACKTEST: {period['name']}")
    print("="*80)
    print(f"Period:           {period['warmup'].strftime('%Y-%m-%d')} to {period['end'].strftime('%Y-%m-%d')}")
    print(f"Warmup Period:    {period['start'].strftime('%Y-%m-%d')} to {period['warmup'].strftime('%Y-%m-%d')}")
    print(f"Initial Capital:  ${BacktestConfig.INITIAL_CAPITAL:,.0f}")
    print("="*80 + "\n")
    
    # Temporarily override config dates
    original_start = BacktestConfig.START_DATE
    original_warmup = BacktestConfig.WARMUP_DATE
    original_end = BacktestConfig.END_DATE
    
    BacktestConfig.START_DATE = period['start']
    BacktestConfig.WARMUP_DATE = period['warmup']
    BacktestConfig.END_DATE = period['end']
    
    # CRITICAL: Clear symbol cache to force re-detection for this period
    # Without this, all years use the same symbol list from first year
    BacktestConfig._symbols_cache = None
    
    try:
        # Get symbols with complete data coverage
        symbols_to_use = BacktestConfig.get_symbols()
        
        if not symbols_to_use:
            print(f"ERROR: No symbols with complete data coverage for {period['name']}")
            return {'error': 'No data available', 'year': period['name']}
        
        print(f"Symbols:          {len(symbols_to_use)} symbols with complete data")
        print(f"Symbol List:      {', '.join(symbols_to_use)}")
        print()
        
        # Fetch historical data
        print(f"[1/3] Fetching historical data for {period['name']}...")
        fetcher = HistoricalDataFetcher()
        
        data = fetcher.fetch_all_data(
            symbols=symbols_to_use,
            start_date=period['start'],
            end_date=period['end'],
            timeframes=[
                BacktestConfig.HTF_TIMEFRAME,
                BacktestConfig.PRIMARY_TIMEFRAME,
                BacktestConfig.ENTRY_TIMEFRAME
            ]
        )
        
        if not data:
            print(f"ERROR: Failed to fetch data for {period['name']}")
            return {'error': 'Data fetch failed', 'year': period['name']}
        
        print(f"✓ Data fetched successfully\n")
        
        # Run backtest
        print(f"[2/3] Running backtest engine for {period['name']}...")
        engine = BacktestEngine(data)
        results = engine.run()
        
        if 'error' in results:
            print(f"ERROR: Backtest error for {period['name']}: {results['error']}")
            return results
        
        print(f"✓ Backtest complete\n")
        
        # Add year and symbol info to results
        results['year'] = period['name']
        results['symbols_tested'] = symbols_to_use
        results['period_start'] = period['warmup'].strftime('%Y-%m-%d')
        results['period_end'] = period['end'].strftime('%Y-%m-%d')
        
        # Print quick summary
        print(f"[3/3] Results for {period['name']}:")
        print(f"  Total Trades:     {results['total_trades']}")
        print(f"  Win Rate:         {results['win_rate']:.1f}%")
        print(f"  Total P&L:        ${results['total_pnl']:+,.2f}")
        print(f"  Total Return:     {results['total_return_pct']:+.2f}%")
        print(f"  Final Equity:     ${results['final_equity']:,.2f}")
        print(f"  Max Drawdown:     {results['max_drawdown_pct']:.2f}%")
        print(f"  Profit Factor:    {results['profit_factor']:.2f}")
        
        # Save results to file
        results_dir = Path('backtest/results')
        results_dir.mkdir(parents=True, exist_ok=True)
        
        results_file = results_dir / f'backtest_{period["name"]}.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n✓ Results saved to {results_file}")
        
        return results
        
    finally:
        # Restore original config
        BacktestConfig.START_DATE = original_start
        BacktestConfig.WARMUP_DATE = original_warmup
        BacktestConfig.END_DATE = original_end

def print_comparison(all_results: list):
    """Print comparison table of all years"""
    print("\n\n" + "="*100)
    print("MULTI-YEAR COMPARISON")
    print("="*100)
    
    # Header
    print(f"{'Metric':<30} {'2023':<20} {'2024':<20} {'2025':<20}")
    print("-"*100)
    
    # Extract results by year
    results_by_year = {r['year']: r for r in all_results if 'error' not in r}
    
    metrics = [
        ('Total Trades', 'total_trades', ''),
        ('Win Rate', 'win_rate', '%'),
        ('Total P&L', 'total_pnl', '$'),
        ('Total Return', 'total_return_pct', '%'),
        ('Final Equity', 'final_equity', '$'),
        ('Profit Factor', 'profit_factor', ''),
        ('Max Drawdown', 'max_drawdown_pct', '%'),
        ('Avg Win', 'avg_win', '$'),
        ('Avg Loss', 'avg_loss', '$'),
        ('Expectancy', 'expectancy', '$'),
        ('Long/Short Ratio', 'long_short_ratio', ''),
        ('Long Win Rate', 'long_win_rate', '%'),
        ('Short Win Rate', 'short_win_rate', '%'),
    ]
    
    for metric_name, metric_key, suffix in metrics:
        row = f"{metric_name:<30}"
        
        for year in ['2023', '2024', '2025']:
            if year in results_by_year:
                value = results_by_year[year].get(metric_key, 'N/A')
                
                if isinstance(value, (int, float)):
                    if suffix == '$':
                        row += f"{value:+,.2f}{suffix:<17}"
                    elif suffix == '%':
                        row += f"{value:+.2f}{suffix:<18}"
                    else:
                        row += f"{value:.2f}{suffix:<18}"
                else:
                    row += f"{str(value):<20}"
            else:
                row += f"{'N/A':<20}"
        
        print(row)
    
    print("="*100)
    
    # Calculate combined stats
    total_trades = sum(r.get('total_trades', 0) for r in results_by_year.values())
    total_pnl = sum(r.get('total_pnl', 0) for r in results_by_year.values())
    
    print(f"\n{'COMBINED (All Years)':<30}")
    print(f"  Total Trades Across All Years:  {total_trades}")
    print(f"  Combined Total P&L:              ${total_pnl:+,.2f}")
    
    if results_by_year:
        avg_win_rate = sum(r.get('win_rate', 0) for r in results_by_year.values()) / len(results_by_year)
        avg_profit_factor = sum(r.get('profit_factor', 0) for r in results_by_year.values()) / len(results_by_year)
        
        print(f"  Average Win Rate:                {avg_win_rate:.2f}%")
        print(f"  Average Profit Factor:           {avg_profit_factor:.2f}")
    
    print("="*100 + "\n")

def main():
    """Run backtests for multiple years"""
    # Disable verbose logging for cleaner output
    logger.remove()
    logger.add(lambda msg: None, level="CRITICAL")
    
    # Also disable config logging
    BacktestConfig.ENABLE_LOGGING = False
    
    print("\n" + "="*100)
    print("MULTI-YEAR BACKTEST RUNNER")
    print("="*100)
    print(f"Running backtests for: {', '.join([p['name'] for p in BACKTEST_PERIODS])}")
    print(f"Initial Capital per test: ${BacktestConfig.INITIAL_CAPITAL:,.0f}")
    print("="*100)
    
    all_results = []
    
    # Run backtest for each period
    for period in BACKTEST_PERIODS:
        try:
            results = run_backtest_for_period(period)
            all_results.append(results)
        except Exception as e:
            print(f"\n❌ ERROR running backtest for {period['name']}: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({'error': str(e), 'year': period['name']})
    
    # Print comparison table
    print_comparison(all_results)
    
    # Save combined results
    results_dir = Path('backtest/results')
    results_dir.mkdir(parents=True, exist_ok=True)
    
    combined_file = results_dir / 'backtest_multi_year_comparison.json'
    with open(combined_file, 'w') as f:
        json.dump({
            'run_date': datetime.now().isoformat(),
            'periods': BACKTEST_PERIODS,
            'results': all_results
        }, f, indent=2, default=str)
    
    print(f"✓ Combined results saved to {combined_file}\n")

if __name__ == "__main__":
    main()
