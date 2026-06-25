import pandas as pd
from loguru import logger
from .market_structure import MarketStructure

class RegimeDetector:
    """
    Detects market regimes (Uptrend, Downtrend, Sideways) to enable adaptive strategy execution.
    - Uptrend: Characterized by higher highs and higher lows. Ideal for trend-following (longs).
    - Downtrend: Characterized by lower highs and lower lows. Ideal for trend-following (shorts).
    - Sideways: Characterized by price action between stable support and resistance. Ideal for mean-reversion.
    """
    
    @staticmethod
    def detect_regime(df: pd.DataFrame, period: int = 20) -> str:
        """
        Detects the market regime using trend structure, EMA slope, ADX, and range compression.

        Sideways must be proven by weak trend strength and compressed range. This keeps
        mean-reversion from taking over during ordinary pullbacks inside real trends.

        Args:
            df (pd.DataFrame): DataFrame with at least 'close' prices and an 'ema_medium' column.
            period (int): The lookback period to determine the trend.

        Returns:
            str: 'Uptrend', 'Downtrend', or 'Sideways'.
        """
        required_columns = {'close', 'high', 'low', 'ema_fast', 'ema_medium', 'ema_slow', 'atr', 'atr_sma'}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            logger.warning(f"Missing columns for regime detection: {', '.join(sorted(missing_columns))}")
            return 'Sideways'

        if len(df) < max(period, 50):
            return 'Sideways'  # Not enough data

        trend_direction = MarketStructure.get_trend_direction(df)

        # Calculate the percentage change of the EMA over the specified period
        ema_values = df['ema_medium'].tail(period)
        start_ema = ema_values.iloc[0]
        end_ema = ema_values.iloc[-1]

        if start_ema == 0:
            return 'Sideways'

        slope_pct = ((end_ema - start_ema) / start_ema) * 100
        adx = df['adx'].iloc[-1] if 'adx' in df.columns else 0
        current_atr = df['atr'].iloc[-1]
        avg_atr = df['atr_sma'].iloc[-1]
        atr_ratio = current_atr / avg_atr if avg_atr else 1.0

        recent = df.tail(50)
        range_pct = (recent['high'].max() - recent['low'].min()) / df['close'].iloc[-1]
        ema_spread_pct = abs(df['ema_fast'].iloc[-1] - df['ema_slow'].iloc[-1]) / df['close'].iloc[-1]

        # Define thresholds for trend determination
        uptrend_threshold = 0.25
        downtrend_threshold = -0.25
        min_trend_adx = 18
        sideways_max_adx = 16
        sideways_max_range_pct = 0.035
        sideways_max_ema_spread_pct = 0.012

        if trend_direction == 'bullish' and (slope_pct > uptrend_threshold or adx >= min_trend_adx):
            return 'Uptrend'
        elif trend_direction == 'bearish' and (slope_pct < downtrend_threshold or adx >= min_trend_adx):
            return 'Downtrend'
        elif (
            trend_direction == 'neutral'
            and abs(slope_pct) < uptrend_threshold
            and adx <= sideways_max_adx
            and range_pct <= sideways_max_range_pct
            and ema_spread_pct <= sideways_max_ema_spread_pct
            and atr_ratio <= 1.15
        ):
            return 'Sideways'
        elif slope_pct > uptrend_threshold:
            return 'Uptrend'
        elif slope_pct < downtrend_threshold:
            return 'Downtrend'

        return 'Sideways'

    @staticmethod
    def get_regime_strategy(regime: str) -> str:
        """
        Determines the appropriate trading strategy for a given market regime.

        Args:
            regime (str): The current market regime ('Uptrend', 'Downtrend', 'Sideways').

        Returns:
            str: 'Trend-Following' or 'Mean-Reversion'.
        """
        if regime in ['Uptrend', 'Downtrend']:
            return 'Trend-Following'
        elif regime == 'Sideways':
            return 'Mean-Reversion'
        else:
            return 'Trend-Following'  # Default strategy

    @staticmethod
    def should_trade_regime(regime: str) -> bool:
        """Compatibility helper for diagnostic/backtest scripts."""
        return regime in ['Uptrend', 'Downtrend', 'Sideways']
    
    @staticmethod
    def check_btc_regime(btc_data: pd.DataFrame) -> dict:
        """
        Check Bitcoin regime to gauge overall market conditions.
        This acts as a macro filter for risk management.
        Returns a dictionary with the regime and corresponding risk adjustments.
        """
        try:
            from .market_structure import MarketStructure
            
            btc_trend = MarketStructure.get_trend_direction(btc_data)
            btc_rsi = btc_data['rsi'].iloc[-1]
            
            # Default adjustments
            adjustments = {
                'score_threshold_adj': 0,
                'position_size_mult': 1.0,
                'max_signals_adj': 0
            }

            # Favorable for longs
            if btc_trend == 'bullish' and 30 < btc_rsi < 70:
                adjustments.update({
                    'score_threshold_adj': -5,  # Be slightly less strict
                    'position_size_mult': 1.1,  # Allow slightly larger size
                    'max_signals_adj': 1        # Allow one extra signal
                })
                return {
                    'regime': 'favorable_long',
                    'reason': f'BTC is bullish (RSI: {btc_rsi:.1f})',
                    **adjustments
                }
            # Favorable for shorts
            elif btc_trend == 'bearish' and 30 < btc_rsi < 70:
                adjustments.update({
                    'score_threshold_adj': -5,
                    'position_size_mult': 1.1,
                    'max_signals_adj': 1
                })
                return {
                    'regime': 'favorable_short',
                    'reason': f'BTC is bearish (RSI: {btc_rsi:.1f})',
                    **adjustments
                }
            # Extended / Overbought
            elif btc_rsi > 75:
                adjustments.update({
                    'score_threshold_adj': 10,  # Be much stricter on new longs
                    'position_size_mult': 0.7,  # Reduce size for new trades
                    'max_signals_adj': -1       # Reduce max signals
                })
                return {
                    'regime': 'extended',
                    'reason': f'BTC is overbought (RSI: {btc_rsi:.1f}), caution on new longs',
                    **adjustments
                }
            # Extended / Oversold
            elif btc_rsi < 25:
                adjustments.update({
                    'score_threshold_adj': 10,  # Be much stricter on new shorts
                    'position_size_mult': 0.7,
                    'max_signals_adj': -1
                })
                return {
                    'regime': 'extended',
                    'reason': f'BTC is oversold (RSI: {btc_rsi:.1f}), caution on new shorts',
                    **adjustments
                }
            # Neutral / Choppy
            else:
                adjustments.update({
                    'score_threshold_adj': 5,   # Be more selective
                    'position_size_mult': 0.9,  # Slightly reduce size
                    'max_signals_adj': 0
                })
                return {
                    'regime': 'neutral',
                    'reason': f'BTC is in a neutral state (RSI: {btc_rsi:.1f})',
                    **adjustments
                }
        
        except Exception as e:
            logger.error(f"Error checking BTC regime: {e}")
            return {
                'regime': 'neutral',
                'reason': 'Error checking BTC regime, defaulting to neutral',
                'score_threshold_adj': 5,
                'position_size_mult': 0.9,
                'max_signals_adj': 0
            }
