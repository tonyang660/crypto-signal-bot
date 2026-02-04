import pandas as pd
from typing import Dict
from loguru import logger
from src.analysis.market_structure import MarketStructure

class SignalScorer:
    """Calculate signal quality score (0-100)"""
    
    @staticmethod
    def calculate_score(
        data: Dict[str, pd.DataFrame],
        direction: str  # 'long' or 'short'
    ) -> int:
        """
        Calculate signal quality score
        
        Breakdown:
        - HTF Alignment: 25 points
        - Momentum Quality (MACD): 20 points
        - RSI Quality: 15 points (NEW)
        - Entry Location: 20 points
        - Volatility Suitability: 10 points
        - Volume Confirmation: 10 points
        
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
                        score += 15
                        
                elif htf_trend == 'neutral':
                    score += 10
            
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
            
            # === 3. RSI Quality (0-15 points) ===
            rsi = primary_df['rsi'].iloc[-1]
            
            if direction == 'long':
                # Long entries: RSI should be oversold to neutral (not overbought)
                if 30 <= rsi <= 50:  # Sweet spot: reset but not overbought
                    score += 15
                elif 50 < rsi <= 60:  # Acceptable
                    score += 10
                elif 25 <= rsi < 30 or 60 < rsi <= 65:  # Marginal
                    score += 5
                # RSI > 70 or < 25 = 0 points (too extreme)
            
            elif direction == 'short':
                # Short entries: RSI should be overbought to neutral (not oversold)
                if 50 <= rsi <= 70:  # Sweet spot: extended but not oversold
                    score += 15
                elif 40 <= rsi < 50:  # Acceptable
                    score += 10
                elif 35 <= rsi < 40 or 70 < rsi <= 75:  # Marginal
                    score += 5
                # RSI < 30 or > 75 = 0 points (too extreme)
            
            # === 4. Entry Location Quality (0-20 points) ===
            price = entry_df['close'].iloc[-1]
            ema_21 = entry_df['ema_21'].iloc[-1]
            atr = primary_df['atr'].iloc[-1]
            
            if atr > 0 and ema_21 > 0:
                distance_from_ema = abs(price - ema_21) / atr
                
                if distance_from_ema < 0.3:  # Very close to EMA
                    score += 20
                elif distance_from_ema < 0.6:
                    score += 15
                elif distance_from_ema < 1.0:
                    score += 10
                else:
                    score += 5
            
            # === 5. Volatility Suitability (0-10 points) ===
            current_atr = primary_df['atr'].iloc[-1]
            avg_atr = primary_df['atr_sma'].iloc[-1]
            
            if avg_atr > 0:
                atr_ratio = current_atr / avg_atr
                
                if 0.9 <= atr_ratio <= 1.3:  # Normal volatility
                    score += 10
                elif 0.7 <= atr_ratio <= 1.6:
                    score += 7
                elif 0.5 <= atr_ratio <= 2.0:
                    score += 3
            
            # === 5. Volume Confirmation (0-10 points) ===
            volume = entry_df['volume'].iloc[-1]
            volume_sma = entry_df['volume_sma'].iloc[-1]
            
            if volume_sma > 0:
                volume_ratio = volume / volume_sma
                
                if volume_ratio > 1.5:  # Significantly above average
                    score += 10
                elif volume_ratio > 1.2:
                    score += 7
                elif volume_ratio > 1.0:
                    score += 5
            
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
                'rsi_quality': {'points': 0, 'max': 15, 'details': ''},
                'entry_location': {'points': 0, 'max': 20, 'details': ''},
                'volatility': {'points': 0, 'max': 10, 'details': ''},
                'volume': {'points': 0, 'max': 10, 'details': ''}
            }
            
            score = 0
            htf_df = data['htf']
            primary_df = data['primary']
            entry_df = data['entry']
            
            # === 1. HTF Trend Alignment (0-30 points) ===
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
                    breakdown['htf_alignment']['points'] = 10
                    breakdown['htf_alignment']['details'] = 'HTF neutral, weak alignment'
                    score += 10
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
                    breakdown['htf_alignment']['points'] = 10
                    breakdown['htf_alignment']['details'] = 'HTF neutral, weak alignment'
                    score += 10
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
            
            # === 3. RSI Quality (0-15 points) ===
            rsi = primary_df['rsi'].iloc[-1]
            
            if direction == 'long':
                if 30 <= rsi <= 50:
                    breakdown['rsi_quality']['points'] = 15
                    breakdown['rsi_quality']['details'] = f'Optimal RSI for long ({rsi:.1f})'
                    score += 15
                elif 50 < rsi <= 60:
                    breakdown['rsi_quality']['points'] = 10
                    breakdown['rsi_quality']['details'] = f'Acceptable RSI ({rsi:.1f})'
                    score += 10
                elif 25 <= rsi < 30 or 60 < rsi <= 65:
                    breakdown['rsi_quality']['points'] = 5
                    breakdown['rsi_quality']['details'] = f'Marginal RSI ({rsi:.1f})'
                    score += 5
                else:
                    breakdown['rsi_quality']['details'] = f'Poor RSI for long ({rsi:.1f})'
            
            elif direction == 'short':
                if 50 <= rsi <= 70:
                    breakdown['rsi_quality']['points'] = 15
                    breakdown['rsi_quality']['details'] = f'Optimal RSI for short ({rsi:.1f})'
                    score += 15
                elif 40 <= rsi < 50:
                    breakdown['rsi_quality']['points'] = 10
                    breakdown['rsi_quality']['details'] = f'Acceptable RSI ({rsi:.1f})'
                    score += 10
                elif 35 <= rsi < 40 or 70 < rsi <= 75:
                    breakdown['rsi_quality']['points'] = 5
                    breakdown['rsi_quality']['details'] = f'Marginal RSI ({rsi:.1f})'
                    score += 5
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
                    breakdown['entry_location']['points'] = 15
                    breakdown['entry_location']['details'] = f'Good entry location ({distance_from_ema:.2f} ATR from EMA)'
                    score += 15
                elif distance_from_ema < 1.0:
                    breakdown['entry_location']['points'] = 10
                    breakdown['entry_location']['details'] = f'Fair entry location ({distance_from_ema:.2f} ATR from EMA)'
                    score += 10
                else:
                    breakdown['entry_location']['points'] = 5
                    breakdown['entry_location']['details'] = f'Poor entry location ({distance_from_ema:.2f} ATR from EMA)'
                    score += 5
            
            # === 5. Volatility Suitability (0-10 points) ===
            current_atr = primary_df['atr'].iloc[-1]
            avg_atr = primary_df['atr_sma'].iloc[-1]
            
            if avg_atr > 0:
                atr_ratio = current_atr / avg_atr
                
                if 0.9 <= atr_ratio <= 1.3:
                    breakdown['volatility']['points'] = 10
                    breakdown['volatility']['details'] = f'Normal volatility (ATR ratio: {atr_ratio:.2f})'
                    score += 10
                elif 0.7 <= atr_ratio <= 1.6:
                    breakdown['volatility']['points'] = 7
                    breakdown['volatility']['details'] = f'Acceptable volatility (ATR ratio: {atr_ratio:.2f})'
                    score += 7
                elif 0.5 <= atr_ratio <= 2.0:
                    breakdown['volatility']['points'] = 3
                    breakdown['volatility']['details'] = f'Marginal volatility (ATR ratio: {atr_ratio:.2f})'
                    score += 3
            else:
                breakdown['volatility']['details'] = f'Extreme volatility (ATR ratio: {atr_ratio:.2f})'
            
            # === 6. Volume Confirmation (0-10 points) ===
            volume = entry_df['volume'].iloc[-1]
            volume_sma = entry_df['volume_sma'].iloc[-1]
            
            if volume_sma > 0:
                volume_ratio = volume / volume_sma
                
                if volume_ratio > 1.5:
                    breakdown['volume']['points'] = 10
                    breakdown['volume']['details'] = f'Strong volume ({volume_ratio:.2f}x average)'
                    score += 10
                elif volume_ratio > 1.2:
                    breakdown['volume']['points'] = 7
                    breakdown['volume']['details'] = f'Good volume ({volume_ratio:.2f}x average)'
                    score += 7
                elif volume_ratio > 1.0:
                    breakdown['volume']['points'] = 5
                    breakdown['volume']['details'] = f'Above average volume ({volume_ratio:.2f}x)'
                    score += 5
            else:
                breakdown['volume']['details'] = f'Low volume ({volume_ratio:.2f}x average)'
            
            final_score = min(score, 100)
            
            # Log detailed breakdown
            logger.info(f"{symbol} {direction.upper()} signal score breakdown:")
            logger.info(f"  HTF Alignment:   {breakdown['htf_alignment']['points']:2d}/{breakdown['htf_alignment']['max']} - {breakdown['htf_alignment']['details']}")
            logger.info(f"  Momentum (MACD): {breakdown['momentum']['points']:2d}/{breakdown['momentum']['max']} - {breakdown['momentum']['details']}")
            logger.info(f"  RSI Quality:     {breakdown['rsi_quality']['points']:2d}/{breakdown['rsi_quality']['max']} - {breakdown['rsi_quality']['details']}")
            logger.info(f"  Entry Location:  {breakdown['entry_location']['points']:2d}/{breakdown['entry_location']['max']} - {breakdown['entry_location']['details']}")
            logger.info(f"  Volatility:      {breakdown['volatility']['points']:2d}/{breakdown['volatility']['max']} - {breakdown['volatility']['details']}")
            logger.info(f"  Volume:          {breakdown['volume']['points']:2d}/{breakdown['volume']['max']} - {breakdown['volume']['details']}")
            logger.info(f"  TOTAL SCORE:     {final_score}/100")
            
            return final_score, breakdown
            
        except Exception as e:
            logger.error(f"Error calculating signal score: {e}")
            return 0, {}