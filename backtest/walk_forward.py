"""
Walk-Forward Testing

Splits data into train/test sets and validates if strategy parameters
would have worked on unseen data.

This prevents overfitting - we test on data the "bot" has never seen before.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from datetime import datetime, timedelta
import pandas as pd

from backtest.config import BacktestConfig
from backtest.data_loader import HistoricalDataFetcher
from backtest.engine import BacktestEngine

def split_data(data: dict, split_date: datetime):
    """
    Split data into train and test sets
    
    Args:
        data: Dict[symbol][timeframe] = DataFrame
        split_date: Date to split on
    
    Returns:
        train_data, test_data
    """
    train_data = {}
    test_data = {}
    
    for symbol in data:
        train_data[symbol] = {}
        test_data[symbol] = {}
        
        for timeframe in data[symbol]:
            df = data[symbol][timeframe]
            
            # Debug: print date range and split
            if symbol == "BTCUSDT" and timeframe == "5m":
                logger.debug(f"Data range: {df.index.min()} to {df.index.max()}")
                logger.debug(f"Split date: {split_date} (type: {type(split_date)})")
                logger.debug(f"Index dtype: {df.index.dtype}")
            
            # Split on date
            train_df = df[df.index < split_date].copy()
            test_df = df[df.index >= split_date].copy()
            
            if symbol == "BTCUSDT" and timeframe == "5m":
                logger.debug(f"Train size: {len(train_df)}, Test size: {len(test_df)}")
            
            train_data[symbol][timeframe] = train_df
            test_data[symbol][timeframe] = test_df
    
    return train_data, test_data

def run_walk_forward():
    """
    Run walk-forward test
    
    Process:
    1. Fetch all data
    2. Split into train (70%) and test (30%)
    3. "Optimize" on train data (in our case, just validate)
    4. Test on unseen test data
    5. Compare results
    """
    logger.info("="*80)
    logger.info("WALK-FORWARD TESTING")
    logger.info("="*80)
    logger.info(f"Train/Test Split: {int(BacktestConfig.TRAIN_SPLIT*100)}/{int((1-BacktestConfig.TRAIN_SPLIT)*100)}")
    
    # Fetch data
    logger.info("\nFetching data...")
    fetcher = HistoricalDataFetcher()
    
    data = fetcher.fetch_all_data(
        symbols=BacktestConfig.get_symbols(),
        start_date=BacktestConfig.START_DATE,
        end_date=BacktestConfig.END_DATE,
        timeframes=[
            BacktestConfig.HTF_TIMEFRAME,
            BacktestConfig.PRIMARY_TIMEFRAME,
            BacktestConfig.ENTRY_TIMEFRAME
        ]
    )
    
    if not data:
        logger.error("Failed to fetch data")
        return
    
    # Calculate split date
    start = BacktestConfig.START_DATE
    end = BacktestConfig.END_DATE
    total_days = (end - start).days
    train_days = int(total_days * BacktestConfig.TRAIN_SPLIT)
    split_date = start + timedelta(days=train_days)
    
    # Convert to timezone-aware timestamp matching the data
    split_date = pd.Timestamp(split_date.replace(hour=0, minute=0, second=0, microsecond=0))
    
    logger.info(f"\nData split:")
    logger.info(f"  Train: {start.date()} to {split_date.date()} ({train_days} days)")
    logger.info(f"  Test:  {split_date.date()} to {end.date()} ({total_days - train_days} days)")
    
    # Split data
    train_data, test_data = split_data(data, split_date)
    
    # Run on train data
    logger.info("\n" + "="*80)
    logger.info("TRAINING PERIOD BACKTEST")
    logger.info("="*80)
    
    train_engine = BacktestEngine(train_data)
    train_results = train_engine.run()
    
    if 'error' in train_results:
        logger.error(f"Training backtest failed: {train_results['error']}")
        return
    
    print_summary("TRAINING", train_results)
    
    # Run on test data (unseen data!)
    logger.info("\n" + "="*80)
    logger.info("TESTING PERIOD BACKTEST (UNSEEN DATA)")
    logger.info("="*80)
    
    test_engine = BacktestEngine(test_data)
    test_results = test_engine.run()
    
    if 'error' in test_results:
        logger.error(f"Testing backtest failed: {test_results['error']}")
        return
    
    print_summary("TESTING", test_results)
    
    # Compare results
    logger.info("\n" + "="*80)
    logger.info("WALK-FORWARD VALIDATION")
    logger.info("="*80)
    
    compare_results(train_results, test_results)

def print_summary(label: str, results: dict):
    """Print concise results summary"""
    print(f"\n{label} RESULTS:")
    print(f"  Trades:         {results['total_trades']}")
    print(f"  Win Rate:       {results['win_rate']:.1f}%")
    print(f"  Total Return:   {results['total_return_pct']:+.2f}%")
    print(f"  Profit Factor:  {results['profit_factor']:.2f}")
    print(f"  Expectancy:     ${results['expectancy']:+.2f}")
    print(f"  Max Drawdown:   {results['max_drawdown_pct']:.2f}%")
    print(f"  Sharpe Ratio:   {results['sharpe_ratio']:.2f}")

def compare_results(train: dict, test: dict):
    """
    Compare train vs test results to check for overfitting
    
    Good signs:
    - Test results similar to train results
    - Test results not significantly worse
    
    Bad signs:
    - Test results much worse than train (overfitting)
    - Negative test results when train was positive
    """
    print("\n📊 METRIC COMPARISON (Train vs Test):")
    print(f"  Win Rate:        {train['win_rate']:.1f}% vs {test['win_rate']:.1f}% ({test['win_rate'] - train['win_rate']:+.1f}%)")
    print(f"  Total Return:    {train['total_return_pct']:+.1f}% vs {test['total_return_pct']:+.1f}% ({test['total_return_pct'] - train['total_return_pct']:+.1f}%)")
    print(f"  Profit Factor:   {train['profit_factor']:.2f} vs {test['profit_factor']:.2f} ({test['profit_factor'] - train['profit_factor']:+.2f})")
    print(f"  Expectancy:      ${train['expectancy']:+.2f} vs ${test['expectancy']:+.2f} (${test['expectancy'] - train['expectancy']:+.2f})")
    print(f"  Max Drawdown:    {train['max_drawdown_pct']:.1f}% vs {test['max_drawdown_pct']:.1f}% ({test['max_drawdown_pct'] - train['max_drawdown_pct']:+.1f}%)")
    print(f"  Sharpe Ratio:    {train['sharpe_ratio']:.2f} vs {test['sharpe_ratio']:.2f} ({test['sharpe_ratio'] - train['sharpe_ratio']:+.2f})")
    
    # Verdict
    print("\n🔍 VALIDATION VERDICT:")
    
    issues = []
    
    # Check for major degradation
    if test['total_return_pct'] < train['total_return_pct'] * 0.5:
        issues.append("⚠️  Test returns < 50% of train returns (possible overfitting)")
    
    if test['profit_factor'] < train['profit_factor'] * 0.7:
        issues.append("⚠️  Test profit factor significantly worse")
    
    if test['win_rate'] < train['win_rate'] - 10:
        issues.append("⚠️  Test win rate dropped >10%")
    
    if test['expectancy'] < 0 and train['expectancy'] > 0:
        issues.append("🚨 Test expectancy turned NEGATIVE (major problem)")
    
    if test['max_drawdown_pct'] < train['max_drawdown_pct'] * 1.5:
        issues.append("⚠️  Test drawdown 50% worse than train")
    
    if not issues:
        print("  ✅ PASS - Test results are consistent with train results")
        print("  Strategy shows good generalization to unseen data")
    else:
        print("  ❌ CONCERNS DETECTED:")
        for issue in issues:
            print(f"    {issue}")
        print("\n  Strategy may be overfitted or market regime changed significantly")
    
    # Overall assessment
    test_positive = test['total_return_pct'] > 0 and test['profit_factor'] > 1 and test['expectancy'] > 0
    train_positive = train['total_return_pct'] > 0 and train['profit_factor'] > 1 and train['expectancy'] > 0
    
    print("\n📈 OVERALL ASSESSMENT:")
    if test_positive and train_positive:
        print("  ✅ Strategy is profitable on both train and test data")
        if not issues:
            print("  ✅ Results are consistent - ready for live trading consideration")
        else:
            print("  ⚠️  Some concerns detected - review before live trading")
    elif train_positive and not test_positive:
        print("  🚨 Strategy profitable on train but NOT on test - likely overfit!")
        print("  ❌ DO NOT use for live trading without fixes")
    elif not train_positive:
        print("  ❌ Strategy not profitable even on train data")
        print("  ❌ Needs fundamental improvements before live use")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Walk-forward validation')
    parser.add_argument('--days', type=int, help='Number of days to test (calculates backwards from today)')
    parser.add_argument('--months', type=int, help='Number of months to test (calculates backwards from today)')
    parser.add_argument('--train-pct', type=int, default=70, help='Train percentage (default: 70)')
    args = parser.parse_args()
    
    # Override config dates if specified
    if args.days:
        # Use end of historical data instead of today
        BacktestConfig.END_DATE = datetime(2024, 12, 31)
        BacktestConfig.START_DATE = BacktestConfig.END_DATE - timedelta(days=args.days)
    elif args.months:
        # Use end of historical data instead of today
        BacktestConfig.END_DATE = datetime(2024, 12, 31)
        BacktestConfig.START_DATE = BacktestConfig.END_DATE - timedelta(days=args.months * 30)
    
    if args.train_pct:
        BacktestConfig.TRAIN_SPLIT = args.train_pct / 100
    
    run_walk_forward()
