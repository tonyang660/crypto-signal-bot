"""
Check for missing Binance data files for the configured trading pairs.

Usage:
    python backtest/check_missing_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import Config


def check_missing_data_files():
    """Check which configured symbols are missing required timeframe files."""
    symbols = Config.TRADING_PAIRS
    print(f"Configured symbols: {len(symbols)} total")
    print(f"   {', '.join(sorted(symbols))}\n")

    data_dir = Path(__file__).parent / "data_binance"
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return []

    required_timeframes = [
        Config.ENTRY_TIMEFRAME,
        Config.PRIMARY_TIMEFRAME,
        Config.HTF_TIMEFRAME,
    ]

    missing = []
    incomplete = []
    complete = []

    for symbol in sorted(symbols):
        symbol_files = {}
        for tf in required_timeframes:
            pattern = f"{symbol}_{tf}_*.csv"
            files = list(data_dir.glob(pattern))
            symbol_files[tf] = len(files) > 0

        missing_tfs = [tf for tf, exists in symbol_files.items() if not exists]

        if len(missing_tfs) == len(required_timeframes):
            missing.append(symbol)
        elif missing_tfs:
            incomplete.append((symbol, missing_tfs))
        else:
            complete.append(symbol)

    print("COMPLETE DATA (all required timeframes):")
    if complete:
        print(f"   {len(complete)} symbols: {', '.join(complete)}")
    else:
        print("   None")

    print("\nINCOMPLETE DATA (missing some timeframes):")
    if incomplete:
        for symbol, missing_tfs in incomplete:
            print(f"   {symbol}: missing {', '.join(missing_tfs)}")
    else:
        print("   None")

    print("\nMISSING DATA (no files at all):")
    if missing:
        print(f"   {len(missing)} symbols: {', '.join(missing)}")
    else:
        print("   None")

    return missing + [s for s, _ in incomplete]


if __name__ == "__main__":
    symbols_to_download = check_missing_data_files()

    if symbols_to_download:
        print("\nRECOMMENDATION:")
        print(f"   Download data for {len(symbols_to_download)} symbol(s):")
        print(f"   {', '.join(sorted(symbols_to_download))}")
        print("\n   Run: python backtest/download_missing_symbols.py")
