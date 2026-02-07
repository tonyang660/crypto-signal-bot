"""
Regime-Specific Signal Scorers

Each market regime (HV, IQ, CS) has custom scoring weights and logic
optimized for that specific market environment.

- HVScorer: Bull market optimized (ride trends, aggressive TPs)
- IQScorer: Bear market optimized (selective shorts, conservative TPs)
- CSScorer: Choppy market optimized (scalp mode, tight stops)
"""

import pandas as pd
from typing import Dict, Tuple
from abc import ABC, abstractmethod
from loguru import logger
from src.analysis.market_structure import MarketStructure


class RegimeScorer(ABC):
    """Abstract base class for regime-specific scorers"""
    
    @staticmethod
    @abstractmethod
    def calculate_score(
        data: Dict[str, pd.DataFrame],
        direction: str
    ) -> Tuple[int, Dict]:
        """
        Calculate signal quality score for this regime.
        
        Args:
            data: Multi-timeframe data dict with 'htf', 'primary', 'entry'
            direction: 'long' or 'short'
            
        Returns:
            Tuple of (score, breakdown_dict)
        """
        pass
    
    @staticmethod
    @abstractmethod
    def get_config() -> Dict:
        """
        Get regime-specific configuration.
        
        Returns:
            Dict with threshold, tp_ratios, sl_multiplier, position_multiplier
        """
        pass


