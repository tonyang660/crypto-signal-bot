"""
Margin and Leverage Calculator

Handles position margin requirements, liquidation prices,
and margin availability checks for paper trading.
"""

from typing import Dict
from loguru import logger


class MarginCalculator:
    """
    Calculate margin requirements and liquidation prices for leveraged positions
    following BitGet perpetual futures margin system.
    """
    
    # BitGet maintenance margin rates (approximate, varies by symbol)
    MAINTENANCE_MARGIN_RATES = {
        'default': 0.005,  # 0.5% for most pairs
        'BTCUSDT': 0.004,  # 0.4% for BTC
        'ETHUSDT': 0.005,  # 0.5% for ETH
    }
    
    def __init__(self):
        """Initialize margin calculator"""
        logger.debug("💰 Margin Calculator initialized")
    
    def calculate_position_margin(self, entry_price: float, size_usd: float, 
                                  leverage: float) -> float:
        """
        Calculate required margin (initial margin) for a position
        
        Args:
            entry_price: Entry price per unit
            size_usd: Position size in USD
            leverage: Leverage multiplier (e.g., 10 for 10×)
            
        Returns:
            margin_required: Dollar amount of margin needed
            
        Example:
            $10,000 position with 10× leverage = $1,000 margin required
        """
        if leverage <= 0:
            raise ValueError(f"Invalid leverage: {leverage}")
        
        margin_required = size_usd / leverage
        
        return margin_required
    
    def calculate_liquidation_price(self, entry_price: float, leverage: float, 
                                    side: str, symbol: str = 'default') -> float:
        """
        Calculate liquidation price for a leveraged position
        
        Args:
            entry_price: Entry price of position
            leverage: Leverage used (e.g., 10 for 10×)
            side: 'long' or 'short'
            symbol: Trading pair symbol for maintenance margin lookup
            
        Returns:
            liquidation_price: Price at which position gets liquidated
            
        Formula:
            Long: liq_price = entry * (1 - (1/leverage) + maintenance_margin)
            Short: liq_price = entry * (1 + (1/leverage) - maintenance_margin)
        """
        if leverage <= 0:
            raise ValueError(f"Invalid leverage: {leverage}")
        
        # Get maintenance margin rate for symbol
        maintenance_margin = self.MAINTENANCE_MARGIN_RATES.get(
            symbol, 
            self.MAINTENANCE_MARGIN_RATES['default']
        )
        
        if side == 'long':
            # Long liquidates when price drops
            # liq_price = entry * (1 - (1/leverage) + maintenance_margin)
            liquidation_price = entry_price * (1 - (1/leverage) + maintenance_margin)
        elif side == 'short':
            # Short liquidates when price rises
            # liq_price = entry * (1 + (1/leverage) - maintenance_margin)
            liquidation_price = entry_price * (1 + (1/leverage) - maintenance_margin)
        else:
            raise ValueError(f"Invalid side: {side}")
        
        return liquidation_price
    
    def check_margin_sufficient(self, total_equity: float, 
                               open_positions: list, 
                               new_position_margin: float) -> bool:
        """
        Check if account has sufficient margin for new position
        
        Args:
            total_equity: Total account equity (balance + unrealized PnL)
            open_positions: List of open position dicts with 'margin_used'
            new_position_margin: Margin required for new position
            
        Returns:
            sufficient: True if enough margin available
        """
        # Calculate used margin from open positions
        used_margin = sum(pos.get('margin_used', 0) for pos in open_positions)
        
        # Available margin
        available_margin = total_equity - used_margin
        
        # Check if sufficient (keep 5% buffer)
        sufficient = available_margin >= (new_position_margin * 1.05)
        
        if not sufficient:
            logger.warning(f"⚠️ Insufficient margin: Available ${available_margin:.2f}, "
                          f"Required ${new_position_margin:.2f}")
        
        return sufficient
    
    def calculate_max_position_size(self, available_equity: float, 
                                    leverage: float) -> float:
        """
        Calculate maximum position size given available equity and leverage
        
        Args:
            available_equity: Available equity for margin
            leverage: Desired leverage
            
        Returns:
            max_size: Maximum position size in USD
        """
        max_size = available_equity * leverage
        return max_size
    
    def get_liquidation_distance(self, entry_price: float, 
                                 liquidation_price: float, 
                                 side: str) -> float:
        """
        Calculate percentage distance to liquidation
        
        Args:
            entry_price: Entry price
            liquidation_price: Liquidation price
            side: 'long' or 'short'
            
        Returns:
            distance_pct: Percentage distance (positive value)
        """
        if side == 'long':
            distance_pct = ((entry_price - liquidation_price) / entry_price) * 100
        else:  # short
            distance_pct = ((liquidation_price - entry_price) / entry_price) * 100
        
        return abs(distance_pct)
    
    def calculate_bankruptcy_price(self, entry_price: float, leverage: float, 
                                   side: str) -> float:
        """
        Calculate bankruptcy price (100% loss of margin)
        
        Args:
            entry_price: Entry price
            leverage: Leverage used
            side: 'long' or 'short'
            
        Returns:
            bankruptcy_price: Price at 100% margin loss
        """
        if side == 'long':
            bankruptcy_price = entry_price * (1 - 1/leverage)
        else:  # short
            bankruptcy_price = entry_price * (1 + 1/leverage)
        
        return bankruptcy_price
    
    def get_position_risk_metrics(self, entry_price: float, current_price: float,
                                  size_usd: float, leverage: float, 
                                  side: str, symbol: str = 'default') -> Dict:
        """
        Get comprehensive risk metrics for a position
        
        Args:
            entry_price: Entry price
            current_price: Current market price
            size_usd: Position size in USD
            leverage: Leverage multiplier
            side: 'long' or 'short'
            symbol: Trading pair symbol
            
        Returns:
            metrics: Dict with risk data (liq_price, distance, unrealized_pnl, etc.)
        """
        liq_price = self.calculate_liquidation_price(entry_price, leverage, side, symbol)
        bankruptcy_price = self.calculate_bankruptcy_price(entry_price, leverage, side)
        liq_distance = self.get_liquidation_distance(entry_price, liq_price, side)
        
        # Calculate unrealized PnL
        if side == 'long':
            pnl_pct = ((current_price - entry_price) / entry_price) * leverage
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * leverage
        
        unrealized_pnl = size_usd * pnl_pct
        
        # Margin metrics
        margin_used = self.calculate_position_margin(entry_price, size_usd, leverage)
        margin_ratio = (unrealized_pnl / margin_used) if margin_used > 0 else 0
        
        metrics = {
            'liquidation_price': liq_price,
            'bankruptcy_price': bankruptcy_price,
            'liquidation_distance_pct': liq_distance,
            'unrealized_pnl': unrealized_pnl,
            'unrealized_pnl_pct': pnl_pct * 100,
            'margin_used': margin_used,
            'margin_ratio': margin_ratio,
            'leverage': leverage,
            'at_risk': liq_distance < 10  # Flag if within 10% of liquidation
        }
        
        return metrics
