import pandas as pd
from datetime import datetime

# Test 5m file
df_5m = pd.read_csv('backtest/data_binance/BTCUSDT_5m_20210101_20260131.csv', index_col=0, parse_dates=True)
print(f"5m total rows: {len(df_5m)}")
print(f"5m date range: {df_5m.index[0]} to {df_5m.index[-1]}")
print(f"5m index type: {type(df_5m.index[0])}")

# Filter by date
start = datetime(2025, 5, 1)
end = datetime(2025, 8, 1)
filtered = df_5m[(df_5m.index >= start) & (df_5m.index <= end)]
print(f"\n5m filtered (2025-05-01 to 2025-08-01): {len(filtered)} rows")

# Test 1h file
df_1h = pd.read_csv('backtest/data_binance/BTCUSDT_1h_20210101_20260131.csv', index_col=0, parse_dates=True)
print(f"\n1h total rows: {len(df_1h)}")
print(f"1h date range: {df_1h.index[0]} to {df_1h.index[-1]}")
print(f"1h index type: {type(df_1h.index[0])}")

filtered_1h = df_1h[(df_1h.index >= start) & (df_1h.index <= end)]
print(f"1h filtered (2025-05-01 to 2025-08-01): {len(filtered_1h)} rows")
