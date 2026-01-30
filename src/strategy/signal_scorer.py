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
        - HTF Alignment: 30 points
        - Momentum Quality: 25 points
        - Entry Location: 20 points
        - Volatility Suitability: 15 points
        - Volume Confirmation: 10 points
        
        Returns:
            Score from 0-100
        """
        try:
            score = 0
            
            htf_df = data['htf']
            primary_df = data['primary']
            entry_df = data['entry']
            
            # === 1. HTF Trend Alignment (0-30 points) ===
            htf_trend = MarketStructure.get_trend_direction(htf_df)
            
            if direction == 'long':
                if htf_trend == 'bullish':
                    # Check strength of trend
                    price = htf_df['close'].iloc[-1]
                    ema_200 = htf_df['ema_200'].iloc[-1]
                    
                    if ema_200 > 0:
                        distance = (price - ema_200) / ema_200
                        
                        if distance > 0.05:  # >5% above EMA200
                            score += 30
                        elif distance > 0.02:  # >2% above
                            score += 20
                        else:
                            score += 15
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
                            score += 30
                        elif distance > 0.02:
                            score += 20
                        else:
                            score += 15
                    else:
                        score += 15
            
            # === 2. Momentum Quality (0-25 points) ===
            macd_hist = primary_df['macd_hist'].tail(3).values
            
            if len(macd_hist) >= 3:
                if direction == 'long':
                    # Accelerating upward momentum
                    if (macd_hist[-1] > macd_hist[-2] > macd_hist[-3] and 
                        macd_hist[-1] > 0):
                        score += 25
                    elif macd_hist[-1] > macd_hist[-2] and macd_hist[-1] > 0:
                        score += 18
                    elif macd_hist[-1] > 0:
                        score += 12
                
                elif direction == 'short':
                    # Accelerating downward momentum
                    if (macd_hist[-1] < macd_hist[-2] < macd_hist[-3] and 
                        macd_hist[-1] < 0):
                        score += 25
                    elif macd_hist[-1] < macd_hist[-2] and macd_hist[-1] < 0:
                        score += 18
                    elif macd_hist[-1] < 0:
                        score += 12
            
            # === 3. Entry Location Quality (0-20 points) ===
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
            
            # === 4. Volatility Suitability (0-15 points) ===
            current_atr = primary_df['atr'].iloc[-1]
            avg_atr = primary_df['atr_sma'].iloc[-1]
            
            if avg_atr > 0:
                atr_ratio = current_atr / avg_atr
                
                if 0.9 <= atr_ratio <= 1.3:  # Normal volatility
                    score += 15
                elif 0.7 <= atr_ratio <= 1.6:
                    score += 10
                elif 0.5 <= atr_ratio <= 2.0:
                    score += 5
            
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