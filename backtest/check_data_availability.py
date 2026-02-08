"""
Check Data Availability for Backtesting

Shows which trading pairs have data available and their date ranges
for each timeframe in backtest/data_binance/
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.config import Config

def check_data_availability():
    """Check available historical data for all trading pairs"""
    
    data_dir = Path("backtest/data_binance")
    
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return
    
    # Get all CSV files
    csv_files = sorted(data_dir.glob("*.csv"))
    
    if not csv_files:
        logger.warning("No data files found in backtest/data_binance/")
        return
    
    logger.info("="*90)
    logger.info("BACKTEST DATA AVAILABILITY CHECK")
    logger.info("="*90)
    
    # Parse all files
    data_info = {}
    timeframes = ['5m', '15m', '1h', '4h']
    
    for file in csv_files:
        filename = file.name
        
        # Parse filename format: SYMBOL_TIMEFRAME_STARTDATE_ENDDATE.csv
        try:
            parts = filename.replace('.csv', '').split('_')
            if len(parts) >= 4:
                symbol = parts[0]
                timeframe = parts[1]
                start_date = parts[2]
                end_date = parts[3]
                
                if symbol not in data_info:
                    data_info[symbol] = {}
                
                # Read file to get actual candle count and date range
                try:
                    df = pd.read_csv(file, parse_dates=['timestamp'])
                    if 'timestamp' in df.columns:
                        actual_start = df['timestamp'].min()
                        actual_end = df['timestamp'].max()
                        candle_count = len(df)
                        
                        data_info[symbol][timeframe] = {
                            'start': actual_start,
                            'end': actual_end,
                            'candles': candle_count,
                            'file': filename
                        }
                except Exception as e:
                    logger.warning(f"Could not read {filename}: {e}")
                    
        except Exception as e:
            logger.debug(f"Could not parse filename {filename}: {e}")
    
    # Display results organized by symbol
    symbols_with_data = sorted(data_info.keys())
    
    logger.info(f"\n📊 Found data for {len(symbols_with_data)} symbols\n")
    
    # Summary table
    print(f"{'SYMBOL':<12} {'5m':<20} {'15m':<20} {'1h':<20} {'4h':<20}")
    print("="*90)
    
    target_start = datetime(2021, 1, 1)
    target_end = datetime(2026, 2, 7)
    
    complete_symbols = []
    partial_symbols = []
    missing_symbols = []
    
    for symbol in symbols_with_data:
        row = f"{symbol:<12}"
        
        has_all_timeframes = True
        coverage_years = []
        
        for tf in timeframes:
            if tf in data_info[symbol]:
                info = data_info[symbol][tf]
                start = info['start']
                end = info['end']
                
                # Calculate years of coverage
                years = (end - start).days / 365.25
                coverage_years.append(years)
                
                # Format: "2021-2024 (3.5y)"
                status = f"{start.year}-{end.year} ({years:.1f}y)"
                row += f" {status:<20}"
            else:
                row += f" {'---':<20}"
                has_all_timeframes = False
        
        print(row)
        
        # Categorize symbol
        if has_all_timeframes and min(coverage_years) >= 3.0:
            complete_symbols.append(symbol)
        elif has_all_timeframes and min(coverage_years) >= 1.0:
            partial_symbols.append(symbol)
        else:
            missing_symbols.append(symbol)
    
    # Summary statistics
    logger.info("\n" + "="*90)
    logger.info("SUMMARY")
    logger.info("="*90)
    
    logger.info(f"\n✅ Complete (3+ years, all timeframes): {len(complete_symbols)} symbols")
    if complete_symbols:
        logger.info(f"   {', '.join(complete_symbols)}")
    
    logger.info(f"\n⚠️  Partial (1-3 years, all timeframes): {len(partial_symbols)} symbols")
    if partial_symbols:
        logger.info(f"   {', '.join(partial_symbols)}")
    
    logger.info(f"\n❌ Missing data: {len(missing_symbols)} symbols")
    if missing_symbols:
        logger.info(f"   {', '.join(missing_symbols)}")
    
    # Check against Config.TRADING_PAIRS
    logger.info("\n" + "="*90)
    logger.info("COMPARISON WITH LIVE CONFIG")
    logger.info("="*90)
    
    config_symbols = [pair for pair in Config.TRADING_PAIRS]
    symbols_in_config_with_data = [s for s in config_symbols if s in symbols_with_data]
    symbols_in_config_without_data = [s for s in config_symbols if s not in symbols_with_data]
    
    logger.info(f"\n📋 Live config has {len(config_symbols)} trading pairs")
    logger.info(f"✅ {len(symbols_in_config_with_data)} have backtest data available")
    logger.info(f"❌ {len(symbols_in_config_without_data)} are missing backtest data")
    
    if symbols_in_config_without_data:
        logger.warning(f"\n⚠️  Missing data for these live trading pairs:")
        for symbol in symbols_in_config_without_data:
            logger.warning(f"   - {symbol}")
        logger.info(f"\n💡 Download missing data with: python backtest/download_binance_data.py")
    
    # Detailed breakdown for each symbol
    logger.info("\n" + "="*90)
    logger.info("DETAILED BREAKDOWN")
    logger.info("="*90)
    
    for symbol in symbols_with_data:
        logger.info(f"\n{symbol}:")
        for tf in sorted(data_info[symbol].keys()):
            info = data_info[symbol][tf]
            logger.info(
                f"  {tf:>4}: {info['start'].strftime('%Y-%m-%d')} to "
                f"{info['end'].strftime('%Y-%m-%d')} | "
                f"{info['candles']:,} candles"
            )
    
    logger.info("\n" + "="*90)

if __name__ == "__main__":
    check_data_availability()
