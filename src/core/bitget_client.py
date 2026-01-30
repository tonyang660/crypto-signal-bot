import ccxt
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import time
from loguru import logger
from .config import Config

class BitGetClient:
    """BitGet API client wrapper using CCXT"""
    
    def __init__(self):
        """Initialize BitGet client"""
        self.exchange = ccxt.bitget({
            'apiKey': Config.BITGET_API_KEY,
            'secret': Config.BITGET_SECRET_KEY,
            'password': Config.BITGET_PASSPHRASE,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # Use perpetual futures (swap)
            }
        })
        
        # Test connection
        try:
            self.exchange.load_markets()
            logger.info(f"✓ Connected to BitGet - {len(self.exchange.markets)} markets loaded")
        except Exception as e:
            logger.error(f"Failed to connect to BitGet: {e}")
            raise
    
    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str, 
        limit: int = 500
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a symbol
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Candle timeframe (e.g., '15m')
            limit: Number of candles to fetch
        
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Format symbol for BitGet
            bitget_symbol = self._format_symbol(symbol)
            
            # Fetch data
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=bitget_symbol,
                timeframe=timeframe,
                limit=limit
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            logger.debug(f"Fetched {len(df)} candles for {symbol} {timeframe}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def get_ticker(self, symbol: str) -> Dict:
        """
        Get current ticker data
        
        Returns dict with: last, bid, ask, high, low, volume
        """
        try:
            bitget_symbol = self._format_symbol(symbol)
            ticker = self.exchange.fetch_ticker(bitget_symbol)
            
            return {
                'symbol': symbol,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'high': ticker['high'],
                'low': ticker['low'],
                'volume': ticker['quoteVolume'],
                'timestamp': datetime.fromtimestamp(ticker['timestamp'] / 1000)
            }
            
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return {}
    
    def get_current_price(self, symbol: str) -> float:
        """Get current market price"""
        ticker = self.get_ticker(symbol)
        return ticker.get('last', 0.0)
    
    def get_market_info(self, symbol: str) -> Dict:
        """
        Get market specifications
        
        Returns: min order size, price precision, quantity precision, etc.
        """
        try:
            bitget_symbol = self._format_symbol(symbol)
            market = self.exchange.market(bitget_symbol)
            
            return {
                'symbol': symbol,
                'min_order_size': market['limits']['amount']['min'],
                'max_order_size': market['limits']['amount']['max'],
                'min_notional': market['limits']['cost']['min'],
                'price_precision': market['precision']['price'],
                'amount_precision': market['precision']['amount'],
                'contract_size': market.get('contractSize', 1),
                'maker_fee': market.get('maker', 0.0002),
                'taker_fee': market.get('taker', 0.0006),
            }
            
        except Exception as e:
            logger.error(f"Error fetching market info for {symbol}: {e}")
            return {}
    
    def get_funding_rate(self, symbol: str) -> float:
        """Get current funding rate for perpetual contract"""
        try:
            bitget_symbol = self._format_symbol(symbol)
            funding = self.exchange.fetch_funding_rate(bitget_symbol)
            return funding.get('fundingRate', 0.0)
            
        except Exception as e:
            logger.warning(f"Could not fetch funding rate for {symbol}: {e}")
            return 0.0
    
    def _format_symbol(self, symbol: str) -> str:
        """
        Convert standard symbol to BitGet format
        
        BTCUSDT -> BTCUSDT (BitGet uses standard format for perpetuals)
        """
        # For BitGet, standard symbols work directly
        # But ensure it's uppercase
        return symbol.upper()
    
    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            self.exchange.fetch_balance()
            logger.info("✓ BitGet API connection test successful")
            return True
        except Exception as e:
            logger.error(f"✗ BitGet API connection test failed: {e}")
            return False


# Quick test function
def test_bitget_client():
    """Test BitGet client functionality"""
    from loguru import logger
    
    client = BitGetClient()
    
    # Test 1: Fetch OHLCV
    print("\n=== Test 1: Fetch OHLCV ===")
    df = client.fetch_ohlcv('BTCUSDT', '15m', limit=10)
    print(df.tail())
    
    # Test 2: Get ticker
    print("\n=== Test 2: Get Ticker ===")
    ticker = client.get_ticker('BTCUSDT')
    print(f"BTC Price: ${ticker['last']:,.2f}")
    
    # Test 3: Get market info
    print("\n=== Test 3: Market Info ===")
    info = client.get_market_info('BTCUSDT')
    print(f"Min order size: {info['min_order_size']}")
    print(f"Price precision: {info['price_precision']}")
    
    # Test 4: Funding rate
    print("\n=== Test 4: Funding Rate ===")
    funding = client.get_funding_rate('BTCUSDT')
    print(f"Funding rate: {funding * 100:.4f}%")


if __name__ == "__main__":
    test_bitget_client()