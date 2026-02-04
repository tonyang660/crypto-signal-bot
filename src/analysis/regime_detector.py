import pandas as pd
from loguru import logger
from .indicators import Indicators

class RegimeDetector:
    """Detect market regime for adaptive strategy behavior"""
    
    @staticmethod
    def detect_regime(df: pd.DataFrame) -> str:
        """
        Detect market regime
        
        Returns: 'high_volatility', 'low_volatility', 'trending', or 'choppy'
        """
        try:
            atr = df['atr'].iloc[-1]
            atr_avg = df['atr_sma'].iloc[-1]
            
            # Prevent division by zero
            if atr_avg == 0:
                return 'choppy'
            
            atr_ratio = atr / atr_avg
            
            # Calculate ADX for trend strength
            adx = Indicators.calculate_adx(df)
            
            # High Volatility (ATR spike)
            if atr_ratio > 1.5:
                return 'high_volatility'
            
            # Low Volatility (compressed)
            elif atr_ratio < 0.7:
                return 'low_volatility'
            
            # Trending (strong directional movement)
            elif adx > 25:
                return 'trending'
            
            # Choppy (sideways, no clear direction)
            else:
                return 'choppy'
                
        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return 'choppy'
    
    @staticmethod
    def should_trade_regime(regime: str) -> bool:
        """
        Determine if regime is suitable for trading
        
        Skip trading in: low_volatility, choppy
        Trade in: trending, high_volatility (with caution)
        """
        favorable_regimes = ['trending', 'high_volatility']
        return regime in favorable_regimes
    
    @staticmethod
    def get_regime_multipliers(regime: str) -> dict:
        """
        Get strategy parameter adjustments based on regime
        
        Returns dict with ATR multiplier, score threshold, etc.
        """
        multipliers = {
            'trending': {
                'atr_multiplier': 1.5,
                'score_threshold': 70,
                'tp_extension': 1.0  # Allow full TP targets
            },
            'high_volatility': {
                'atr_multiplier': 1.8,  # Wider stops
                'score_threshold': 80,   # Higher quality only
                'tp_extension': 0.8      # Take profits earlier
            },
            'low_volatility': {
                'atr_multiplier': 1.2,
                'score_threshold': 85,
                'tp_extension': 0.6
            },
            'choppy': {
                'atr_multiplier': 1.5,
                'score_threshold': 90,   # Almost never trade
                'tp_extension': 0.5
            }
        }
        
        return multipliers.get(regime, multipliers['choppy'])
    
    @staticmethod
    def check_btc_regime(btc_data: pd.DataFrame) -> dict:
        """
        Check Bitcoin regime to gauge overall market conditions
        
        Since crypto is highly correlated (~0.75-0.85), BTC trend indicates
        market-wide direction. Use this BEFORE creating new signals.
        
        IMPORTANT: Only affects NEW signal creation, never touches existing positions
        
        Args:
            btc_data: BTCUSDT dataframe with indicators (4H timeframe recommended)
        
        Returns:
            dict with:
                - regime: 'favorable', 'neutral', 'extended', 'adverse'
                - score_threshold_adj: points to add to normal threshold
                - position_size_mult: multiplier for position sizing (0.5-1.0)
                - max_signals_adj: adjustment to max concurrent signals
                - reason: human-readable explanation
        """
        try:
            from .market_structure import MarketStructure
            
            # Get BTC trend direction
            btc_trend = MarketStructure.get_trend_direction(btc_data)
            
            # Get BTC RSI (overbought/oversold)
            btc_rsi = btc_data['rsi'].iloc[-1]
            
            # Get BTC momentum
            btc_macd_hist = btc_data['macd_hist'].iloc[-1]
            btc_macd_prev = btc_data['macd_hist'].iloc[-2]
            
            # Get BTC volatility
            btc_atr = btc_data['atr'].iloc[-1]
            btc_atr_avg = btc_data['atr_sma'].iloc[-1]
            btc_atr_ratio = btc_atr / btc_atr_avg if btc_atr_avg > 0 else 1.0
            
            # === FAVORABLE: Strong trend, healthy RSI, momentum building ===
            if btc_trend == 'bullish' and 30 < btc_rsi < 70 and btc_macd_hist > btc_macd_prev:
                return {
                    'regime': 'favorable',
                    'score_threshold_adj': 0,      # No change to threshold
                    'position_size_mult': 1.0,     # Full position size
                    'max_signals_adj': 0,          # No change to max signals
                    'reason': f'BTC bullish trend, RSI {btc_rsi:.1f}, momentum building'
                }
            
            elif btc_trend == 'bearish' and 30 < btc_rsi < 70 and btc_macd_hist < btc_macd_prev:
                return {
                    'regime': 'favorable',
                    'score_threshold_adj': 0,
                    'position_size_mult': 1.0,
                    'max_signals_adj': 0,
                    'reason': f'BTC bearish trend, RSI {btc_rsi:.1f}, momentum building'
                }
            
            # === EXTENDED: BTC overbought/oversold (potential reversal zone) ===
            elif btc_rsi > 70 or btc_rsi < 30:
                return {
                    'regime': 'extended',
                    'score_threshold_adj': 10,     # Require 80+ instead of 70
                    'position_size_mult': 0.7,     # 30% smaller positions
                    'max_signals_adj': -1,         # Max 2 signals instead of 3
                    'reason': f'BTC extended (RSI {btc_rsi:.1f}), reduce new exposure'
                }
            
            # === ADVERSE: BTC trend weakening or reversing ===
            elif btc_trend == 'bullish' and btc_macd_hist < btc_macd_prev and btc_macd_hist < 0:
                return {
                    'regime': 'adverse',
                    'score_threshold_adj': 15,     # Require 85+
                    'position_size_mult': 0.5,     # 50% smaller positions
                    'max_signals_adj': -2,         # Max 1 signal
                    'reason': 'BTC bullish but momentum turning negative'
                }
            
            elif btc_trend == 'bearish' and btc_macd_hist > btc_macd_prev and btc_macd_hist > 0:
                return {
                    'regime': 'adverse',
                    'score_threshold_adj': 15,
                    'position_size_mult': 0.5,
                    'max_signals_adj': -2,
                    'reason': 'BTC bearish but momentum turning positive'
                }
            
            # === HIGH VOLATILITY: BTC experiencing extreme volatility ===
            elif btc_atr_ratio > 2.0:
                return {
                    'regime': 'extended',
                    'score_threshold_adj': 10,
                    'position_size_mult': 0.7,
                    'max_signals_adj': -1,
                    'reason': f'BTC high volatility ({btc_atr_ratio:.2f}x avg), reduce risk'
                }
            
            # === NEUTRAL: BTC in consolidation/sideways ===
            else:
                return {
                    'regime': 'neutral',
                    'score_threshold_adj': 5,      # Slightly more selective (75 threshold)
                    'position_size_mult': 0.9,     # Slightly smaller
                    'max_signals_adj': 0,          # No change
                    'reason': f'BTC {btc_trend}, RSI {btc_rsi:.1f}, neutral conditions'
                }
        
        except Exception as e:
            logger.error(f"Error checking BTC regime: {e}")
            # On error, be conservative
            return {
                'regime': 'neutral',
                'score_threshold_adj': 10,
                'position_size_mult': 0.8,
                'max_signals_adj': -1,
                'reason': 'Error checking BTC regime, defaulting to conservative'
            }