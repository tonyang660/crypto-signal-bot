from typing import Dict
from loguru import logger
from src.core.config import Config

class PositionSizer:
    """Calculate position size intelligently based on market conditions and trade timeframe"""
    
    @staticmethod
    def _determine_leverage_for_stop(stop_distance_pct: float) -> float:
        """
        Determine optimal isolated leverage based on stop tightness
        
        Tighter stops = shorter timeframes = higher leverage
        Wider stops = longer timeframes = lower leverage
        
        Stop Distance → Trade Duration → Leverage
        < 1%   → Intraday scalp    → 10-12x
        1-2%   → 1 day swing       → 7-10x
        2-3%   → 1-2 day position  → 6-8x
        3-4%   → 2-3 day position  → 5-7x
        > 4%   → Swing trade       → 5x minimum
        """
        stop_pct = stop_distance_pct * 100  # Convert to percentage
        
        if stop_pct < 1.0:
            # Very tight stop - intraday scalp - use high leverage
            return 11.0
        elif stop_pct < 1.5:
            # Tight stop - quick 1 day trade
            return 9.0
        elif stop_pct < 2.5:
            # Normal stop - 1-2 day trade
            return 7.0
        elif stop_pct < 3.5:
            # Wider stop - 2 day position
            return 6.0
        else:
            # Wide stop - longer swing trade
            return 5.0
    
    @staticmethod
    def calculate_position_size(
        account_equity: float,
        entry_price: float,
        stop_loss: float,
        symbol: str,
        available_margin: float = None
    ) -> Dict:
        """
        Calculate position size intelligently with dynamic leverage
        
        Strategy:
        1. Determine stop distance (market risk)
        2. Select leverage based on implied trade duration from stop tightness
        3. Calculate position size to risk $20
        4. Apply isolated leverage to minimize margin per position
        5. Allow multiple concurrent positions without using full margin
        6. Resize if insufficient margin available
        
        Dynamic Leverage Logic:
        - Tight stops (< 1%) suggest intraday/scalp → 10-12x leverage
        - Normal stops (1-2.5%) suggest 1-2 day trade → 7-9x leverage
        - Wide stops (> 3%) suggest swing trade → 5-6x leverage
        
        Args:
            available_margin: Optional margin available for new position (if tracking total exposure)
        
        Returns:
            Dict with contracts, notional value, leverage, risk amount, margin used
        """
        try:
            # Fixed risk per trade (1% = $20 for $2000 account)
            risk_amount = account_equity * Config.RISK_PER_TRADE
            
            # Stop distance as percentage (market risk)
            stop_distance_pct = abs(entry_price - stop_loss) / entry_price
            
            if stop_distance_pct == 0:
                logger.error("Stop distance is zero - cannot calculate position size")
                return {}
            
            # Calculate position size to risk exactly $20
            position_size_usd = risk_amount / stop_distance_pct
            
            # Determine optimal leverage based on stop tightness (trade timeframe)
            isolated_leverage = PositionSizer._determine_leverage_for_stop(stop_distance_pct)
            
            # Cap at exchange maximum
            if isolated_leverage > Config.MAX_LEVERAGE:
                isolated_leverage = Config.MAX_LEVERAGE
                logger.warning(f"{symbol}: Capping leverage at {Config.MAX_LEVERAGE}×")
            
            # Calculate margin required for this position
            margin_required = position_size_usd / isolated_leverage
            margin_percent = (margin_required / account_equity) * 100
            
            # Check if we need to resize based on available margin
            if available_margin is not None and margin_required > available_margin:
                logger.warning(f"{symbol}: Insufficient margin! Need ${margin_required:.2f}, available ${available_margin:.2f}")
                
                # Resize position to fit available margin
                # Keep the same leverage, just reduce position size
                position_size_usd = available_margin * isolated_leverage
                margin_required = available_margin
                margin_percent = (margin_required / account_equity) * 100
                
                # Recalculate risk (will be less than target $20)
                risk_amount = position_size_usd * stop_distance_pct
                
                logger.info(f"{symbol}: Position resized to ${position_size_usd:.2f} | Risk reduced to ${risk_amount:.2f}")
            
            # Sanity check: if single position requires >40% margin, INCREASE leverage to reduce margin
            # (This happens with very tight stops that create large positions)
            if margin_percent > 40:
                # Increase leverage to bring margin down to 40% of account
                isolated_leverage = position_size_usd / (account_equity * 0.40)
                
                # Cap at exchange maximum
                if isolated_leverage > Config.MAX_LEVERAGE:
                    isolated_leverage = Config.MAX_LEVERAGE
                    logger.warning(f"{symbol}: Hit max leverage {Config.MAX_LEVERAGE}×, margin will be {(position_size_usd / isolated_leverage / account_equity * 100):.1f}%")
                
                margin_required = position_size_usd / isolated_leverage
                margin_percent = (margin_required / account_equity) * 100
                logger.info(f"{symbol}: Increased leverage to {isolated_leverage:.1f}× to reduce margin to {margin_percent:.1f}%")
            
            # Calculate contracts
            contracts = position_size_usd / entry_price
            
            # Determine trade timeframe description
            stop_pct = stop_distance_pct * 100
            if stop_pct < 1.0:
                timeframe = "intraday scalp"
            elif stop_pct < 2.5:
                timeframe = "1-day swing"
            elif stop_pct < 3.5:
                timeframe = "1-2 day position"
            else:
                timeframe = "2+ day swing"
            
            logger.info(f"{symbol}: {timeframe.upper()} | Position ${position_size_usd:.2f} @ {isolated_leverage:.1f}× | "
                       f"Margin: ${margin_required:.2f} ({margin_percent:.1f}%) | "
                       f"Risk: ${risk_amount:.2f} | Stop: {stop_distance_pct*100:.2f}%")
            
            return {
                'contracts': round(contracts, 6),
                'notional_usd': round(position_size_usd, 2),
                'leverage': round(isolated_leverage, 2),
                'risk_usd': round(risk_amount, 2),
                'margin_used': round(margin_required, 2),
                'margin_percent': round(margin_percent, 2),
                'stop_distance_pct': round(stop_distance_pct * 100, 2),
                'stop_distance_usd': round(abs(entry_price - stop_loss) * contracts, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return {}
    
    @staticmethod
    def validate_position_size(position_data: Dict, market_info: Dict) -> bool:
        """
        Validate position size against market constraints
        
        Checks:
        - Minimum order size
        - Maximum order size
        - Minimum notional value
        """
        try:
            contracts = position_data.get('contracts', 0)
            notional = position_data.get('notional_usd', 0)
            
            min_size = market_info.get('min_order_size') or 0
            max_size = market_info.get('max_order_size') or float('inf')
            min_notional = market_info.get('min_notional') or 0
            
            if contracts < min_size:
                logger.warning(f"Position size {contracts} below minimum {min_size}")
                return False
            
            if contracts > max_size:
                logger.warning(f"Position size {contracts} exceeds maximum {max_size}")
                return False
            
            if notional < min_notional:
                logger.warning(f"Notional value ${notional} below minimum ${min_notional}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating position size: {e}")
            return False