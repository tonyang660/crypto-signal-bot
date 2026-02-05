#!/usr/bin/env python3
"""Check volume data and averages"""

import pandas as pd
from datetime import datetime, timedelta
from src.core.config import Config
from src.core.bitget_client import BitGetClient
from src.analysis.indicators import Indicators

def check_volume_data():
    """Check volume on 15m timeframe"""
    
    client = BitGetClient()
    symbol = 'BTCUSDT'
    
    print(f"\n{'='*80}")
    print(f"VOLUME ANALYSIS FOR {symbol}")
    print(f"{'='*80}\n")
    
    # Fetch 15m data (last 24 hours = 96 candles)
    print("Fetching 15m data (last 24 hours)...")
    df_15m = client.fetch_ohlcv(symbol, '15m', limit=200)
    
    # Add indicators
    df_15m = Indicators.add_all_indicators(df_15m)
    
    # Get last 24 hours (96 candles)
    last_24h = df_15m.tail(96)
    
    print(f"\n15M TIMEFRAME ANALYSIS:")
    print(f"-" * 80)
    print(f"Total candles in last 24h: {len(last_24h)}")
    print(f"\nVolume Statistics (last 24 hours):")
    print(f"  Average volume: {last_24h['volume'].mean():,.0f}")
    print(f"  Median volume:  {last_24h['volume'].median():,.0f}")
    print(f"  Min volume:     {last_24h['volume'].min():,.0f}")
    print(f"  Max volume:     {last_24h['volume'].max():,.0f}")
    
    print(f"\n15M Last 2 candles (last 30 minutes):")
    print(f"-" * 80)
    for i in range(2, 0, -1):
        candle = df_15m.iloc[-i]
        timestamp = pd.to_datetime(candle['timestamp'], unit='ms')
        volume = candle['volume']
        volume_sma = candle['volume_sma']
        ratio = volume / volume_sma if volume_sma > 0 else 0
        
        print(f"\n  Candle {3-i} ({timestamp.strftime('%Y-%m-%d %H:%M')}):")
        print(f"    Volume:         {volume:,.0f}")
        print(f"    100-period avg: {volume_sma:,.0f}")
        print(f"    Ratio:          {ratio:.2f}x")
    
    # Now check 5m data
    print(f"\n\n{'='*80}")
    print("5M TIMEFRAME ANALYSIS (for comparison):")
    print(f"{'='*80}\n")
    
    df_5m = client.fetch_ohlcv(symbol, '5m', limit=200)
    df_5m = Indicators.add_all_indicators(df_5m)
    
    # Last 24 hours = 288 candles
    last_24h_5m = df_5m.tail(288)
    
    print(f"Total candles in last 24h: {len(last_24h_5m)}")
    print(f"\nVolume Statistics (last 24 hours):")
    print(f"  Average volume: {last_24h_5m['volume'].mean():,.0f}")
    print(f"  Median volume:  {last_24h_5m['volume'].median():,.0f}")
    print(f"  Min volume:     {last_24h_5m['volume'].min():,.0f}")
    print(f"  Max volume:     {last_24h_5m['volume'].max():,.0f}")
    
    print(f"\n5M Last 6 candles (last 30 minutes):")
    print(f"-" * 80)
    for i in range(6, 0, -1):
        candle = df_5m.iloc[-i]
        timestamp = pd.to_datetime(candle['timestamp'], unit='ms')
        volume = candle['volume']
        volume_sma = candle['volume_sma']
        ratio = volume / volume_sma if volume_sma > 0 else 0
        
        print(f"  {timestamp.strftime('%H:%M')}: Vol={volume:>8,.0f} | Avg={volume_sma:>8,.0f} | Ratio={ratio:.2f}x")
    
    # Compare current candle
    print(f"\n\nCURRENT CANDLE COMPARISON:")
    print(f"-" * 80)
    
    current_15m = df_15m.iloc[-1]
    current_5m = df_5m.iloc[-1]
    
    print(f"\n15M Current:")
    print(f"  Volume:      {current_15m['volume']:,.0f}")
    print(f"  100-pd avg:  {current_15m['volume_sma']:,.0f}")
    print(f"  Ratio:       {(current_15m['volume'] / current_15m['volume_sma']):.2f}x")
    
    print(f"\n5M Current:")
    print(f"  Volume:      {current_5m['volume']:,.0f}")
    print(f"  100-pd avg:  {current_5m['volume_sma']:,.0f}")
    print(f"  Ratio:       {(current_5m['volume'] / current_5m['volume_sma']):.2f}x")
    
    print(f"\n{'='*80}\n")
    
    # Recommendation
    print("\nRECOMMENDATION:")
    print("-" * 80)
    print("If 5m shows very low ratios (0.02x) but 15m shows normal ratios (0.5-1.0x),")
    print("then we should use PRIMARY TIMEFRAME (15m) for volume calculation instead of")
    print("ENTRY TIMEFRAME (5m), as 15m better represents actual trading activity.")

if __name__ == '__main__':
    check_volume_data()
