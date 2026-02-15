import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_loader import BinanceDataLoader
from datetime import datetime

loader = BinanceDataLoader()

# Test individual timeframe loading
timeframes = ['5m', '15m', '1h', '4h']
print("Testing individual timeframe loading:")  
for tf in timeframes:
    df = loader.load_symbol_data('BTCUSDT', tf, datetime(2025, 5, 1), datetime(2025, 8, 1))
    print(f"  {tf}: {len(df)} candles")

# Test full loading via HistoricalDataFetcher
print("\nTesting via HistoricalDataFetcher:")
from backtest.data_loader import HistoricalDataFetcher
fetcher = HistoricalDataFetcher()
data = fetcher.fetch_all_data(
    symbols=['BTCUSDT'],
    start_date=datetime(2025, 5, 1),
    end_date=datetime(2025, 8, 1),
    timeframes=['5m', '15m', '1h', '4h']
)

print(f"Loaded symbols: {list(data.keys())}")
if 'BTCUSDT' in data:
    print(f"BTCUSDT timeframes: {list(data['BTCUSDT'].keys())}")
    for tf in data['BTCUSDT']:
        print(f"  {tf}: {len(data['BTCUSDT'][tf])} candles")
