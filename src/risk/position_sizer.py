from typing import Dict
from loguru import logger
from src.core.config import Config

class PositionSizer:
    """Calculate position size based on risk parameters"""
    
    @staticmethod
    def calculate_position_size(
        account_equity: float,
        entry_price: float,
        stop_loss: float,
        symbol: str
    ) -> Dict:
        """
        Calculate position size based on fixed risk
        
        Formula:
        Position Size = (Account Equity × Risk %) / Stop Distance %
        
        Returns:
            Dict with contracts, notional value, leverage, risk amount
        """
        try:
            # Risk amount in dollars
            risk_amount = account_equity * Config.RISK_PER_TRADE
            
            # Stop distance as percentage
            stop_distance_pct = abs(entry_price - stop_loss) / entry_price
            
            if stop_distance_pct == 0:
                logger.error("Stop distance is zero - cannot calculate position size")
                return {}
            
            # Position size in dollars
            position_size_usd = risk_amount / stop_distance_pct
            
            # Calculate contracts (number of coins)
            contracts = position_size_usd / entry_price
            
            # Effective leverage
            effective_leverage = position_size_usd / account_equity
            
            # Cap leverage at maximum
            if effective_leverage > Config.MAX_LEVERAGE:
                logger.warning(f"Leverage {effective_leverage:.2f}× exceeds max {Config.MAX_LEVERAGE}×, capping position")
                position_size_usd = account_equity * Config.MAX_LEVERAGE
                contracts = position_size_usd / entry_price
                effective_leverage = Config.MAX_LEVERAGE
            
            return {
                'contracts': round(contracts, 6),
                'notional_usd': round(position_size_usd, 2),
                'leverage': round(effective_leverage, 2),
                'risk_usd': round(risk_amount, 2),
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