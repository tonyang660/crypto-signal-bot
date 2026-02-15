"""
Diagnostic tool to analyze why a specific symbol didn't generate trades

Usage:
    python backtest/diagnose_symbol.py BTCUSDT 2025-05-01 2025-08-01
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
import pandas as pd
from backtest.config import BacktestConfig
from backtest.data_loader import HistoricalDataFetcher
from src.strategy.signal_scorer import SignalScorer
from src.strategy.entry_logic import EntryLogic
from src.analysis.indicators import Indicators
from src.analysis.regime_detector import RegimeDetector

def diagnose_symbol(symbol: str, start_date: datetime, end_date: datetime):
    """Analyze signal generation for a specific symbol"""
    print("\n" + "="*80)
    print(f"SIGNAL DIAGNOSTIC: {symbol}")
    print("="*80)
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("="*80 + "\n")
    
    # Fetch data
    print("📥 Fetching data...")
    fetcher = HistoricalDataFetcher()
    data = fetcher.fetch_all_data(
        symbols=[symbol],
        start_date=start_date,
        end_date=end_date,
        timeframes=['5m', '15m', '1h', '4h']
    )
    
    if not data or symbol not in data:
        print(f"❌ Failed to load data for {symbol}")
        return
    
    symbol_data = data[symbol]
    print(f"✅ Data loaded successfully")
    
    # Check what timeframes are available
    available_tfs = list(symbol_data.keys())
    print(f"   Available timeframes: {', '.join(available_tfs)}")
    for tf in available_tfs:
        print(f"   {tf}: {len(symbol_data[tf]):,} candles")
    
    # Map timeframes to expected keys
    if '5m' not in symbol_data or '15m' not in symbol_data or '4h' not in symbol_data:
        print(f"❌ Missing required timeframes (need 5m, 15m, 4h)")
        return
    
    # Initialize components  
    signal_scorer = SignalScorer()
    
    # Track signals
    total_long_checks = 0
    total_short_checks = 0
    signals_by_score = {
        'below_50': 0,
        '50_to_60': 0,
        '60_to_70': 0,
        '70_to_75': 0,
        'above_75': 0
    }
    
    best_signals = []  # Track top signals
    
    # Process each candle (5m timeframe)
    print("\n🔍 Processing candles...")
    df_5m = symbol_data['5m'].reset_index().rename(columns={'index': 'timestamp'})
    df_15m = symbol_data['15m'].reset_index().rename(columns={'index': 'timestamp'})
    df_1h = symbol_data['1h'].reset_index().rename(columns={'index': 'timestamp'})
    df_4h = symbol_data['4h'].reset_index().rename(columns={'index': 'timestamp'})
    
    for idx in range(200, len(df_5m)):  # Start after warm-up period
        current_time = df_5m.iloc[idx]['timestamp']
        
        # Build multi-timeframe data up to current point (no future data)
        data = {
            'entry': df_5m.iloc[:idx+1].copy(),
            'primary': df_15m[df_15m['timestamp'] <= current_time].copy(),
            'htf': df_4h[df_4h['timestamp'] <= current_time].copy()
        }
        
        # Need at least 200 candles for indicators
        if len(data['htf']) < 200 or len(data['primary']) < 200 or len(data['entry']) < 200:
            continue
        
        # Add indicators
        for tf in data:
            data[tf] = Indicators.add_all_indicators(data[tf])
        
        # Check regime
        regime = RegimeDetector.detect_regime(data['primary'])
        if not RegimeDetector.should_trade_regime(regime):
            continue
        
        # Check long entry
        total_long_checks += 1
        long_check = EntryLogic.check_long_entry(data)
        
        if long_check['valid']:
            score, breakdown = signal_scorer.calculate_score_with_breakdown(
                data=data,
                direction='long',
                symbol=symbol
            )
            
            # Categorize
            if score < 50:
                signals_by_score['below_50'] += 1
            elif score < 60:
                signals_by_score['50_to_60'] += 1
            elif score < 70:
                signals_by_score['60_to_70'] += 1
            elif score < 75:
                signals_by_score['70_to_75'] += 1
            else:
                signals_by_score['above_75'] += 1
            
            # Track best signals
            best_signals.append({
                'time': current_time,
                'direction': 'LONG',
                'score': score,
                'breakdown': breakdown,
                'reason': long_check['reason']
            })
        
        # Check short entry
        total_short_checks += 1
        short_check = EntryLogic.check_short_entry(data)
        
        if short_check['valid']:
            score, breakdown = signal_scorer.calculate_score_with_breakdown(
                data=data,
                direction='short',
                symbol=symbol
            )
            
            # Categorize
            if score < 50:
                signals_by_score['below_50'] += 1
            elif score < 60:
                signals_by_score['50_to_60'] += 1
            elif score < 70:
                signals_by_score['60_to_70'] += 1
            elif score < 75:
                signals_by_score['70_to_75'] += 1
            else:
                signals_by_score['above_75'] += 1
            
            # Track best signals
            best_signals.append({
                'time': current_time,
                'direction': 'SHORT',
                'score': score,
                'breakdown': breakdown,
                'reason': short_check['reason']
            })
    
    # Sort and keep top 10
    best_signals.sort(key=lambda x: x['score'], reverse=True)
    best_signals = best_signals[:10]
    
    total_signals_generated = sum(signals_by_score.values())
    
    # Print results
    print(f"\n📊 SIGNAL ANALYSIS:")
    print(f"  Entry Checks: {total_long_checks:,} long + {total_short_checks:,} short")
    print(f"  Valid Signals Generated: {total_signals_generated}")
    print(f"\n  Score Distribution:")
    print(f"    Below 50:    {signals_by_score['below_50']:4} ({signals_by_score['below_50']/max(total_signals_generated,1)*100:.1f}%)")
    print(f"    50-60:       {signals_by_score['50_to_60']:4} ({signals_by_score['50_to_60']/max(total_signals_generated,1)*100:.1f}%)")
    print(f"    60-70:       {signals_by_score['60_to_70']:4} ({signals_by_score['60_to_70']/max(total_signals_generated,1)*100:.1f}%)")
    print(f"    70-75:       {signals_by_score['70_to_75']:4} ({signals_by_score['70_to_75']/max(total_signals_generated,1)*100:.1f}%) ⚠️  Just below threshold")
    print(f"    Above 75:    {signals_by_score['above_75']:4} ({signals_by_score['above_75']/max(total_signals_generated,1)*100:.1f}%) ✅ Would trade")
    
    if signals_by_score['above_75'] == 0:
        print(f"\n❌ NO SIGNALS ABOVE 75-POINT THRESHOLD")
        print(f"   This is why {symbol} had no trades in the backtest")
    
    if best_signals:
        print(f"\n🏆 TOP 10 SIGNALS (Highest Scores):")
        print("="*80)
        for i, sig in enumerate(best_signals, 1):
            bd = sig['breakdown']
            print(f"\n#{i}. {sig['direction']:5} | Score: {sig['score']}/100 | {sig['time']}")
            print(f"    Reason: {sig['reason']}")
            print(f"    HTF Alignment:  {bd.get('htf_score', 0)}/25  - {bd.get('htf_reason', 'N/A')}")
            print(f"    Momentum:       {bd.get('momentum_score', 0)}/20  - {bd.get('momentum_reason', 'N/A')}")
            print(f"    RSI:            {bd.get('rsi_score', 0)}/12  - {bd.get('rsi_reason', 'N/A')}")
            print(f"    Entry:          {bd.get('entry_score', 0)}/20  - {bd.get('entry_reason', 'N/A')}")
            print(f"    BOS:            {bd.get('bos_score', 0)}/13  - {bd.get('bos_reason', 'N/A')}")
            print(f"    Volatility:     {bd.get('volatility_score', 0)}/10  - {bd.get('volatility_reason', 'N/A')}")
            print(f"    Volume:         {bd.get('volume_score', 0)}/8   - {bd.get('volume_reason', 'N/A')}")
    
    print("\n" + "="*80)
    
    # Analysis recommendations
    print("\n💡 RECOMMENDATIONS:")
    if signals_by_score['above_75'] == 0:
        if signals_by_score['70_to_75'] > 0:
            print("  • Many signals scored 70-75 (just below threshold)")
            print("  • Consider lowering SIGNAL_QUALITY_THRESHOLD to 70 in backtest config")
            print("  • Or investigate why HTF/Momentum scores are weak for this symbol")
        elif total_signals_generated == 0:
            print("  • No signals generated at all - check data quality")
            print("  • Verify EMAs, MACD, and market structure detection")
        else:
            print("  • Signals are generated but quality is consistently low")
            print("  • Check the top signals above to see which components are weak")
            print("  • HTF Alignment and Momentum typically contribute most points")
    
    print("\n")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python backtest/diagnose_symbol.py SYMBOL START_DATE END_DATE")
        print("Example: python backtest/diagnose_symbol.py BTCUSDT 2025-05-01 2025-08-01")
        sys.exit(1)
    
    symbol = sys.argv[1]
    start_str = sys.argv[2]
    end_str = sys.argv[3]
    
    start_date = datetime.strptime(start_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_str, '%Y-%m-%d')
    
    diagnose_symbol(symbol, start_date, end_date)
