"""
Download historical klines data from Binance Data Vision
https://data.binance.vision/

This script downloads intraday historical data for backtesting
"""

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import zipfile
import io
from typing import List
import time

class BinanceDataDownloader:
    """Download historical klines from Binance Data Vision"""
    
    BASE_URL = "https://data.binance.vision/data"
    
    def __init__(self):
        self.output_dir = Path("backtest/data_binance")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path("backtest/data_binance/temp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def download_monthly_klines(
        self,
        symbol: str,
        interval: str,
        year: int,
        month: int,
        market_type: str = "spot"
    ) -> pd.DataFrame:
        """
        Download monthly klines data
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Timeframe (e.g., '5m', '15m', '4h')
            year: Year to download
            month: Month to download (1-12)
            market_type: 'spot' or 'futures'
        
        Returns:
            DataFrame with OHLCV data
        """
        # Binance uses different symbol format for some pairs
        # Most are like BTCUSDT, but need to check
        
        month_str = f"{month:02d}"
        filename = f"{symbol}-{interval}-{year}-{month_str}.zip"
        
        if market_type == "futures":
            url = f"{self.BASE_URL}/futures/um/monthly/klines/{symbol}/{interval}/{filename}"
        else:
            url = f"{self.BASE_URL}/spot/monthly/klines/{symbol}/{interval}/{filename}"
        
        logger.debug(f"Attempting: {url}")
        
        try:
            response = requests.get(url, timeout=30)
            
            if response.status_code == 404:
                logger.debug(f"Not found: {year}-{month_str} ({market_type})")
                return None
            
            response.raise_for_status()
            
            # Extract ZIP file
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                csv_filename = f"{symbol}-{interval}-{year}-{month_str}.csv"
                with z.open(csv_filename) as f:
                    df = pd.read_csv(f, header=None)
            
            # Binance klines format:
            # 0: Open time, 1: Open, 2: High, 3: Low, 4: Close, 5: Volume,
            # 6: Close time, 7: Quote asset volume, 8: Number of trades,
            # 9: Taker buy base volume, 10: Taker buy quote volume, 11: Ignore
            
            df.columns = [
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ]
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Select only OHLCV columns
            df = df[['open', 'high', 'low', 'close', 'volume']].copy()
            
            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Filter out invalid timestamps (corrupted data)
            # Valid range: 2000-01-01 to 2099-12-31
            valid_start = pd.Timestamp('2000-01-01')
            valid_end = pd.Timestamp('2099-12-31')
            df = df[(df.index >= valid_start) & (df.index <= valid_end)]
            
            if df.empty:
                logger.debug(f"No valid data after filtering for {symbol} {interval} {year}-{month_str}")
                return None
            
            logger.info(f"✓ Downloaded {len(df)} candles for {symbol} {interval} {year}-{month_str} ({market_type})")
            
            return df
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Error downloading {symbol} {interval} {year}-{month_str}: {e}")
            return None
    
    def download_symbol_interval(
        self,
        symbol: str,
        interval: str,
        start_year: int = 2020,
        end_date: datetime = None,
        market_type: str = "spot"
    ) -> pd.DataFrame:
        """
        Download all available data for a symbol and interval
        
        Args:
            symbol: Trading pair
            interval: Timeframe
            start_year: Year to start downloading from
            end_date: End date (default: today)
            market_type: 'spot' or 'futures'
        
        Returns:
            Combined DataFrame
        """
        if end_date is None:
            end_date = datetime.now()
        
        logger.info(f"Downloading {symbol} {interval} from {start_year} to {end_date.year}...")
        
        all_data = []
        
        # Download year by year, month by month
        current_date = datetime(start_year, 1, 1)
        
        while current_date <= end_date:
            df = self.download_monthly_klines(
                symbol=symbol,
                interval=interval,
                year=current_date.year,
                month=current_date.month,
                market_type=market_type
            )
            
            if df is not None and not df.empty:
                all_data.append(df)
            
            # Move to next month
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)
            
            # Rate limiting - be nice to Binance servers
            time.sleep(0.2)
        
        if not all_data:
            logger.warning(f"No data found for {symbol} {interval}")
            return pd.DataFrame()
        
        # Combine all months
        df_combined = pd.concat(all_data, axis=0)
        df_combined = df_combined.sort_index()
        
        # Remove duplicates (can happen at month boundaries)
        df_combined = df_combined[~df_combined.index.duplicated(keep='first')]
        
        logger.info(f"✓ Total: {len(df_combined)} candles from {df_combined.index.min()} to {df_combined.index.max()}")
        
        return df_combined
    
    def save_to_backtest_format(self, df: pd.DataFrame, symbol: str, interval: str):
        """Save DataFrame in backtest-ready format"""
        if df.empty:
            logger.warning(f"Skipping save - no data for {symbol} {interval}")
            return None
        
        # Use manual date formatting to avoid strftime issues with edge cases
        start_ts = df.index.min()
        end_ts = df.index.max()
        start_date = f"{start_ts.year:04d}{start_ts.month:02d}{start_ts.day:02d}"
        end_date = f"{end_ts.year:04d}{end_ts.month:02d}{end_ts.day:02d}"
        
        filename = f"{symbol}_{interval}_{start_date}_{end_date}.csv"
        filepath = self.output_dir / filename
        
        df.to_csv(filepath)
        logger.info(f"✓ Saved {len(df)} candles to {filepath.name}")
        
        return filepath
    
    def download_all_for_backtesting(
        self,
        symbols: List[str],
        intervals: List[str],
        start_year: int = 2020,
        market_type: str = "spot"
    ):
        """
        Download all required data for backtesting
        
        Args:
            symbols: List of symbols to download
            intervals: List of intervals to download
            start_year: Year to start from
            market_type: 'spot' or 'futures'
        """
        logger.info("="*70)
        logger.info("BINANCE HISTORICAL DATA DOWNLOAD")
        logger.info("="*70)
        logger.info(f"Symbols: {symbols}")
        logger.info(f"Intervals: {intervals}")
        logger.info(f"Start year: {start_year}")
        logger.info(f"Market type: {market_type}")
        logger.info("")
        
        downloaded = []
        
        for symbol in symbols:
            logger.info(f"\n{'='*70}")
            logger.info(f"Processing {symbol}")
            logger.info(f"{'='*70}")
            
            for interval in intervals:
                # Try spot first, then futures if spot fails
                df = self.download_symbol_interval(
                    symbol=symbol,
                    interval=interval,
                    start_year=start_year,
                    market_type=market_type
                )
                
                # If spot market failed and we haven't tried futures yet, try futures
                if df.empty and market_type == "spot":
                    logger.info(f"  Trying futures market for {symbol}...")
                    df = self.download_symbol_interval(
                        symbol=symbol,
                        interval=interval,
                        start_year=start_year,
                        market_type="futures"
                    )
                
                if not df.empty:
                    filepath = self.save_to_backtest_format(df, symbol, interval)
                    if filepath:
                        downloaded.append({
                            'symbol': symbol,
                            'interval': interval,
                            'candles': len(df),
                            'start': df.index.min(),
                            'end': df.index.max(),
                            'file': filepath.name
                        })
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("DOWNLOAD SUMMARY")
        logger.info("="*70)
        
        if downloaded:
            for item in downloaded:
                logger.info(
                    f"{item['symbol']:10} {item['interval']:4} "
                    f"{item['candles']:6} candles  "
                    f"{item['start'].date()} to {item['end'].date()}"
                )
            
            logger.info(f"\n✅ Downloaded {len(downloaded)} datasets")
            logger.info(f"📁 Data saved to: {self.output_dir}")
        else:
            logger.error("❌ No data was downloaded. Check symbols and try 'futures' market type.")
        
        return downloaded


