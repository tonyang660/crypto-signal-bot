"""
Utility script to check active signals status
Run this to see detailed information about your active signals
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.tracking.signal_tracker import SignalTracker
from src.core.data_manager import DataManager
from loguru import logger

# Configure minimal logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<level>{message}</level>")

def main():
    """Check and display active signals"""
    try:
        tracker = SignalTracker()
        
        # Get summary
        summary = tracker.get_active_signals_summary()
        print(summary)
        
        # If we have active signals, get current prices
        active_symbols = tracker.get_active_symbols()
        if active_symbols:
            print("Fetching current prices...")
            try:
                data_manager = DataManager()
                for symbol in active_symbols:
                    current_price = data_manager.client.get_current_price(symbol)
                    signal = tracker.get_active_signal(symbol)
                    
                    # Calculate distances to TP/SL
                    direction = signal['direction']
                    entry = signal['entry_price']
                    stop = signal['stop_loss']
                    
                    # Distance to stop loss
                    if direction == 'long':
                        sl_distance_pct = ((current_price - stop) / stop) * 100
                        sl_status = "Above" if current_price > stop else "⚠️ BELOW"
                    else:
                        sl_distance_pct = ((stop - current_price) / stop) * 100
                        sl_status = "Below" if current_price < stop else "⚠️ ABOVE"
                    
                    print(f"\n{symbol}: ${current_price:.4f}")
                    print(f"  Stop Loss: {sl_status} SL by {abs(sl_distance_pct):.2f}%")
                    
                    # Check each TP
                    for tp_name in ['tp1', 'tp2', 'tp3']:
                        if not signal.get(f'{tp_name}_hit'):
                            tp_price = signal['take_profits'][tp_name]['price']
                            if direction == 'long':
                                tp_distance_pct = ((tp_price - current_price) / current_price) * 100
                                tp_status = "above" if current_price < tp_price else "✅ HIT"
                            else:
                                tp_distance_pct = ((current_price - tp_price) / current_price) * 100
                                tp_status = "below" if current_price > tp_price else "✅ HIT"
                            
                            if tp_status != "✅ HIT":
                                print(f"  {tp_name.upper()}: {tp_distance_pct:+.2f}% {tp_status} target")
                            else:
                                print(f"  {tp_name.upper()}: {tp_status}")
                
            except Exception as e:
                print(f"\nCouldn't fetch current prices: {e}")
                print("This is normal if the exchange API is unavailable")
        
        else:
            print("No active signals to monitor.")
            print("\nTip: When you have active signals, run this script to check their status!")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
