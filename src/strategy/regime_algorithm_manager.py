"""
Market Regime Algorithm Manager

Detects market-wide regime (HV, IQ, CS) using multi-factor analysis of BTC structure.
Each regime has independent scoring, position sizing, TP/SL logic optimized for that market environment.

Regimes:
- HV (High Velocity): Sustained bull markets with strong trends and momentum
- IQ (Inverse Quantitative): Sustained bear markets with distribution patterns
- CS (Chop Suppression): Sideways/choppy conditions with weak trends
"""

import pandas as pd
from enum import Enum
from typing import Dict, Tuple
from loguru import logger
from src.analysis.market_structure import MarketStructure
from src.analysis.indicators import Indicators


class MarketRegime(Enum):
    """Market regime types"""
    HV = "HV"  # Bull market - High Velocity
    IQ = "IQ"  # Bear market - Inverse Quantitative
    CS = "CS"  # Choppy/Sideways - Chop Suppression


class RegimeAlgorithmManager:
    """
    Detects market regime using multi-factor analysis of BTC price action.
    
    Analysis Factors:
    1. Trend Direction - EMA cascade, price position, slope persistence
    2. Trend Strength - ADX values, EMA separation percentage
    3. Momentum Quality - MACD histogram, acceleration, signal crossovers
    4. Volatility Pattern - ATR trending, ratio vs average
    5. Volume Behavior - Volume trends, spikes vs SMA
    6. Market Structure - Swing patterns (higher highs/lower lows vs ranging)
    """
    
    # Configuration constants
    ADX_STRONG_THRESHOLD = 25
    ADX_WEAK_THRESHOLD = 20
    ATR_HIGH_THRESHOLD = 1.3
    ATR_LOW_THRESHOLD = 0.8
    MOMENTUM_LOOKBACK = 5
    VOLUME_SPIKE_THRESHOLD = 1.5
    EMA_SEPARATION_STRONG = 0.03  # 3% separation
    
    @staticmethod
    def detect_market_regime(btc_data: Dict[str, pd.DataFrame]) -> Tuple[MarketRegime, int]:
        """
        Detect current market regime using BTC multi-timeframe analysis.
        
        Args:
            btc_data: Dictionary with 'htf' (4h) and 'primary' (1h) BTC dataframes
            
        Returns:
            Tuple of (regime, confidence_score)
            - regime: MarketRegime enum (HV, IQ, or CS)
            - confidence_score: 0-100 indicating detection confidence
        """
        try:
            htf_df = btc_data.get('htf')  # 4h for broader context
            primary_df = btc_data.get('primary')  # 1h for recent action
            
            if htf_df is None or primary_df is None or len(htf_df) < 50 or len(primary_df) < 50:
                logger.warning("Insufficient BTC data for regime detection, defaulting to CS")
                return MarketRegime.CS, 50
            
            # Analyze all factors
            trend_analysis = RegimeAlgorithmManager._analyze_trend(htf_df, primary_df)
            momentum_analysis = RegimeAlgorithmManager._analyze_momentum(primary_df)
            volatility_analysis = RegimeAlgorithmManager._analyze_volatility(primary_df)
            volume_analysis = RegimeAlgorithmManager._analyze_volume(primary_df)
            structure_analysis = RegimeAlgorithmManager._analyze_structure(htf_df, primary_df)
            
            # Determine regime based on combined factors
            regime, confidence = RegimeAlgorithmManager._classify_regime(
                trend_analysis,
                momentum_analysis,
                volatility_analysis,
                volume_analysis,
                structure_analysis
            )
            
            # Log regime detection
            logger.info(f"🎯 Market Regime Detected: {regime.value} (Confidence: {confidence}%)")
            logger.debug(f"Trend: {trend_analysis}")
            logger.debug(f"Momentum: {momentum_analysis}")
            logger.debug(f"Volatility: {volatility_analysis}")
            logger.debug(f"Volume: {volume_analysis}")
            logger.debug(f"Structure: {structure_analysis}")
            
            return regime, confidence
            
        except Exception as e:
            logger.error(f"Error detecting market regime: {e}")
            return MarketRegime.CS, 50  # Default to safest regime
    
    @staticmethod
    def _analyze_trend(htf_df: pd.DataFrame, primary_df: pd.DataFrame) -> Dict:
        """
        Analyze trend direction and strength.
        
        Returns:
            dict with direction, strength, ema_cascade, slope_persistence
        """
        try:
            # HTF (4h) trend direction
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            
            # Primary (1h) trend for confirmation
            primary_trend = MarketStructure.get_trend_direction(primary_df)
            
            # Calculate trend strength via EMA separation
            price = htf_df['close'].iloc[-1]
            ema_21 = htf_df['ema_21'].iloc[-1]
            ema_50 = htf_df['ema_50'].iloc[-1]
            ema_200 = htf_df['ema_200'].iloc[-1]
            
            # Check for full EMA cascade
            bullish_cascade = (price > ema_21 > ema_50 > ema_200)
            bearish_cascade = (price < ema_21 < ema_50 < ema_200)
            
            # Calculate EMA separation (measure of trend strength)
            ema_separation = 0
            if ema_200 > 0:
                if bullish_cascade:
                    ema_separation = (ema_21 - ema_200) / ema_200
                elif bearish_cascade:
                    ema_separation = (ema_200 - ema_21) / ema_200
            
            # Slope persistence (how many consecutive bars with same slope direction)
            slope_persistence = RegimeAlgorithmManager._calculate_slope_persistence(primary_df, 'ema_21')
            
            # ADX for trend strength
            adx = Indicators.calculate_adx(primary_df)
            
            return {
                'htf_direction': htf_trend,
                'primary_direction': primary_trend,
                'aligned': htf_trend == primary_trend,
                'adx': adx,
                'bullish_cascade': bullish_cascade,
                'bearish_cascade': bearish_cascade,
                'ema_separation': ema_separation,
                'slope_persistence': slope_persistence,
                'strength': 'strong' if adx > RegimeAlgorithmManager.ADX_STRONG_THRESHOLD else 'weak'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trend: {e}")
            return {
                'htf_direction': 'neutral',
                'primary_direction': 'neutral',
                'aligned': False,
                'adx': 15,
                'bullish_cascade': False,
                'bearish_cascade': False,
                'ema_separation': 0,
                'slope_persistence': 0,
                'strength': 'weak'
            }
    
    @staticmethod
    def _analyze_momentum(df: pd.DataFrame) -> Dict:
        """
        Analyze momentum quality and acceleration.
        
        Returns:
            dict with direction, acceleration, histogram_trend, consistency
        """
        try:
            macd = df['macd'].iloc[-1]
            macd_signal = df['macd_signal'].iloc[-1]
            macd_hist = df['macd_hist'].tail(RegimeAlgorithmManager.MOMENTUM_LOOKBACK).values
            
            # Momentum direction
            direction = 'bullish' if macd > macd_signal else 'bearish'
            
            # Check for acceleration (histogram expanding)
            is_accelerating = False
            if len(macd_hist) >= 3:
                if direction == 'bullish':
                    is_accelerating = (macd_hist[-1] > macd_hist[-2] > macd_hist[-3])
                else:
                    is_accelerating = (macd_hist[-1] < macd_hist[-2] < macd_hist[-3])
            
            # Momentum consistency (how many bars in same direction)
            consistency = 0
            for i in range(len(macd_hist) - 1, 0, -1):
                if direction == 'bullish' and macd_hist[i] > 0:
                    consistency += 1
                elif direction == 'bearish' and macd_hist[i] < 0:
                    consistency += 1
                else:
                    break
            
            # Histogram trend (expanding or contracting)
            histogram_trend = 'expanding' if is_accelerating else 'contracting'
            
            # Recent crossover detection
            recent_crossover = False
            if len(df) >= 3:
                prev_macd = df['macd'].iloc[-3]
                prev_signal = df['macd_signal'].iloc[-3]
                if (macd > macd_signal and prev_macd <= prev_signal) or \
                   (macd < macd_signal and prev_macd >= prev_signal):
                    recent_crossover = True
            
            return {
                'direction': direction,
                'is_accelerating': is_accelerating,
                'histogram_trend': histogram_trend,
                'consistency': consistency,
                'recent_crossover': recent_crossover,
                'histogram_value': macd_hist[-1]
            }
            
        except Exception as e:
            logger.error(f"Error analyzing momentum: {e}")
            return {
                'direction': 'neutral',
                'is_accelerating': False,
                'histogram_trend': 'contracting',
                'consistency': 0,
                'recent_crossover': False,
                'histogram_value': 0
            }
    
    @staticmethod
    def _analyze_volatility(df: pd.DataFrame) -> Dict:
        """
        Analyze volatility patterns.
        
        Returns:
            dict with atr_ratio, trend, spike_detected
        """
        try:
            atr = df['atr'].iloc[-1]
            atr_sma = df['atr_sma'].iloc[-1]
            
            if atr_sma == 0:
                atr_ratio = 1.0
            else:
                atr_ratio = atr / atr_sma
            
            # ATR trend (increasing or decreasing volatility)
            atr_values = df['atr'].tail(10).values
            atr_trend = 'increasing' if atr_values[-1] > atr_values[0] else 'decreasing'
            
            # Volatility spike detection
            spike_detected = atr_ratio > RegimeAlgorithmManager.ATR_HIGH_THRESHOLD
            compressed = atr_ratio < RegimeAlgorithmManager.ATR_LOW_THRESHOLD
            
            return {
                'atr_ratio': atr_ratio,
                'trend': atr_trend,
                'spike_detected': spike_detected,
                'compressed': compressed,
                'state': 'high' if spike_detected else ('low' if compressed else 'normal')
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volatility: {e}")
            return {
                'atr_ratio': 1.0,
                'trend': 'stable',
                'spike_detected': False,
                'compressed': False,
                'state': 'normal'
            }
    
    @staticmethod
    def _analyze_volume(df: pd.DataFrame) -> Dict:
        """
        Analyze volume behavior.
        
        Returns:
            dict with volume_ratio, trend, spikes_detected
        """
        try:
            volume = df['volume'].iloc[-1]
            volume_sma = df['volume_sma'].iloc[-1]
            
            if volume_sma == 0:
                volume_ratio = 1.0
            else:
                volume_ratio = volume / volume_sma
            
            # Volume trend
            volume_values = df['volume'].tail(20).values
            volume_trend = 'increasing' if volume_values[-1] > volume_values[0] else 'decreasing'
            
            # Spike detection
            spike_detected = volume_ratio > RegimeAlgorithmManager.VOLUME_SPIKE_THRESHOLD
            
            # Count recent spikes
            recent_spikes = 0
            for i in range(min(10, len(df))):
                vol = df['volume'].iloc[-(i+1)]
                vol_avg = df['volume_sma'].iloc[-(i+1)]
                if vol_avg > 0 and (vol / vol_avg) > RegimeAlgorithmManager.VOLUME_SPIKE_THRESHOLD:
                    recent_spikes += 1
            
            return {
                'volume_ratio': volume_ratio,
                'trend': volume_trend,
                'spike_detected': spike_detected,
                'recent_spikes': recent_spikes
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volume: {e}")
            return {
                'volume_ratio': 1.0,
                'trend': 'stable',
                'spike_detected': False,
                'recent_spikes': 0
            }
    
    @staticmethod
    def _analyze_structure(htf_df: pd.DataFrame, primary_df: pd.DataFrame) -> Dict:
        """
        Analyze market structure patterns.
        
        Returns:
            dict with pattern, swing_direction, breakout_detected
        """
        try:
            # Find recent swing highs and lows on primary timeframe
            swing_high = MarketStructure.find_swing_high(primary_df, lookback=20)
            swing_low = MarketStructure.find_swing_low(primary_df, lookback=20)
            
            current_price = primary_df['close'].iloc[-1]
            
            # Determine if making higher highs/lower lows or ranging
            highs = primary_df['high'].tail(30).values
            lows = primary_df['low'].tail(30).values
            
            # Check for higher highs pattern (uptrend structure)
            higher_highs = 0
            for i in range(len(highs) - 10, len(highs)):
                if highs[i] > max(highs[:i]):
                    higher_highs += 1
            
            # Check for lower lows pattern (downtrend structure)
            lower_lows = 0
            for i in range(len(lows) - 10, len(lows)):
                if lows[i] < min(lows[:i]):
                    lower_lows += 1
            
            # Determine pattern
            if higher_highs >= 3:
                pattern = 'higher_highs'
            elif lower_lows >= 3:
                pattern = 'lower_lows'
            else:
                pattern = 'ranging'
            
            # Check for recent breakout
            breakout_detected = False
            if swing_high and current_price > swing_high:
                breakout_detected = True
            elif swing_low and current_price < swing_low:
                breakout_detected = True
            
            return {
                'pattern': pattern,
                'higher_highs_count': higher_highs,
                'lower_lows_count': lower_lows,
                'breakout_detected': breakout_detected,
                'swing_high': swing_high,
                'swing_low': swing_low
            }
            
        except Exception as e:
            logger.error(f"Error analyzing structure: {e}")
            return {
                'pattern': 'ranging',
                'higher_highs_count': 0,
                'lower_lows_count': 0,
                'breakout_detected': False,
                'swing_high': None,
                'swing_low': None
            }
    
    @staticmethod
    def _calculate_slope_persistence(df: pd.DataFrame, column: str, lookback: int = 10) -> int:
        """
        Calculate how many consecutive bars the slope has been in the same direction.
        
        Returns:
            Number of consecutive bars with same slope direction (positive or negative)
        """
        try:
            values = df[column].tail(lookback).values
            
            if len(values) < 2:
                return 0
            
            # Determine current slope direction
            current_slope = values[-1] - values[-2]
            current_direction = 1 if current_slope > 0 else -1
            
            # Count consecutive bars with same direction
            persistence = 1
            for i in range(len(values) - 2, 0, -1):
                slope = values[i] - values[i-1]
                direction = 1 if slope > 0 else -1
                
                if direction == current_direction:
                    persistence += 1
                else:
                    break
            
            return persistence
            
        except Exception as e:
            logger.error(f"Error calculating slope persistence: {e}")
            return 0
    
    @staticmethod
    def _classify_regime(
        trend: Dict,
        momentum: Dict,
        volatility: Dict,
        volume: Dict,
        structure: Dict
    ) -> Tuple[MarketRegime, int]:
        """
        Classify regime based on combined multi-factor analysis.
        
        Returns:
            Tuple of (regime, confidence_score)
        """
        
        # Scoring system for each regime
        hv_score = 0  # Bull market score
        iq_score = 0  # Bear market score
        cs_score = 0  # Choppy market score
        
        # === TREND ANALYSIS (40 points) ===
        if trend['aligned'] and trend['htf_direction'] == 'bullish':
            hv_score += 20
            if trend['bullish_cascade']:
                hv_score += 10
            if trend['strength'] == 'strong':
                hv_score += 10
        elif trend['aligned'] and trend['htf_direction'] == 'bearish':
            iq_score += 20
            if trend['bearish_cascade']:
                iq_score += 10
            if trend['strength'] == 'strong':
                iq_score += 10
        else:
            # Weak or misaligned trend
            cs_score += 30
        
        # Strong EMA separation indicates conviction
        if trend['ema_separation'] > RegimeAlgorithmManager.EMA_SEPARATION_STRONG:
            if trend['bullish_cascade']:
                hv_score += 10
            elif trend['bearish_cascade']:
                iq_score += 10
        
        # === MOMENTUM ANALYSIS (25 points) ===
        if momentum['is_accelerating']:
            if momentum['direction'] == 'bullish':
                hv_score += 15
            else:
                iq_score += 15
        
        if momentum['consistency'] >= 4:  # Sustained momentum
            if momentum['direction'] == 'bullish':
                hv_score += 10
            else:
                iq_score += 10
        elif momentum['consistency'] <= 1:
            cs_score += 15  # Momentum keeps switching
        
        # === VOLATILITY ANALYSIS (15 points) ===
        if volatility['state'] == 'normal':
            # Normal volatility favors trending regimes
            if trend['strength'] == 'strong':
                if trend['htf_direction'] == 'bullish':
                    hv_score += 15
                elif trend['htf_direction'] == 'bearish':
                    iq_score += 15
        elif volatility['spike_detected']:
            # High volatility can indicate either regime depending on direction
            if momentum['direction'] == 'bearish':
                iq_score += 10  # Volatility spikes often bearish
            else:
                hv_score += 5
        elif volatility['compressed']:
            cs_score += 15  # Low volatility = choppy/consolidation
        
        # === VOLUME ANALYSIS (10 points) ===
        if volume['trend'] == 'increasing':
            if momentum['direction'] == 'bullish':
                hv_score += 10
            else:
                iq_score += 10
        
        if volume['recent_spikes'] >= 3:
            # Multiple volume spikes indicate activity
            if trend['strength'] == 'strong':
                if trend['htf_direction'] == 'bullish':
                    hv_score += 5
                else:
                    iq_score += 5
        
        # === STRUCTURE ANALYSIS (10 points) ===
        if structure['pattern'] == 'higher_highs' and structure['higher_highs_count'] >= 3:
            hv_score += 10
        elif structure['pattern'] == 'lower_lows' and structure['lower_lows_count'] >= 3:
            iq_score += 10
        elif structure['pattern'] == 'ranging':
            cs_score += 20
        
        # === DETERMINE REGIME ===
        scores = {
            MarketRegime.HV: hv_score,
            MarketRegime.IQ: iq_score,
            MarketRegime.CS: cs_score
        }
        
        # Select regime with highest score
        regime = max(scores, key=scores.get)
        confidence = scores[regime]
        
        # If scores are too close, default to CS (safest)
        max_score = max(scores.values())
        second_max = sorted(scores.values(), reverse=True)[1]
        
        if max_score - second_max < 10 and confidence < 50:
            logger.warning(f"Regime scores too close: {scores}, defaulting to CS")
            return MarketRegime.CS, 60
        
        # Ensure confidence is in 0-100 range (normalize if needed)
        confidence = min(100, confidence)
        
        return regime, confidence
