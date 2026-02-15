"""
Check for missing data files and download them

Usage:
    python backtest/check_missing_data.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import Config
from datetime import datetime

def check_missing_data_files():
    """Check which symbols are missing data files"""
    
    # Get configured symbols
    symbols = Config.TRADING_PAIRS
    print(f"📋 Configured symbols: {len(symbols)} total")
    print(f"   {', '.join(sorted(symbols))}\n")
    
    # Check data directory
    data_dir = Path(__file__).parent / "data_binance"
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return
    
    # Required timeframes
    required_timeframes = ['5m', '15m', '1h', '4h']
    
    # Check each symbol
    missing = []
    incomplete = []
    complete = []
    
    for symbol in sorted(symbols):
        symbol_files = {}
        for tf in required_timeframes:
            # Look for any file matching the pattern
            pattern = f"{symbol}_{tf}_*.csv"
            files = list(data_dir.glob(pattern))
            symbol_files[tf] = len(files) > 0
        
        # Check completeness
        missing_tfs = [tf for tf, exists in symbol_files.items() if not exists]
        
        if len(missing_tfs) == len(required_timeframes):
            missing.append(symbol)
        elif len(missing_tfs) > 0:
            incomplete.append((symbol, missing_tfs))
        else:
            complete.append(symbol)
    
    # Report results
    print("✅ COMPLETE DATA (all timeframes):")
    if complete:
        print(f"   {len(complete)} symbols: {', '.join(complete)}")
    else:
        print("   None")
    
    print(f"\n⚠️  INCOMPLETE DATA (missing some timeframes):")
    if incomplete:
        for symbol, missing_tfs in incomplete:
            print(f"   {symbol}: missing {', '.join(missing_tfs)}")
    else:
        print("   None")
    
    print(f"\n❌ MISSING DATA (no files at all):")
    if missing:
        print(f"   {len(missing)} symbols: {', '.join(missing)}")
    else:
        print("   None")
    
    # Return list of symbols that need downloading
    need_download = missing + [s for s, _ in incomplete]
    return need_download

if __name__ == "__main__":
    symbols_to_download = check_missing_data_files()
    
    if symbols_to_download:
        print(f"\n💡 RECOMMENDATION:")
        print(f"   Download data for {len(symbols_to_download)} symbol(s):")
        print(f"   {', '.join(sorted(symbols_to_download))}")
        print(f"\n   Run: python backtest/download_binance_data.py")
        print(f"   (Make sure to add these symbols to the SYMBOLS list in that script)")