class HVScorer(RegimeScorer):
    """
    Bull Market Scorer - High Velocity (HV)
    
    Optimized for sustained bull markets with strong trends.
    
    Component Weights:
    - HTF Alignment: 30 points (critical - ride the bull)
    - Momentum: 20 points (acceleration matters in bulls)
    - RSI: 15 points (pullbacks to 45-55 are reload zones)
    - Entry Location: 15 points (buy support at EMA21)
    - Break Structure: 15 points (breakouts above resistance)
    - Volatility & Volume: 5 points (confirmation only)
    
    Strategy:
    - Let winners run with aggressive TP targets
    - Tighter stops (trend is your friend)
    - Full position sizing
    - Entry threshold: 75 (allow good setups)
    """
    
    @staticmethod
    def calculate_score(
        data: Dict[str, pd.DataFrame],
        direction: str
    ) -> Tuple[int, Dict]:
        """Calculate HV regime score"""
        
        try:
            score = 0
            breakdown = {}
            
            htf_df = data['htf']
            primary_df = data['primary']
            entry_df = data['entry']
            
            # === 1. HTF ALIGNMENT (30 points) ===
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            htf_points = 0
            
            if direction == 'long':
                if htf_trend == 'bullish':
                    # Check cascade strength
                    price = htf_df['close'].iloc[-1]
                    ema_21 = htf_df['ema_21'].iloc[-1]
                    ema_50 = htf_df['ema_50'].iloc[-1]
                    ema_200 = htf_df['ema_200'].iloc[-1]
                    
                    if price > ema_21 > ema_50 > ema_200:
                        # Perfect bullish cascade
                        htf_points = 30
                    elif price > ema_21 > ema_50:
                        # Good bullish alignment
                        htf_points = 22
                    elif price > ema_21:
                        # Basic bullish
                        htf_points = 15
                    else:
                        htf_points = 5
                elif htf_trend == 'neutral':
                    htf_points = 10
                # Bearish HTF = 0 points (don't fight the trend)
                
            elif direction == 'short':
                # In HV (bull) regime, shorts are counter-trend - heavily penalized
                if htf_trend == 'bearish':
                    htf_points = 15  # Max 15 for counter-trend shorts
                elif htf_trend == 'neutral':
                    htf_points = 8
                # Bullish HTF short = 0
            
            score += htf_points
            breakdown['htf_alignment'] = htf_points
            
            # === 2. MOMENTUM (20 points) ===
            macd_hist = primary_df['macd_hist'].tail(5).values
            momentum_points = 0
            
            if len(macd_hist) >= 3:
                if direction == 'long':
                    # Accelerating bullish momentum
                    if (macd_hist[-1] > macd_hist[-2] > macd_hist[-3] and 
                        macd_hist[-1] > 0):
                        momentum_points = 20
                    elif macd_hist[-1] > macd_hist[-2] and macd_hist[-1] > 0:
                        momentum_points = 14
                    elif macd_hist[-1] > 0:
                        momentum_points = 8
                    
                elif direction == 'short':
                    # Short momentum (counter-trend in HV)
                    if (macd_hist[-1] < macd_hist[-2] < macd_hist[-3] and 
                        macd_hist[-1] < 0):
                        momentum_points = 12  # Max 12 for counter-trend
                    elif macd_hist[-1] < macd_hist[-2] and macd_hist[-1] < 0:
                        momentum_points = 7
            
            score += momentum_points
            breakdown['momentum'] = momentum_points
            
            # === 3. RSI (15 points) ===
            # In bull markets, RSI runs hot - accept 40-70 range
            rsi = primary_df['rsi'].iloc[-1]
            rsi_points = 0
            
            if direction == 'long':
                if 45 <= rsi <= 55:
                    # Perfect reload zone
                    rsi_points = 15
                elif 40 <= rsi <= 60:
                    # Good range
                    rsi_points = 12
                elif 35 <= rsi <= 70:
                    # Acceptable
                    rsi_points = 8
                elif rsi < 35:
                    # Oversold - caution
                    rsi_points = 5
                elif rsi > 70:
                    # Overbought - risk
                    rsi_points = 3
                    
            elif direction == 'short':
                if 55 <= rsi <= 65:
                    rsi_points = 10
                elif 50 <= rsi <= 70:
                    rsi_points = 7
                elif rsi < 50:
                    rsi_points = 2
            
            score += rsi_points
            breakdown['rsi'] = rsi_points
            
            # === 4. ENTRY LOCATION (15 points) ===
            price = primary_df['close'].iloc[-1]
            ema_21 = primary_df['ema_21'].iloc[-1]
            atr = primary_df['atr'].iloc[-1]
            
            entry_points = 0
            if atr > 0 and ema_21 > 0:
                distance = abs(price - ema_21) / atr
                
                if direction == 'long':
                    # Buying near EMA21 support
                    if distance < 0.25:
                        entry_points = 15
                    elif distance < 0.5:
                        entry_points = 10
                    elif distance < 0.8:
                        entry_points = 6
                    elif distance < 1.2:
                        entry_points = 3
                        
                elif direction == 'short':
                    # Shorting near EMA21 resistance
                    if distance < 0.25:
                        entry_points = 12
                    elif distance < 0.5:
                        entry_points = 8
                    elif distance < 0.8:
                        entry_points = 4
            
            score += entry_points
            breakdown['entry_location'] = entry_points
            
            # === 5. BREAK STRUCTURE (15 points) ===
            bos_detected = MarketStructure.detect_break_of_structure(
                primary_df, 
                direction, 
                lookback=15  # Shorter lookback for intraday
            )
            
            structure_points = 0
            if bos_detected:
                if direction == 'long':
                    # Bullish breakout highly valued in HV
                    structure_points = 15
                elif direction == 'short':
                    # Bearish breakdown less valued (counter-trend)
                    structure_points = 8
            else:
                # No clear breakout
                structure_points = 3
            
            score += structure_points
            breakdown['break_structure'] = structure_points
            
            # === 6. VOLATILITY & VOLUME (5 points) ===
            atr_sma = primary_df['atr_sma'].iloc[-1]
            volume = primary_df['volume'].iloc[-1]
            volume_sma = primary_df['volume_sma'].iloc[-1]
            
            vol_points = 0
            
            # Check volatility is normal (not extreme)
            if atr_sma > 0:
                atr_ratio = atr / atr_sma
                if 0.8 <= atr_ratio <= 1.5:
                    vol_points += 3
                elif 0.6 <= atr_ratio <= 2.0:
                    vol_points += 1
            
            # Check volume confirmation
            if volume_sma > 0:
                volume_ratio = volume / volume_sma
                if volume_ratio > 1.1:
                    vol_points += 2
                elif volume_ratio > 0.8:
                    vol_points += 1
            
            score += vol_points
            breakdown['volatility_volume'] = vol_points
            
            # Final score
            breakdown['total'] = score
            
            return score, breakdown
            
        except Exception as e:
            logger.error(f"Error calculating HV score: {e}")
            return 0, {'error': str(e)}
    
    @staticmethod
    def get_config() -> Dict:
        """Get HV regime configuration"""
        return {
            'threshold': 75,  # Entry threshold
            'tp_ratios': [2.0, 3.5, 5.0],  # Aggressive - let winners run
            'tp_percentages': [50, 30, 20],  # Standard partial closes
            'sl_multiplier': 1.8,  # Tighter stops (trend is your friend)
            'position_multiplier': 1.0,  # Full size
            'description': 'Bull Market - High Velocity'
        }


