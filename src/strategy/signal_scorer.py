import pandas as pd
from typing import Dict, Tuple
from loguru import logger
from src.strategy.regime_algorithm_manager import MarketRegime, RegimeAlgorithmManager
from src.strategy.regime_scorers import HVScorer, IQScorer, CSScorer

class SignalScorer:
    """
    Multi-Regime Signal Scorer
    
    Routes scoring to regime-specific algorithms (HV/IQ/CS) based on market conditions.
    Each regime has custom weights and logic optimized for that market environment.
    """
    
    @staticmethod
    def calculate_score(
        data: Dict[str, pd.DataFrame],
        direction: str,
        regime: MarketRegime
    ) -> int:
        """
        Calculate signal quality score using regime-specific algorithm.
        
        Args:
            data: Multi-timeframe data dict
            direction: 'long' or 'short'
            regime: Current market regime (HV/IQ/CS)
            
        Returns:
            Score from 0-100
        """
        try:
            # Route to appropriate regime scorer
            if regime == MarketRegime.HV:
                score, _ = HVScorer.calculate_score(data, direction)
            elif regime == MarketRegime.IQ:
                score, _ = IQScorer.calculate_score(data, direction)
            else:  # MarketRegime.CS
                score, _ = CSScorer.calculate_score(data, direction)
            
            return min(score, 100)
            
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
        symbol: str,
        regime: MarketRegime
    ) -> Tuple[int, Dict]:
        """
        Calculate signal quality score with detailed breakdown using regime algorithm.
        
        Args:
            data: Multi-timeframe data dict
            direction: 'long' or 'short'
            symbol: Trading pair symbol
            regime: Current market regime (HV/IQ/CS)
            
        Returns:
            Tuple of (score, breakdown_dict)
        """
        try:
            # Get regime config for logging
            if regime == MarketRegime.HV:
                score, breakdown = HVScorer.calculate_score(data, direction)
                config = HVScorer.get_config()
            elif regime == MarketRegime.IQ:
                score, breakdown = IQScorer.calculate_score(data, direction)
                config = IQScorer.get_config()
            else:  # MarketRegime.CS
                score, breakdown = CSScorer.calculate_score(data, direction)
                config = CSScorer.get_config()
            
            # Log detailed breakdown
            logger.info(f"📊 {symbol} {direction.upper()} | Regime: {regime.value} ({config['description']})")
            logger.info(f"  HTF Alignment:   {breakdown.get('htf_alignment', 0):2d}/30")
            logger.info(f"  Momentum (MACD): {breakdown.get('momentum', 0):2d}/20")
            logger.info(f"  RSI Quality:     {breakdown.get('rsi', 0):2d}/15")
            logger.info(f"  Entry Location:  {breakdown.get('entry_location', 0):2d}/15")
            logger.info(f"  Break Structure: {breakdown.get('break_structure', 0):2d}/15")
            logger.info(f"  Vol & Volume:    {breakdown.get('volatility_volume', 0):2d}/5")
            logger.info(f"  TOTAL SCORE:     {score}/100 (Threshold: {config['threshold']})")
            
            return score, breakdown
            
        except Exception as e:
            logger.error(f"Error calculating signal score with breakdown: {e}")
            return 0, {}
    
    @staticmethod
    def get_regime_config(regime: MarketRegime) -> Dict:
        """
        Get configuration for a specific regime.
        
        Args:
            regime: Market regime (HV/IQ/CS)
            
        Returns:
            Dict with threshold, tp_ratios, sl_multiplier, position_multiplier
        """
        if regime == MarketRegime.HV:
            return HVScorer.get_config()
        elif regime == MarketRegime.IQ:
            return IQScorer.get_config()
        else:  # MarketRegime.CS
            return CSScorer.get_config()
