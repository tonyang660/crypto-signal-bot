import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_loader import BinanceDataLoader
from datetime import datetime
import pandas as pd

loader = BinanceDataLoader()

# Find the file
pattern = "BTCUSDT_5m_*.csv"
files = list(loader.data_dir.glob(pattern))
print(f"Found files: {[f.name for f in files]}")

filepath = files[0]
print(f"\nLoading: {filepath}")

# Read CSV
df = pd.read_csv(filepath, index_col=0, parse_dates=True)
print(f"Total rows: {len(df)}")
print(f"Index type: {type(df.index)}")
print(f"First index: {df.index[0]}")
print(f"Last index: {df.index[-1]}")

# Apply same filters as the loader
start_date = datetime(2025, 5, 1)
end_date = datetime(2025, 8, 1)

print(f"\nFiltering by: {start_date} to {end_date}")

if start_date is not None:
    df = df[df.index >= start_date]
    print(f"After start filter: {len(df)} rows")

if end_date is not None:
    df = df[df.index <= end_date]
    print(f"After end filter: {len(df)} rows")