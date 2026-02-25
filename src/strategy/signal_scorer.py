import pandas as pd
from typing import Dict
from loguru import logger
from src.analysis.market_structure import MarketStructure

class SignalScorer:
    """Calculate signal quality score (0-100)"""
    
    @staticmethod
    def detect_price_velocity(
        df: pd.DataFrame,
        lookback_bars: int = 16
    ) -> float:
        """
        Calculate price velocity (rate of change) over lookback period
        
        Args:
            df: DataFrame with OHLC data
            lookback_bars: Number of bars to measure velocity over (default 16 = 4 hours on 15M)
        
        Returns:
            Price change percentage (e.g., 0.05 = 5% move)
        """
        try:
            if len(df) < lookback_bars + 1:
                return 0.0
            
            price_current = df['close'].iloc[-1]
            price_past = df['close'].iloc[-lookback_bars]
            
            if price_past == 0:
                return 0.0
            
            velocity = (price_current - price_past) / price_past
            return velocity
            
        except Exception as e:
            logger.error(f"Error calculating price velocity: {e}")
            return 0.0
    
    @staticmethod
    def detect_fast_rally(
        primary_df: pd.DataFrame,
        direction: str
    ) -> dict:
        """
        Detect fast rally/correction using multiple velocity windows
        Catches explosive moves that happen in 1-3 hours, not just 4-hour average
        
        Args:
            primary_df: 15M timeframe data
            direction: 'long' or 'short'
        
        Returns:
            Dict with 'detected' (bool), 'velocity_short' (float), 'velocity_medium' (float),
            'velocity_long' (float), 'is_accelerating' (bool), 'strength' (str)
        """
        try:
            # Calculate velocity over multiple windows (on 15M timeframe)
            velocity_short = SignalScorer.detect_price_velocity(primary_df, lookback_bars=6)   # 1.5 hours
            velocity_medium = SignalScorer.detect_price_velocity(primary_df, lookback_bars=12)  # 3 hours
            velocity_long = SignalScorer.detect_price_velocity(primary_df, lookback_bars=16)    # 4 hours
            
            # Debug logging for velocity calculation
            if len(primary_df) >= 17:
                price_now = primary_df['close'].iloc[-1]
                price_6bars = primary_df['close'].iloc[-7] if len(primary_df) >= 7 else 0
                price_12bars = primary_df['close'].iloc[-13] if len(primary_df) >= 13 else 0
                price_16bars = primary_df['close'].iloc[-17] if len(primary_df) >= 17 else 0
                logger.debug(f"Velocity calc: Now=${price_now:.4f}, 6bars=${price_6bars:.4f}, 12bars=${price_12bars:.4f}, 16bars=${price_16bars:.4f}")
                logger.debug(f"Velocities: 1.5h={velocity_short*100:+.2f}%, 3h={velocity_medium*100:+.2f}%, 4h={velocity_long*100:+.2f}%")
            
            # Check if velocity is accelerating (recent > medium > long term)
            if direction == 'long':
                is_accelerating = (abs(velocity_short) > abs(velocity_medium) > abs(velocity_long) 
                                 and velocity_short > 0)
                # Detect fast rally
                if velocity_short > 0.05:  # >5% in 1.5 hours
                    return {
                        'detected': True,
                        'velocity_short': velocity_short,
                        'velocity_medium': velocity_medium,
                        'velocity_long': velocity_long,
                        'is_accelerating': is_accelerating,
                        'strength': 'explosive'  # >5% in 1.5h
                    }
                elif velocity_short > 0.03 or velocity_medium > 0.045:  # >3% in 1.5h OR >4.5% in 3h
                    return {
                        'detected': True,
                        'velocity_short': velocity_short,
                        'velocity_medium': velocity_medium,
                        'velocity_long': velocity_long,
                        'is_accelerating': is_accelerating,
                        'strength': 'strong'
                    }
                elif velocity_medium > 0.03 and velocity_short > 0.02:  # 3% in 3h + still moving
                    return {
                        'detected': True,
                        'velocity_short': velocity_short,
                        'velocity_medium': velocity_medium,
                        'velocity_long': velocity_long,
                        'is_accelerating': is_accelerating,
                        'strength': 'moderate'
                    }
            else:  # short direction
                is_accelerating = (abs(velocity_short) > abs(velocity_medium) > abs(velocity_long) 
                                 and velocity_short < 0)
                # Detect fast correction
                if velocity_short < -0.05:  # <-5% in 1.5 hours
                    return {
                        'detected': True,
                        'velocity_short': velocity_short,
                        'velocity_medium': velocity_medium,
                        'velocity_long': velocity_long,
                        'is_accelerating': is_accelerating,
                        'strength': 'explosive'
                    }
                elif velocity_short < -0.03 or velocity_medium < -0.045:
                    return {
                        'detected': True,
                        'velocity_short': velocity_short,
                        'velocity_medium': velocity_medium,
                        'velocity_long': velocity_long,
                        'is_accelerating': is_accelerating,
                        'strength': 'strong'
                    }
                elif velocity_medium < -0.03 and velocity_short < -0.02:
                    return {
                        'detected': True,
                        'velocity_short': velocity_short,
                        'velocity_medium': velocity_medium,
                        'velocity_long': velocity_long,
                        'is_accelerating': is_accelerating,
                        'strength': 'moderate'
                    }
            
            # No fast rally detected
            return {
                'detected': False,
                'velocity_short': velocity_short,
                'velocity_medium': velocity_medium,
                'velocity_long': velocity_long,
                'is_accelerating': is_accelerating,
                'strength': 'none'
            }
            
        except Exception as e:
            logger.error(f"Error detecting fast rally: {e}")
            return {
                'detected': False,
                'velocity_short': 0.0,
                'velocity_medium': 0.0,
                'velocity_long': 0.0,
                'is_accelerating': False,
                'strength': 'none'
            }
    
    @staticmethod
    def detect_strong_primary_trend(
        primary_df: pd.DataFrame,
        direction: str
    ) -> tuple:
        """
        Detect if PRIMARY (15M) shows strong trending characteristics
        
        Returns:
            (is_strong: bool, reason: str)
        """
        try:
            # 1. Check PRIMARY trend direction
            primary_trend = MarketStructure.get_trend_direction(primary_df)
            
            if direction == 'long' and primary_trend != 'bullish':
                return False, f"PRIMARY not bullish ({primary_trend})"
            elif direction == 'short' and primary_trend != 'bearish':
                return False, f"PRIMARY not bearish ({primary_trend})"
            
            # 2. Check MACD acceleration (strong momentum)
            macd_hist = primary_df['macd_hist'].tail(3).values
            if len(macd_hist) < 3:
                return False, "Insufficient MACD data"
            
            if direction == 'long':
                # Require accelerating upward momentum
                if not (macd_hist[-1] > macd_hist[-2] > macd_hist[-3] and macd_hist[-1] > 0):
                    return False, "MACD not accelerating upward"
            else:
                # Require accelerating downward momentum
                if not (macd_hist[-1] < macd_hist[-2] < macd_hist[-3] and macd_hist[-1] < 0):
                    return False, "MACD not accelerating downward"
            
            # 3. Check Break of Structure on PRIMARY
            try:
                if hasattr(MarketStructure, 'detect_break_of_structure'):
                    bos_detected, bars_ago, _ = MarketStructure.detect_break_of_structure(
                        primary_df, direction, lookback=20, confirmation_bars=15
                    )
                    if bos_detected and bars_ago <= 10:
                        # Recent BOS is very strong signal
                        return True, f"Strong BOS + accelerating MACD (BOS {bars_ago} bars ago)"
            except Exception:
                pass
            
            # If no BOS but has acceleration, still consider it strong
            return True, "Accelerating MACD + PRIMARY trend aligned"
            
        except Exception as e:
            logger.error(f"Error detecting strong PRIMARY trend: {e}")
            return False, str(e)
    
    @staticmethod
    def calculate_score(
        data: Dict[str, pd.DataFrame],
        direction: str  # 'long' or 'short'
    ) -> int:
        """
        Calculate signal quality score
        
        Breakdown:
        - HTF Alignment: 25 points (most critical - never fight trend)
        - Momentum Quality (MACD): 20 points (acceleration matters)
        - Entry Location: 20 points (timing = R:R foundation)
        - BOS (Break of Structure): 13 points (institutional footprints)
        - RSI Quality: 12 points (confirmation, not predictor)
        - Volatility Suitability: 10 points (risk management)
        - Volume Confirmation: 8 points (least reliable in crypto)
        
        Returns:
            Score from 0-100
        """
        try:
            score = 0
            
            htf_df = data['htf']
            primary_df = data['primary']
            entry_df = data['entry']
            
            # === 1. HTF Trend Alignment (0-25 points) ===
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            
            if direction == 'long':
                if htf_trend == 'bullish':
                    # Check strength of trend
                    price = htf_df['close'].iloc[-1]
                    ema_200 = htf_df['ema_200'].iloc[-1]
                    
                    if ema_200 > 0:
                        distance = (price - ema_200) / ema_200
                        
                        if distance > 0.05:  # >5% above EMA200
                            score += 25
                        elif distance > 0.02:  # >2% above
                            score += 18
                        else:
                            score += 12
                    else:
                        score += 12
                        
                elif htf_trend == 'neutral':
                    # FAST RALLY DETECTION: If HTF neutral but PRIMARY shows explosive momentum
                    # Check price velocity and PRIMARY strength
                    velocity = SignalScorer.detect_price_velocity(primary_df, lookback_bars=16)
                    is_strong_primary, _ = SignalScorer.detect_strong_primary_trend(primary_df, direction)
                    
                    # If fast rally detected (>3% in 4 hours + strong PRIMARY), award partial credit
                    if velocity > 0.03 and is_strong_primary:
                        # Award 18-20 points for explosive bullish move (HTF hasn't caught up yet)
                        if velocity > 0.05:  # >5% in 4 hours = very strong
                            score += 20
                        else:  # 3-5% in 4 hours = strong
                            score += 18
                    else:
                        # Standard neutral scoring
                        score += 8
            
            elif direction == 'short':
                if htf_trend == 'bearish':
                    price = htf_df['close'].iloc[-1]
                    ema_200 = htf_df['ema_200'].iloc[-1]
                    
                    if ema_200 > 0:
                        distance = (ema_200 - price) / ema_200
                        
                        if distance > 0.05:
                            score += 25
                        elif distance > 0.02:
                            score += 18
                        else:
                            score += 12
                    else:
                        score += 12
                        
                elif htf_trend == 'neutral':
                    # FAST CORRECTION DETECTION: If HTF neutral but PRIMARY shows explosive downward momentum
                    velocity = SignalScorer.detect_price_velocity(primary_df, lookback_bars=16)
                    is_strong_primary, _ = SignalScorer.detect_strong_primary_trend(primary_df, direction)
                    
                    # If fast correction detected (<-3% in 4 hours + strong PRIMARY), award partial credit
                    if velocity < -0.03 and is_strong_primary:
                        # Award 18-20 points for explosive bearish move
                        if velocity < -0.05:  # <-5% in 4 hours = very strong
                            score += 20
                        else:  # -3% to -5% in 4 hours = strong
                            score += 18
                    else:
                        # Standard neutral scoring
                        score += 8
            
            # === 2. Momentum Quality (0-20 points) ===
            macd_hist = primary_df['macd_hist'].tail(3).values
            
            if len(macd_hist) >= 3:
                if direction == 'long':
                    # Accelerating upward momentum
                    if (macd_hist[-1] > macd_hist[-2] > macd_hist[-3] and 
                        macd_hist[-1] > 0):
                        score += 20
                    elif macd_hist[-1] > macd_hist[-2] and macd_hist[-1] > 0:
                        score += 14
                    elif macd_hist[-1] > 0:
                        score += 8
                
                elif direction == 'short':
                    # Accelerating downward momentum
                    if (macd_hist[-1] < macd_hist[-2] < macd_hist[-3] and 
                        macd_hist[-1] < 0):
                        score += 20
                    elif macd_hist[-1] < macd_hist[-2] and macd_hist[-1] < 0:
                        score += 14
                    elif macd_hist[-1] < 0:
                        score += 8
            
            # === 3. RSI Quality (0-12 points) ===
            rsi = primary_df['rsi'].iloc[-1]
            
            # Get HTF trend for context-aware RSI scoring
            htf_trend_for_rsi = MarketStructure.get_trend_direction(htf_df)
            
            if direction == 'long':
                # During strong bullish trends, higher RSI is normal and acceptable
                if htf_trend_for_rsi == 'bullish':
                    if 40 <= rsi <= 65:
                        score += 12
                    elif 30 <= rsi < 40 or 65 < rsi <= 72:
                        score += 8
                    elif 25 <= rsi < 30 or 72 < rsi <= 78:
                        score += 4
                else:
                    if 30 <= rsi <= 50:
                        score += 12
                    elif 50 < rsi <= 60:
                        score += 8
                    elif 25 <= rsi < 30 or 60 < rsi <= 65:
                        score += 4
            
            elif direction == 'short':
                # During strong bearish trends, lower RSI is normal and acceptable
                if htf_trend_for_rsi == 'bearish':
                    if 35 <= rsi <= 60:
                        score += 12
                    elif 28 <= rsi < 35 or 60 < rsi <= 70:
                        score += 8
                    elif 22 <= rsi < 28 or 70 < rsi <= 75:
                        score += 4
                else:
                    if 50 <= rsi <= 70:
                        score += 12
                    elif 40 <= rsi < 50:
                        score += 8
                    elif 35 <= rsi < 40 or 70 < rsi <= 75:
                        score += 4
            
            # === 4. Entry Location Quality (0-20 points) ===
            price = entry_df['close'].iloc[-1]
            ema_21 = entry_df['ema_21'].iloc[-1]
            atr = primary_df['atr'].iloc[-1]
            
            if atr > 0 and ema_21 > 0:
                distance_from_ema = abs(price - ema_21) / atr
                
                if distance_from_ema < 0.3:  # Very close to EMA
                    score += 20
                elif distance_from_ema < 0.6:
                    score += 14
                elif distance_from_ema < 1.0:
                    score += 8
                else:
                    score += 3
            
            # === 5. Break of Structure (0-10 points) ===
            # Check primary timeframe for BOS confirmation
            try:
                if hasattr(MarketStructure, 'detect_break_of_structure'):
                    bos_detected, bars_ago, structure_level = MarketStructure.detect_break_of_structure(
                        primary_df, direction
                    )
                    bos_points, _ = MarketStructure.get_bos_quality_score(bos_detected, bars_ago)
                    score += bos_points
                # else: Skip BOS scoring (0 points)
            except Exception as e:
                logger.debug(f"BOS detection skipped: {e}")
                # Continue without BOS points
            
            # === 6. Volume Confirmation (0-8 points) ===
            # Use PRIMARY timeframe (15m) for volume - more representative than 5m
            volume = primary_df['volume'].iloc[-1]
            volume_sma = primary_df['volume_sma'].iloc[-1]
            
            if volume_sma > 0:
                volume_ratio = volume / volume_sma
                
                # More lenient thresholds for crypto (volume less reliable)
                if volume_ratio > 1.2:  # Was 1.5x
                    score += 8
                elif volume_ratio > 0.9:  # Was 1.2x
                    score += 5
                elif volume_ratio > 0.7:  # Was 1.0x
                    score += 3
                elif volume_ratio > 0.5:  # Was 0.8x
                    score += 1
            
            return min(score, 100)  # Cap at 100
            
        except Exception as e:
            logger.error(f"Error calculating signal score: {e}")
            return 0
    
    @staticmethod
    def get_score_grade(score: int) -> str:
        """Convert score to letter grade"""
        if score >= 90:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 70:
            return 'B+'
        elif score >= 60:
            return 'B'
        elif score >= 50:
            return 'C'
        else:
            return 'D'

    @staticmethod
    def calculate_score_with_breakdown(
        data: Dict[str, pd.DataFrame],
        direction: str,
        symbol: str
    ) -> tuple:
        """
        Calculate signal quality score with detailed breakdown
        
        Returns:
            (score: int, breakdown: dict)
        """
        try:
            breakdown = {
                'htf_alignment': {'points': 0, 'max': 25, 'details': ''},
                'momentum': {'points': 0, 'max': 20, 'details': ''},
                'entry_location': {'points': 0, 'max': 20, 'details': ''},
                'break_of_structure': {'points': 0, 'max': 13, 'details': ''},
                'rsi_quality': {'points': 0, 'max': 12, 'details': ''},
                'volatility': {'points': 0, 'max': 10, 'details': ''},
                'volume': {'points': 0, 'max': 8, 'details': ''}
            }
            
            score = 0
            htf_df = data['htf']
            primary_df = data['primary']
            entry_df = data['entry']
            
            # === 1. HTF Trend Alignment (0-25 points) ===
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            
            if direction == 'long':
                if htf_trend == 'bullish':
                    price = htf_df['close'].iloc[-1]
                    ema_200 = htf_df['ema_200'].iloc[-1]
                    
                    if ema_200 > 0:
                        distance = (price - ema_200) / ema_200
                        
                        if distance > 0.05:
                            breakdown['htf_alignment']['points'] = 25
                            breakdown['htf_alignment']['details'] = f'Strongly bullish, {distance*100:.1f}% above EMA200'
                            score += 25
                        elif distance > 0.02:
                            breakdown['htf_alignment']['points'] = 18
                            breakdown['htf_alignment']['details'] = f'Bullish, {distance*100:.1f}% above EMA200'
                            score += 18
                        else:
                            breakdown['htf_alignment']['points'] = 12
                            breakdown['htf_alignment']['details'] = f'Weakly bullish, {distance*100:.1f}% above EMA200'
                            score += 12
                    else:
                        breakdown['htf_alignment']['points'] = 12
                        breakdown['htf_alignment']['details'] = 'Bullish trend'
                        score += 12
                        
                elif htf_trend == 'neutral':
                    # NEW FAST RALLY DETECTION: Multi-window velocity analysis
                    rally_data = SignalScorer.detect_fast_rally(primary_df, direction)
                    is_strong_primary, primary_reason = SignalScorer.detect_strong_primary_trend(primary_df, direction)
                    
                    if rally_data['detected'] and is_strong_primary:
                        # Fast rally detected - award points based on strength
                        if rally_data['strength'] == 'explosive':  # >5% in 1.5h
                            breakdown['htf_alignment']['points'] = 25
                            breakdown['htf_alignment']['details'] = f"EXPLOSIVE RALLY: +{rally_data['velocity_short']*100:.1f}% in 1.5h {'(accelerating)' if rally_data['is_accelerating'] else ''}"
                            score += 25
                        elif rally_data['strength'] == 'strong':  # >3% in 1.5h or >4.5% in 3h
                            breakdown['htf_alignment']['points'] = 22
                            breakdown['htf_alignment']['details'] = f"STRONG RALLY: +{rally_data['velocity_short']*100:.1f}% (1.5h), +{rally_data['velocity_medium']*100:.1f}% (3h)"
                            score += 22
                        else:  # moderate
                            breakdown['htf_alignment']['points'] = 18
                            breakdown['htf_alignment']['details'] = f"FAST RALLY: +{rally_data['velocity_medium']*100:.1f}% in 3h, {primary_reason}"
                            score += 18
                    else:
                        # No fast rally - low score for neutral HTF
                        breakdown['htf_alignment']['points'] = 8
                        breakdown['htf_alignment']['details'] = f"HTF neutral, weak alignment (1.5h: {rally_data['velocity_short']*100:+.1f}%, 3h: {rally_data['velocity_medium']*100:+.1f}%)"
                        score += 8
                else:
                    breakdown['htf_alignment']['details'] = f'HTF is {htf_trend}, opposing direction'
            
            elif direction == 'short':
                if htf_trend == 'bearish':
                    price = htf_df['close'].iloc[-1]
                    ema_200 = htf_df['ema_200'].iloc[-1]
                    
                    if ema_200 > 0:
                        distance = (ema_200 - price) / ema_200
                        
                        if distance > 0.05:
                            breakdown['htf_alignment']['points'] = 25
                            breakdown['htf_alignment']['details'] = f'Strongly bearish, {distance*100:.1f}% below EMA200'
                            score += 25
                        elif distance > 0.02:
                            breakdown['htf_alignment']['points'] = 18
                            breakdown['htf_alignment']['details'] = f'Bearish, {distance*100:.1f}% below EMA200'
                            score += 18
                        else:
                            breakdown['htf_alignment']['points'] = 12
                            breakdown['htf_alignment']['details'] = f'Weakly bearish, {distance*100:.1f}% below EMA200'
                            score += 12
                    else:
                        breakdown['htf_alignment']['points'] = 12
                        breakdown['htf_alignment']['details'] = 'Bearish trend'
                        score += 12
                        
                elif htf_trend == 'neutral':
                    # NEW FAST CORRECTION DETECTION: Multi-window velocity analysis
                    rally_data = SignalScorer.detect_fast_rally(primary_df, direction)
                    is_strong_primary, primary_reason = SignalScorer.detect_strong_primary_trend(primary_df, direction)
                    
                    if rally_data['detected'] and is_strong_primary:
                        # Fast correction detected - award points based on strength
                        if rally_data['strength'] == 'explosive':  # <-5% in 1.5h
                            breakdown['htf_alignment']['points'] = 25
                            breakdown['htf_alignment']['details'] = f"EXPLOSIVE CORRECTION: {rally_data['velocity_short']*100:.1f}% in 1.5h {'(accelerating)' if rally_data['is_accelerating'] else ''}"
                            score += 25
                        elif rally_data['strength'] == 'strong':  # <-3% in 1.5h or <-4.5% in 3h
                            breakdown['htf_alignment']['points'] = 22
                            breakdown['htf_alignment']['details'] = f"STRONG CORRECTION: {rally_data['velocity_short']*100:.1f}% (1.5h), {rally_data['velocity_medium']*100:.1f}% (3h)"
                            score += 22
                        else:  # moderate
                            breakdown['htf_alignment']['points'] = 18
                            breakdown['htf_alignment']['details'] = f"FAST CORRECTION: {rally_data['velocity_medium']*100:.1f}% in 3h, {primary_reason}"
                            score += 18
                    else:
                        # No fast correction - low score for neutral HTF
                        breakdown['htf_alignment']['points'] = 8
                        breakdown['htf_alignment']['details'] = f"HTF neutral, weak alignment (1.5h: {rally_data['velocity_short']*100:+.1f}%, 3h: {rally_data['velocity_medium']*100:+.1f}%)"
                        score += 8
                else:
                    breakdown['htf_alignment']['details'] = f'HTF is {htf_trend}, opposing direction'
            
            # === 2. Momentum Quality (0-20 points) ===
            macd_hist = primary_df['macd_hist'].tail(3).values
            
            if len(macd_hist) >= 3:
                if direction == 'long':
                    if (macd_hist[-1] > macd_hist[-2] > macd_hist[-3] and macd_hist[-1] > 0):
                        breakdown['momentum']['points'] = 20
                        breakdown['momentum']['details'] = 'Accelerating upward momentum'
                        score += 20
                    elif macd_hist[-1] > macd_hist[-2] and macd_hist[-1] > 0:
                        breakdown['momentum']['points'] = 14
                        breakdown['momentum']['details'] = 'Increasing momentum'
                        score += 14
                    elif macd_hist[-1] > 0:
                        breakdown['momentum']['points'] = 8
                        breakdown['momentum']['details'] = 'Positive but weak momentum'
                        score += 8
                elif direction == 'short':
                    if (macd_hist[-1] < macd_hist[-2] < macd_hist[-3] and macd_hist[-1] < 0):
                        breakdown['momentum']['points'] = 20
                        breakdown['momentum']['details'] = 'Accelerating downward momentum'
                        score += 20
                    elif macd_hist[-1] < macd_hist[-2] and macd_hist[-1] < 0:
                        breakdown['momentum']['points'] = 14
                        breakdown['momentum']['details'] = 'Increasing downward momentum'
                        score += 14
                    elif macd_hist[-1] < 0:
                        breakdown['momentum']['points'] = 8
                        breakdown['momentum']['details'] = 'Negative but weak momentum'
                        score += 8
                else:
                    breakdown['momentum']['details'] = f'Negative momentum (MACD: {macd_hist[-1]:.4f})'
            
            # === 3. RSI Quality (0-12 points) ===
            rsi = primary_df['rsi'].iloc[-1]
            
            # Get HTF trend and check for fast rally
            htf_trend_for_rsi = MarketStructure.get_trend_direction(htf_df)
            rally_data = SignalScorer.detect_fast_rally(primary_df, direction)
            is_fast_rally = rally_data['detected']
            
            if direction == 'long':
                # During fast rallies, allow MUCH higher RSI (momentum trades)
                if is_fast_rally and rally_data['strength'] in ['explosive', 'strong']:
                    if 50 <= rsi <= 75:
                        breakdown['rsi_quality']['points'] = 12
                        breakdown['rsi_quality']['details'] = f'Strong momentum RSI during fast rally ({rsi:.1f})'
                        score += 12
                    elif 45 <= rsi < 50 or 75 < rsi <= 82:
                        breakdown['rsi_quality']['points'] = 10
                        breakdown['rsi_quality']['details'] = f'Acceptable RSI in explosive move ({rsi:.1f})'
                        score += 10
                    elif 40 <= rsi < 45 or 82 < rsi <= 88:
                        breakdown['rsi_quality']['points'] = 6
                        breakdown['rsi_quality']['details'] = f'High RSI but fast rally continues ({rsi:.1f})'
                        score += 6
                    else:
                        breakdown['rsi_quality']['points'] = 2
                        breakdown['rsi_quality']['details'] = f'Extreme RSI even for fast rally ({rsi:.1f})'
                        score += 2
                # During strong bullish trends, higher RSI is normal and acceptable
                elif htf_trend_for_rsi == 'bullish':
                    # In bullish trends, embrace momentum - higher RSI is okay
                    if 40 <= rsi <= 65:
                        breakdown['rsi_quality']['points'] = 12
                        breakdown['rsi_quality']['details'] = f'Optimal RSI for long in bullish trend ({rsi:.1f})'
                        score += 12
                    elif 30 <= rsi < 40 or 65 < rsi <= 72:
                        breakdown['rsi_quality']['points'] = 8
                        breakdown['rsi_quality']['details'] = f'Acceptable RSI in bullish trend ({rsi:.1f})'
                        score += 8
                    elif 25 <= rsi < 30 or 72 < rsi <= 78:
                        breakdown['rsi_quality']['points'] = 4
                        breakdown['rsi_quality']['details'] = f'Marginal RSI ({rsi:.1f})'
                        score += 4
                    else:
                        breakdown['rsi_quality']['details'] = f'Extreme RSI for long ({rsi:.1f})'
                else:
                    # In neutral/bearish trends, prefer lower RSI (reversal plays)
                    if 30 <= rsi <= 50:
                        breakdown['rsi_quality']['points'] = 12
                        breakdown['rsi_quality']['details'] = f'Optimal RSI for long ({rsi:.1f})'
                        score += 12
                    elif 50 < rsi <= 60:
                        breakdown['rsi_quality']['points'] = 8
                        breakdown['rsi_quality']['details'] = f'Acceptable RSI ({rsi:.1f})'
                        score += 8
                    elif 25 <= rsi < 30 or 60 < rsi <= 65:
                        breakdown['rsi_quality']['points'] = 4
                        breakdown['rsi_quality']['details'] = f'Marginal RSI ({rsi:.1f})'
                        score += 4
                    else:
                        breakdown['rsi_quality']['details'] = f'Poor RSI for long ({rsi:.1f})'
            
            elif direction == 'short':
                # During fast corrections, allow MUCH lower RSI (momentum trades)
                if is_fast_rally and rally_data['strength'] in ['explosive', 'strong']:
                    if 25 <= rsi <= 50:
                        breakdown['rsi_quality']['points'] = 12
                        breakdown['rsi_quality']['details'] = f'Strong momentum RSI during fast correction ({rsi:.1f})'
                        score += 12
                    elif 18 <= rsi < 25 or 50 < rsi <= 55:
                        breakdown['rsi_quality']['points'] = 10
                        breakdown['rsi_quality']['details'] = f'Acceptable RSI in explosive move ({rsi:.1f})'
                        score += 10
                    elif 12 <= rsi < 18 or 55 < rsi <= 60:
                        breakdown['rsi_quality']['points'] = 6
                        breakdown['rsi_quality']['details'] = f'Low RSI but fast correction continues ({rsi:.1f})'
                        score += 6
                    else:
                        breakdown['rsi_quality']['points'] = 2
                        breakdown['rsi_quality']['details'] = f'Extreme RSI even for fast correction ({rsi:.1f})'
                        score += 2
                # During strong bearish trends, lower RSI is normal and acceptable
                elif htf_trend_for_rsi == 'bearish':
                    # In bearish trends, embrace downward momentum - lower RSI is okay
                    if 35 <= rsi <= 60:
                        breakdown['rsi_quality']['points'] = 12
                        breakdown['rsi_quality']['details'] = f'Optimal RSI for short in bearish trend ({rsi:.1f})'
                        score += 12
                    elif 28 <= rsi < 35 or 60 < rsi <= 70:
                        breakdown['rsi_quality']['points'] = 8
                        breakdown['rsi_quality']['details'] = f'Acceptable RSI in bearish trend ({rsi:.1f})'
                        score += 8
                    elif 22 <= rsi < 28 or 70 < rsi <= 75:
                        breakdown['rsi_quality']['points'] = 4
                        breakdown['rsi_quality']['details'] = f'Marginal RSI ({rsi:.1f})'
                        score += 4
                    else:
                        breakdown['rsi_quality']['details'] = f'Extreme RSI for short ({rsi:.1f})'
                else:
                    # In neutral/bullish trends, prefer higher RSI (reversal plays)
                    if 50 <= rsi <= 70:
                        breakdown['rsi_quality']['points'] = 12
                        breakdown['rsi_quality']['details'] = f'Optimal RSI for short ({rsi:.1f})'
                        score += 12
                    elif 40 <= rsi < 50:
                        breakdown['rsi_quality']['points'] = 8
                        breakdown['rsi_quality']['details'] = f'Acceptable RSI ({rsi:.1f})'
                        score += 8
                    elif 35 <= rsi < 40 or 70 < rsi <= 75:
                        breakdown['rsi_quality']['points'] = 4
                        breakdown['rsi_quality']['details'] = f'Marginal RSI ({rsi:.1f})'
                        score += 4
                    else:
                        breakdown['rsi_quality']['details'] = f'Poor RSI for short ({rsi:.1f})'
            
            # === 4. Entry Location Quality (0-20 points) ===
            price = entry_df['close'].iloc[-1]
            ema_21 = entry_df['ema_21'].iloc[-1]
            atr = primary_df['atr'].iloc[-1]
            
            if atr > 0 and ema_21 > 0:
                distance_from_ema = abs(price - ema_21) / atr
                
                if distance_from_ema < 0.3:
                    breakdown['entry_location']['points'] = 20
                    breakdown['entry_location']['details'] = f'Excellent entry location ({distance_from_ema:.2f} ATR from EMA)'
                    score += 20
                elif distance_from_ema < 0.6:
                    breakdown['entry_location']['points'] = 14
                    breakdown['entry_location']['details'] = f'Good entry location ({distance_from_ema:.2f} ATR from EMA)'
                    score += 14
                elif distance_from_ema < 1.0:
                    breakdown['entry_location']['points'] = 8
                    breakdown['entry_location']['details'] = f'Fair entry location ({distance_from_ema:.2f} ATR from EMA)'
                    score += 8
                else:
                    breakdown['entry_location']['points'] = 3
                    breakdown['entry_location']['details'] = f'Poor entry location ({distance_from_ema:.2f} ATR from EMA, chasing)'
                    score += 3
            
            # === 5. Break of Structure (0-13 points) ===
            # Check for BOS on primary timeframe (15M)
            try:
                if hasattr(MarketStructure, 'detect_break_of_structure'):
                    bos_detected, bars_ago, structure_level = MarketStructure.detect_break_of_structure(
                        primary_df, direction, lookback=20, confirmation_bars=20
                    )
                    bos_points, bos_desc = MarketStructure.get_bos_quality_score(bos_detected, bars_ago, max_points=13)
                    
                    breakdown['break_of_structure']['points'] = bos_points
                    if bos_detected:
                        breakdown['break_of_structure']['details'] = f'{bos_desc} at ${structure_level:.2f}'
                    else:
                        breakdown['break_of_structure']['details'] = 'No structure break detected'
                    score += bos_points
                else:
                    # BOS methods not available
                    breakdown['break_of_structure']['details'] = 'BOS detection not implemented'
            except Exception as e:
                logger.debug(f"BOS detection skipped: {e}")
                breakdown['break_of_structure']['details'] = 'BOS detection error'
            
            # === 6. Volatility Suitability (0-10 points) ===
            current_atr = primary_df['atr'].iloc[-1]
            avg_atr = primary_df['atr_sma'].iloc[-1]
            
            if avg_atr > 0:
                atr_ratio = current_atr / avg_atr
                
                if 1.0 <= atr_ratio <= 1.4:  # Ideal volatility
                    breakdown['volatility']['points'] = 10
                    breakdown['volatility']['details'] = f'Ideal volatility ({atr_ratio:.2f}x avg)'
                    score += 10
                elif 0.8 <= atr_ratio < 1.0 or 1.4 < atr_ratio <= 1.8:  # Acceptable
                    breakdown['volatility']['points'] = 6
                    breakdown['volatility']['details'] = f'Acceptable volatility ({atr_ratio:.2f}x avg)'
                    score += 6
                elif 0.7 <= atr_ratio < 0.8 or 1.8 < atr_ratio <= 2.0:  # Marginal
                    breakdown['volatility']['points'] = 3
                    breakdown['volatility']['details'] = f'Marginal volatility ({atr_ratio:.2f}x avg)'
                    score += 3
                else:
                    breakdown['volatility']['details'] = f'Extreme volatility ({atr_ratio:.2f}x avg)'
            else:
                breakdown['volatility']['details'] = 'Invalid ATR data'
            
            # === 7. Volume Confirmation (0-8 points) ===
            # Use PRIMARY timeframe (15m) for volume - more representative than 5m
            volume = primary_df['volume'].iloc[-1]
            volume_sma = primary_df['volume_sma'].iloc[-1]
            
            # Also check last 2 candles for recent volume trend
            recent_volumes = primary_df['volume'].iloc[-2:].values
            avg_recent = recent_volumes.mean()
            
            if volume_sma > 0:
                volume_ratio = volume / volume_sma
                recent_ratio = avg_recent / volume_sma
                
                # Log diagnostic info
                logger.debug(f"Volume check: current={volume:,.0f}, avg={volume_sma:,.0f}, "
                           f"ratio={volume_ratio:.2f}x, recent_2_candles_avg={avg_recent:,.0f} ({recent_ratio:.2f}x)")
                
                # More lenient thresholds for crypto (volume less reliable)
                if volume_ratio > 1.2:  # Was 1.5x
                    breakdown['volume']['points'] = 8
                    breakdown['volume']['details'] = f'Strong volume ({volume_ratio:.2f}x average)'
                    score += 8
                elif volume_ratio > 0.9:  # Was 1.2x
                    breakdown['volume']['points'] = 5
                    breakdown['volume']['details'] = f'Good volume ({volume_ratio:.2f}x average)'
                    score += 5
                elif volume_ratio > 0.7:  # Was 1.0x
                    breakdown['volume']['points'] = 3
                    breakdown['volume']['details'] = f'Above average volume ({volume_ratio:.2f}x)'
                    score += 3
                elif volume_ratio > 0.5:  # Was 0.8x
                    breakdown['volume']['points'] = 1
                    breakdown['volume']['details'] = f'Near average volume ({volume_ratio:.2f}x)'
                    score += 1
                else:
                    breakdown['volume']['details'] = f'Low volume ({volume_ratio:.2f}x average)'
            else:
                breakdown['volume']['details'] = 'Invalid volume data'
            
            final_score = min(score, 100)
            
            # Log detailed breakdown
            logger.info(f"{symbol} {direction.upper()} signal score breakdown:")
            logger.info(f"  HTF Alignment:   {breakdown['htf_alignment']['points']:2d}/{breakdown['htf_alignment']['max']} - {breakdown['htf_alignment']['details']}")
            logger.info(f"  Momentum (MACD): {breakdown['momentum']['points']:2d}/{breakdown['momentum']['max']} - {breakdown['momentum']['details']}")
            logger.info(f"  RSI Quality:     {breakdown['rsi_quality']['points']:2d}/{breakdown['rsi_quality']['max']} - {breakdown['rsi_quality']['details']}")
            logger.info(f"  Entry Location:  {breakdown['entry_location']['points']:2d}/{breakdown['entry_location']['max']} - {breakdown['entry_location']['details']}")
            logger.info(f"  Break Structure: {breakdown['break_of_structure']['points']:2d}/{breakdown['break_of_structure']['max']} - {breakdown['break_of_structure']['details']}")
            logger.info(f"  Volatility:      {breakdown['volatility']['points']:2d}/{breakdown['volatility']['max']} - {breakdown['volatility']['details']}")
            logger.info(f"  Volume:          {breakdown['volume']['points']:2d}/{breakdown['volume']['max']} - {breakdown['volume']['details']}")
            logger.info(f"  TOTAL SCORE:     {final_score}/100")
            
            return final_score, breakdown
            
        except Exception as e:
            logger.error(f"Error calculating signal score: {e}")
            return 0, {}