class IQScorer(RegimeScorer):
    """
    Bear Market Scorer - Inverse Quantitative (IQ)
    
    Optimized for sustained bear markets with distribution patterns.
    
    Component Weights:
    - HTF Alignment: 30 points (critical - short into weakness)
    - Momentum: 20 points (selling pressure acceleration)
    - RSI: 15 points (rallies to 45-55 are short entries)
    - Entry Location: 15 points (short resistance at EMA21)
    - Break Structure: 15 points (breakdowns below support)
    - Volatility & Volume: 5 points (spikes on dumps)
    
    Strategy:
    - Take profits faster (bear rallies are swift)
    - Wider stops (volatility spikes common)
    - Reduced position sizing (risk management)
    - Entry threshold: 80 (very selective)
    """
    
    @staticmethod
    def calculate_score(
        data: Dict[str, pd.DataFrame],
        direction: str
    ) -> Tuple[int, Dict]:
        """Calculate IQ regime score"""
        
        try:
            score = 0
            breakdown = {}
            
            htf_df = data['htf']
            primary_df = data['primary']
            entry_df = data['entry']
            
            # === 1. HTF ALIGNMENT (30 points) ===
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            htf_points = 0
            
            if direction == 'short':
                if htf_trend == 'bearish':
                    # Check cascade strength
                    price = htf_df['close'].iloc[-1]
                    ema_21 = htf_df['ema_21'].iloc[-1]
                    ema_50 = htf_df['ema_50'].iloc[-1]
                    ema_200 = htf_df['ema_200'].iloc[-1]
                    
                    if price < ema_21 < ema_50 < ema_200:
                        # Perfect bearish cascade
                        htf_points = 30
                    elif price < ema_21 < ema_50:
                        # Good bearish alignment
                        htf_points = 22
                    elif price < ema_21:
                        # Basic bearish
                        htf_points = 15
                    else:
                        htf_points = 5
                elif htf_trend == 'neutral':
                    htf_points = 10
                # Bullish HTF = 0 points
                
            elif direction == 'long':
                # In IQ (bear) regime, longs are counter-trend - heavily penalized
                if htf_trend == 'bullish':
                    htf_points = 15  # Max 15 for counter-trend longs
                elif htf_trend == 'neutral':
                    htf_points = 8
                # Bearish HTF long = 0
            
            score += htf_points
            breakdown['htf_alignment'] = htf_points
            
            # === 2. MOMENTUM (20 points) ===
            macd_hist = primary_df['macd_hist'].tail(5).values
            momentum_points = 0
            
            if len(macd_hist) >= 3:
                if direction == 'short':
                    # Accelerating bearish momentum
                    if (macd_hist[-1] < macd_hist[-2] < macd_hist[-3] and 
                        macd_hist[-1] < 0):
                        momentum_points = 20
                    elif macd_hist[-1] < macd_hist[-2] and macd_hist[-1] < 0:
                        momentum_points = 14
                    elif macd_hist[-1] < 0:
                        momentum_points = 8
                    
                elif direction == 'long':
                    # Long momentum (counter-trend in IQ)
                    if (macd_hist[-1] > macd_hist[-2] > macd_hist[-3] and 
                        macd_hist[-1] > 0):
                        momentum_points = 12  # Max 12 for counter-trend
                    elif macd_hist[-1] > macd_hist[-2] and macd_hist[-1] > 0:
                        momentum_points = 7
            
            score += momentum_points
            breakdown['momentum'] = momentum_points
            
            # === 3. RSI (15 points) ===
            # In bear markets, rallies are selling opportunities
            rsi = primary_df['rsi'].iloc[-1]
            rsi_points = 0
            
            if direction == 'short':
                if 45 <= rsi <= 55:
                    # Perfect short entry zone
                    rsi_points = 15
                elif 40 <= rsi <= 60:
                    # Good range
                    rsi_points = 12
                elif 30 <= rsi <= 65:
                    # Acceptable
                    rsi_points = 8
                elif rsi > 65:
                    # Overbought rally - good short
                    rsi_points = 10
                elif rsi < 30:
                    # Oversold - wait for bounce
                    rsi_points = 3
                    
            elif direction == 'long':
                if 30 <= rsi <= 40:
                    rsi_points = 10
                elif 25 <= rsi <= 45:
                    rsi_points = 7
                elif rsi > 50:
                    rsi_points = 2
            
            score += rsi_points
            breakdown['rsi'] = rsi_points
            
            # === 4. ENTRY LOCATION (15 points) ===
            price = primary_df['close'].iloc[-1]
            ema_21 = primary_df['ema_21'].iloc[-1]
            atr = primary_df['atr'].iloc[-1]
            
            entry_points = 0
            if atr > 0 and ema_21 > 0:
                distance = abs(price - ema_21) / atr
                
                if direction == 'short':
                    # Shorting near EMA21 resistance from above
                    if distance < 0.25:
                        entry_points = 15
                    elif distance < 0.5:
                        entry_points = 10
                    elif distance < 0.8:
                        entry_points = 6
                    elif distance < 1.2:
                        entry_points = 3
                        
                elif direction == 'long':
                    # Buying dips (counter-trend)
                    if distance < 0.25:
                        entry_points = 12
                    elif distance < 0.5:
                        entry_points = 8
                    elif distance < 0.8:
                        entry_points = 4
            
            score += entry_points
            breakdown['entry_location'] = entry_points
            
            # === 5. BREAK STRUCTURE (15 points) ===
            bos_detected = MarketStructure.detect_break_of_structure(
                primary_df, 
                direction, 
                lookback=15
            )
            
            structure_points = 0
            if bos_detected:
                if direction == 'short':
                    # Bearish breakdown highly valued in IQ
                    structure_points = 15
                elif direction == 'long':
                    # Bullish breakout less valued (counter-trend)
                    structure_points = 8
            else:
                structure_points = 3
            
            score += structure_points
            breakdown['break_structure'] = structure_points
            
            # === 6. VOLATILITY & VOLUME (5 points) ===
            atr_sma = primary_df['atr_sma'].iloc[-1]
            volume = primary_df['volume'].iloc[-1]
            volume_sma = primary_df['volume_sma'].iloc[-1]
            
            vol_points = 0
            
            # Higher volatility tolerance in bear markets
            if atr_sma > 0:
                atr_ratio = atr / atr_sma
                if 1.0 <= atr_ratio <= 2.0:
                    vol_points += 3  # Accept higher vol
                elif 0.8 <= atr_ratio <= 2.5:
                    vol_points += 2
            
            # Volume spikes on dumps are confirmatory
            if volume_sma > 0:
                volume_ratio = volume / volume_sma
                if direction == 'short' and volume_ratio > 1.3:
                    vol_points += 2  # Strong volume on breakdown
                elif volume_ratio > 1.0:
                    vol_points += 1
            
            score += vol_points
            breakdown['volatility_volume'] = vol_points
            
            breakdown['total'] = score
            
            return score, breakdown
            
        except Exception as e:
            logger.error(f"Error calculating IQ score: {e}")
            return 0, {'error': str(e)}
    
    @staticmethod
    def get_config() -> Dict:
        """Get IQ regime configuration"""
        return {
            'threshold': 80,  # Very selective
            'tp_ratios': [1.5, 2.5, 4.0],  # Conservative - take profits fast
            'tp_percentages': [50, 30, 20],
            'sl_multiplier': 2.0,  # Wider stops (expect volatility)
            'position_multiplier': 0.8,  # Reduced exposure
            'description': 'Bear Market - Inverse Quantitative'
        }


