"""
Check Data Availability in data_binance folder

This script scans the data_binance folder to identify all available symbols,
timeframes, and date ranges. It helps ensure backtests only run with symbols
that have complete data coverage for the requested date range.

Usage:
    python backtest/check_data_availability.py
    
    # Or import as module:
    from backtest.check_data_availability import DataAvailabilityChecker
    checker = DataAvailabilityChecker()
    symbols = checker.get_available_symbols_for_range('2024-01-01', '2024-12-31', ['5m', '15m', '4h'])
"""

import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Set
from collections import defaultdict
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class DataAvailabilityChecker:
    """Check what data is available in the data_binance folder"""
    
    def __init__(self, data_dir: str = None):
        """
        Initialize checker
        
        Args:
            data_dir: Path to data directory (defaults to backtest/data_binance)
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data_binance"
        self.data_dir = Path(data_dir)
        
        if not self.data_dir.exists():
            raise FileNotFoundError(
                f"Data directory not found: {self.data_dir}\n"
                "Run backtest/download_binance_data.py to download historical data"
            )
        
        # Pattern: SYMBOL_TIMEFRAME_STARTDATE_ENDDATE.csv
        # Example: BTCUSDT_15m_20210101_20260131.csv
        self.file_pattern = re.compile(
            r'^([A-Z]+USDT)_([0-9]+[mh])_(\d{8})_(\d{8})\.csv$'
        )
        
        self.data_inventory = None
        self._scan_data_directory()
    
    def _scan_data_directory(self):
        """Scan directory and build inventory of available data"""
        self.data_inventory = defaultdict(lambda: defaultdict(list))
        
        for filepath in self.data_dir.glob("*.csv"):
            match = self.file_pattern.match(filepath.name)
            if not match:
                continue
            
            symbol, timeframe, start_str, end_str = match.groups()
            start_date = datetime.strptime(start_str, "%Y%m%d")
            end_date = datetime.strptime(end_str, "%Y%m%d")
            
            self.data_inventory[symbol][timeframe].append({
                'filepath': filepath,
                'start_date': start_date,
                'end_date': end_date,
                'start_str': start_str,
                'end_str': end_str
            })
        
        # Sort by start date for each symbol/timeframe
        for symbol in self.data_inventory:
            for timeframe in self.data_inventory[symbol]:
                self.data_inventory[symbol][timeframe].sort(
                    key=lambda x: x['start_date']
                )
    
    def get_all_symbols(self) -> List[str]:
        """Get list of all symbols with data"""
        return sorted(self.data_inventory.keys())
    
    def get_all_timeframes(self) -> Set[str]:
        """Get set of all timeframes available"""
        timeframes = set()
        for symbol in self.data_inventory:
            timeframes.update(self.data_inventory[symbol].keys())
        return timeframes
    
    def get_timeframes_for_symbol(self, symbol: str) -> List[str]:
        """Get list of timeframes available for a specific symbol"""
        if symbol not in self.data_inventory:
            return []
        return sorted(self.data_inventory[symbol].keys())
    
    def get_date_range_for_symbol(
        self,
        symbol: str,
        timeframe: str
    ) -> Tuple[datetime, datetime]:
        """
        Get the full date range available for a symbol/timeframe
        
        Returns:
            (earliest_start, latest_end) or (None, None) if not found
        """
        if symbol not in self.data_inventory:
            return None, None
        if timeframe not in self.data_inventory[symbol]:
            return None, None
        
        files = self.data_inventory[symbol][timeframe]
        if not files:
            return None, None
        
        earliest_start = min(f['start_date'] for f in files)
        latest_end = max(f['end_date'] for f in files)
        
        return earliest_start, latest_end
    
    def has_coverage(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> bool:
        """
        Check if a symbol/timeframe has complete coverage for date range
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Interval (e.g., '5m', '15m', '4h')
            start_date: Required start date
            end_date: Required end date
        
        Returns:
            True if complete coverage exists
        """
        data_start, data_end = self.get_date_range_for_symbol(symbol, timeframe)
        
        if data_start is None or data_end is None:
            return False
        
        return data_start <= start_date and data_end >= end_date
    
    def get_available_symbols_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
        timeframes: List[str]
    ) -> List[str]:
        """
        Get symbols that have complete coverage for all timeframes in date range
        
        Args:
            start_date: Required start date
            end_date: Required end date
            timeframes: List of required timeframes
        
        Returns:
            List of symbols with complete coverage
        """
        available = []
        
        for symbol in self.get_all_symbols():
            has_all_timeframes = True
            
            for timeframe in timeframes:
                if not self.has_coverage(symbol, timeframe, start_date, end_date):
                    has_all_timeframes = False
                    break
            
            if has_all_timeframes:
                available.append(symbol)
        
        return available
    
    def get_missing_data_report(
        self,
        symbols: List[str],
        timeframes: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Dict[str, str]]:
        """
        Generate report of missing data for requested symbols/timeframes
        
        Returns:
            Dict[symbol][timeframe] = status message
        """
        report = {}
        
        for symbol in symbols:
            report[symbol] = {}
            
            for timeframe in timeframes:
                if symbol not in self.data_inventory:
                    report[symbol][timeframe] = "Symbol not found"
                    continue
                
                if timeframe not in self.data_inventory[symbol]:
                    report[symbol][timeframe] = "Timeframe not found"
                    continue
                
                data_start, data_end = self.get_date_range_for_symbol(
                    symbol, timeframe
                )
                
                if data_start > start_date:
                    report[symbol][timeframe] = (
                        f"Data starts {data_start.strftime('%Y-%m-%d')} "
                        f"(need {start_date.strftime('%Y-%m-%d')})"
                    )
                elif data_end < end_date:
                    report[symbol][timeframe] = (
                        f"Data ends {data_end.strftime('%Y-%m-%d')} "
                        f"(need {end_date.strftime('%Y-%m-%d')})"
                    )
                else:
                    report[symbol][timeframe] = "✓ Complete"
        
        return report
    
    def print_summary(self):
        """Print a summary of all available data"""
        print("\n" + "="*80)
        print("DATA AVAILABILITY SUMMARY")
        print("="*80)
        
        all_symbols = self.get_all_symbols()
        all_timeframes = sorted(self.get_all_timeframes())
        
        print(f"\nTotal Symbols: {len(all_symbols)}")
        print(f"Available Timeframes: {', '.join(all_timeframes)}")
        
        print("\n" + "-"*80)
        print(f"{'SYMBOL':<12} {'TIMEFRAMES':<20} {'DATE RANGE'}")
        print("-"*80)
        
        for symbol in all_symbols:
            tfs = self.get_timeframes_for_symbol(symbol)
            
            # Get overall date range (use 15m as reference)
            if '15m' in tfs:
                start, end = self.get_date_range_for_symbol(symbol, '15m')
                date_range = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
            else:
                # Use first available timeframe
                start, end = self.get_date_range_for_symbol(symbol, tfs[0])
                date_range = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
            
            print(f"{symbol:<12} {', '.join(tfs):<20} {date_range}")
        
        print("="*80 + "\n")
    
    def print_coverage_report(
        self,
        symbols: List[str],
        timeframes: List[str],
        start_date: datetime,
        end_date: datetime
    ):
        """Print detailed coverage report for requested symbols/timeframes"""
        print("\n" + "="*80)
        print("DATA COVERAGE REPORT")
        print("="*80)
        print(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"Timeframes: {', '.join(timeframes)}")
        print("="*80)
        
        report = self.get_missing_data_report(symbols, timeframes, start_date, end_date)
        
        # Count complete symbols
        complete_symbols = []
        incomplete_symbols = []
        
        for symbol in symbols:
            if symbol in report:
                all_complete = all(
                    report[symbol].get(tf, "").startswith("✓") 
                    for tf in timeframes
                )
                if all_complete:
                    complete_symbols.append(symbol)
                else:
                    incomplete_symbols.append(symbol)
        
        print(f"\n✓ Complete Coverage: {len(complete_symbols)}/{len(symbols)} symbols")
        if complete_symbols:
            print(f"   {', '.join(complete_symbols)}")
        
        if incomplete_symbols:
            print(f"\n✗ Incomplete Coverage: {len(incomplete_symbols)} symbols")
            print("\nDetailed Issues:")
            print("-"*80)
            
            for symbol in incomplete_symbols:
                print(f"\n{symbol}:")
                for timeframe in timeframes:
                    status = report[symbol].get(timeframe, "Unknown")
                    if not status.startswith("✓"):
                        print(f"  {timeframe:<6} {status}")
        
        print("\n" + "="*80 + "\n")


def main():
    """Run data availability checker"""
    # Initialize checker
    checker = DataAvailabilityChecker()
    
    # Print overall summary
    checker.print_summary()
    
    # Example: Check coverage for common backtest configuration
    from backtest.config import BacktestConfig
    
    print("\nChecking coverage for current backtest configuration...")
    
    # Get symbols dynamically
    symbols_for_backtest = BacktestConfig.get_symbols()
    
    checker.print_coverage_report(
        symbols=symbols_for_backtest,
        timeframes=[
            BacktestConfig.HTF_TIMEFRAME,
            BacktestConfig.PRIMARY_TIMEFRAME,
            BacktestConfig.ENTRY_TIMEFRAME
        ],
        start_date=BacktestConfig.START_DATE,
        end_date=BacktestConfig.END_DATE
    )
    
    # Get filtered list of symbols with complete coverage
    available_symbols = checker.get_available_symbols_for_range(
        start_date=BacktestConfig.START_DATE,
        end_date=BacktestConfig.END_DATE,
        timeframes=[
            BacktestConfig.HTF_TIMEFRAME,
            BacktestConfig.PRIMARY_TIMEFRAME,
            BacktestConfig.ENTRY_TIMEFRAME
        ]
    )
    
    print(f"\nRecommended symbols for backtest ({len(available_symbols)} total):")
    print(f"{', '.join(available_symbols)}")


if __name__ == '__main__':
    main()