def main():
    """Download historical data from Binance"""
    
    # Configuration - All 38 trading pairs
    SYMBOLS = [
        # Major cryptocurrencies
        'BTCUSDT',
        'ETHUSDT',
        'BNBUSDT',
        'XRPUSDT',
        'SOLUSDT',
        'TRXUSDT',
        'DOGEUSDT',
        'ADAUSDT',
        
        # Popular altcoins
        'LINKUSDT',
        'LTCUSDT',
        'AVAXUSDT',
        'SUIUSDT',      # Newer (2023+)
        'XLMUSDT',
        'TONUSDT',      # Newer (2024+)
        'DOTUSDT',
        'UNIUSDT',
        'APTUSDT',      # Newer (2022+)
        'ALGOUSDT',
        'FILUSDT',
        'VETUSDT',
        'ARBUSDT',      # Newer (2023+)
        
        # Privacy & older coins
        'XMRUSDT',      # May have limited data (delisted from some exchanges)
        'ZECUSDT',
        'HBARUSDT',
        
        # Meme coins
        'SHIBUSDT',
        'PEPEUSDT',     # Newer (2023+)
        
        # DeFi & AI sector
        'AAVEUSDT',
        'TAOUSDT',      # Newer (2024+)
        'RENDERUSDT',   # Newer (2024+)
        'JUPUSDT',      # Newer (2024+)
        
        # Other altcoins
        'CROUSDT',
        'BGBUSDT',      # May have limited availability
        'ONDOUSDT',     # Newer (2024+)
        'POLUSDT',      # Formerly MATIC
        'FLRUSDT',
        'QNTUSDT',      # Newer (2022+)
        'XDCUSDT',      # May have limited availability
        'HYPEUSDT',     # Very new (2025+) - might not be available
    ]
    
    INTERVALS = ['5m', '15m', '1h']  # Strategy required timeframes
    START_YEAR = 2021  # Start from 2021 (adjust to 2020 or 2019 for more history)
    
    # Market type: 'spot' for regular trading, 'futures' for perpetual contracts
    # Try 'spot' first since it has longer history, fallback to 'futures' if needed
    MARKET_TYPE = 'spot'
    
    downloader = BinanceDataDownloader()
    
    logger.info("\n⚠️  NOTE: This will download several GB of data and may take 10-30 minutes")
    logger.info("Press Ctrl+C to cancel\n")
    
    time.sleep(3)
    
    downloader.download_all_for_backtesting(
        symbols=SYMBOLS,
        intervals=INTERVALS,
        start_year=START_YEAR,
        market_type=MARKET_TYPE
    )
    
    logger.info("\n" + "="*70)
    logger.info("✅ DOWNLOAD COMPLETE!")
    logger.info("="*70)
    logger.info("You can now run backtests with this historical data.")
    logger.info("The data will be automatically used when you run backtest scripts.")


if __name__ == "__main__":
    main()