class CSScorer(RegimeScorer):
    """
    Choppy Market Scorer - Chop Suppression (CS)
    
    Optimized for sideways/choppy conditions with weak trends.
    
    Component Weights:
    - HTF Alignment: 30 points (relaxed - range boundaries)
    - Momentum: 20 points (requires clear shift)
    - RSI: 15 points (extremes prioritized - mean reversion)
    - Entry Location: 15 points (EMA bounces or range edges)
    - Break Structure: 15 points (breakouts from consolidation)
    - Volatility & Volume: 5 points (low vol + breakout volume)
    
    Strategy:
    - Scalp mode - take profits quickly
    - Tightest stops - exit bad trades fast
    - Minimal position sizing
    - Entry threshold: 85 (highly selective - avoid chop)
    """
    
    @staticmethod
    def calculate_score(
        data: Dict[str, pd.DataFrame],
        direction: str
    ) -> Tuple[int, Dict]:
        """Calculate CS regime score"""
        
        try:
            score = 0
            breakdown = {}
            
            htf_df = data['htf']
            primary_df = data['primary']
            entry_df = data['entry']
            
            # === 1. HTF ALIGNMENT (30 points) ===
            # In choppy markets, HTF less critical - focus on range structure
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            price = htf_df['close'].iloc[-1]
            ema_21 = htf_df['ema_21'].iloc[-1]
            ema_50 = htf_df['ema_50'].iloc[-1]
            
            htf_points = 0
            
            # Reward proximity to range boundaries
            if direction == 'long':
                if htf_trend == 'neutral':
                    # Neutral is good for range trading
                    if price < ema_21:
                        htf_points = 25  # At lower range boundary
                    elif price < ema_50:
                        htf_points = 18
                    else:
                        htf_points = 12
                elif htf_trend == 'bullish':
                    htf_points = 15
                elif htf_trend == 'bearish':
                    htf_points = 8
                    
            elif direction == 'short':
                if htf_trend == 'neutral':
                    if price > ema_21:
                        htf_points = 25  # At upper range boundary
                    elif price > ema_50:
                        htf_points = 18
                    else:
                        htf_points = 12
                elif htf_trend == 'bearish':
                    htf_points = 15
                elif htf_trend == 'bullish':
                    htf_points = 8
            
            score += htf_points
            breakdown['htf_alignment'] = htf_points
            
            # === 2. MOMENTUM (20 points) ===
            # Requires clear momentum shift, not just positive/negative
            macd = primary_df['macd'].iloc[-1]
            macd_signal = primary_df['macd_signal'].iloc[-1]
            macd_hist = primary_df['macd_hist'].tail(5).values
            
            momentum_points = 0
            
            # Check for recent crossover (momentum shift)
            recent_crossover = False
            if len(primary_df) >= 3:
                prev_macd = primary_df['macd'].iloc[-3]
                prev_signal = primary_df['macd_signal'].iloc[-3]
                curr_macd = macd
                curr_signal = macd_signal
                
                if direction == 'long':
                    if curr_macd > curr_signal and prev_macd <= prev_signal:
                        recent_crossover = True
                elif direction == 'short':
                    if curr_macd < curr_signal and prev_macd >= prev_signal:
                        recent_crossover = True
            
            if recent_crossover:
                # Crossover within last 3 bars
                momentum_points = 20
            elif len(macd_hist) >= 3:
                if direction == 'long':
                    if macd_hist[-1] > macd_hist[-2] > macd_hist[-3]:
                        momentum_points = 12
                    elif macd_hist[-1] > macd_hist[-2]:
                        momentum_points = 7
                elif direction == 'short':
                    if macd_hist[-1] < macd_hist[-2] < macd_hist[-3]:
                        momentum_points = 12
                    elif macd_hist[-1] < macd_hist[-2]:
                        momentum_points = 7
            
            score += momentum_points
            breakdown['momentum'] = momentum_points
            
            # === 3. RSI (15 points) ===
            # Mean reversion focus - extremes are best entries
            rsi = primary_df['rsi'].iloc[-1]
            rsi_points = 0
            
            if direction == 'long':
                if rsi < 35:
                    # Oversold - best long entry in range
                    rsi_points = 15
                elif 35 <= rsi <= 45:
                    rsi_points = 10
                elif 45 <= rsi <= 55:
                    rsi_points = 6
                elif rsi > 55:
                    # Too high for long in chop
                    rsi_points = 2
                    
            elif direction == 'short':
                if rsi > 65:
                    # Overbought - best short entry in range
                    rsi_points = 15
                elif 55 <= rsi <= 65:
                    rsi_points = 10
                elif 45 <= rsi <= 55:
                    rsi_points = 6
                elif rsi < 45:
                    rsi_points = 2
            
            score += rsi_points
            breakdown['rsi'] = rsi_points
            
            # === 4. ENTRY LOCATION (15 points) ===
            # Values both EMA21 bounces AND range extremes
            price = primary_df['close'].iloc[-1]
            ema_21_primary = primary_df['ema_21'].iloc[-1]
            atr = primary_df['atr'].iloc[-1]
            
            # Also check range position using HTF
            high_20 = htf_df['high'].tail(20).max()
            low_20 = htf_df['low'].tail(20).min()
            range_size = high_20 - low_20
            
            entry_points = 0
            
            if atr > 0 and ema_21_primary > 0:
                ema_distance = abs(price - ema_21_primary) / atr
                
                # Check range position
                range_position = 0.5
                if range_size > 0:
                    range_position = (price - low_20) / range_size
                
                if direction == 'long':
                    # Prefer entries near range bottom or EMA21 support
                    if range_position < 0.3 and ema_distance < 0.5:
                        entry_points = 15
                    elif range_position < 0.4 or ema_distance < 0.4:
                        entry_points = 10
                    elif ema_distance < 0.8:
                        entry_points = 6
                        
                elif direction == 'short':
                    # Prefer entries near range top or EMA21 resistance
                    if range_position > 0.7 and ema_distance < 0.5:
                        entry_points = 15
                    elif range_position > 0.6 or ema_distance < 0.4:
                        entry_points = 10
                    elif ema_distance < 0.8:
                        entry_points = 6
            
            score += entry_points
            breakdown['entry_location'] = entry_points
            
            # === 5. BREAK STRUCTURE (15 points) ===
            # Breakouts from consolidation highly valued, but need volume
            bos_detected = MarketStructure.detect_break_of_structure(
                primary_df, 
                direction, 
                lookback=20  # Longer lookback for consolidation
            )
            
            structure_points = 0
            
            # Check volume confirmation for breakouts
            volume = primary_df['volume'].iloc[-1]
            volume_sma = primary_df['volume_sma'].iloc[-1]
            volume_confirmed = False
            if volume_sma > 0:
                volume_confirmed = (volume / volume_sma) > 1.3
            
            if bos_detected:
                if volume_confirmed:
                    # Breakout with volume - highly valued
                    structure_points = 15
                else:
                    # Breakout without volume - likely false
                    structure_points = 5
            else:
                # No breakout
                structure_points = 2
            
            score += structure_points
            breakdown['break_structure'] = structure_points
            
            # === 6. VOLATILITY & VOLUME (5 points) ===
            # Prefer low volatility with volume spikes on breakouts
            atr_sma = primary_df['atr_sma'].iloc[-1]
            
            vol_points = 0
            
            # Low volatility preferred (consolidation phase)
            if atr_sma > 0:
                atr_ratio = atr / atr_sma
                if 0.7 <= atr_ratio <= 1.2:
                    vol_points += 3
                elif 0.6 <= atr_ratio <= 1.4:
                    vol_points += 1
            
            # Volume spike on entry
            if volume_confirmed:
                vol_points += 2
            elif volume_sma > 0 and (volume / volume_sma) > 1.0:
                vol_points += 1
            
            score += vol_points
            breakdown['volatility_volume'] = vol_points
            
            breakdown['total'] = score
            
            return score, breakdown
            
        except Exception as e:
            logger.error(f"Error calculating CS score: {e}")
            return 0, {'error': str(e)}
    
    @staticmethod
    def get_config() -> Dict:
        """Get CS regime configuration"""
        return {
            'threshold': 85,  # Highly selective - avoid chop
            'tp_ratios': [1.2, 2.0, 3.0],  # Scalp mode - quick profits
            'tp_percentages': [50, 30, 20],
            'sl_multiplier': 1.5,  # Tightest stops - exit fast
            'position_multiplier': 0.6,  # Minimal exposure
            'description': 'Choppy/Sideways - Chop Suppression'
        }
