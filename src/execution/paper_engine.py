"""
Paper Trading Execution Engine

Simulates realistic order fills using live BitGet market data.
Handles limit/market orders, slippage, fees, TP/SL tracking.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from loguru import logger
from ..core.bitget_client import BitGetClient
from .margin_calculator import MarginCalculator
from .paper_account import PaperAccount


class PaperTradingEngine:
    """
    Self-hosted paper trading engine that simulates order execution
    using real-time market data from BitGet without placing actual trades.
    """
    
    def __init__(self, bitget_client: BitGetClient, paper_account: PaperAccount):
        """
        Initialize paper trading engine
        
        Args:
            bitget_client: BitGet client for market data
            paper_account: Virtual account for balance tracking
        """
        self.bitget = bitget_client
        self.account = paper_account
        self.margin_calc = MarginCalculator()
        
        # Track pending orders: {order_id: order_data}
        self.pending_orders: Dict[str, Dict] = {}
        
        # BitGet fee structure (perpetual futures)
        self.MAKER_FEE = 0.0002  # 0.02%
        self.TAKER_FEE = 0.0006  # 0.06%
        
        # Slippage parameters
        self.BASE_SLIPPAGE = 0.0003      # 0.03% normal
        self.ELEVATED_SLIPPAGE = 0.0008  # 0.08% high volatility
        self.STOP_SLIPPAGE = 0.0015      # 0.15% stop loss
        
        logger.info("📊 Paper Trading Engine initialized")
    
    def place_limit_order(self, signal: Dict) -> str:
        """
        Place a virtual limit order for signal entry
        
        Args:
            signal: Signal dict with entry_price, direction, position_size, etc.
            
        Returns:
            order_id: Unique identifier for tracking order
        """
        order_id = f"PAPER_{signal['signal_id']}_ENTRY"
        
        order = {
            'order_id': order_id,
            'signal_id': signal['signal_id'],
            'symbol': signal['symbol'],
            'side': signal['direction'],  # 'long' or 'short'
            'order_type': 'limit',
            'limit_price': signal['entry_price'],
            'size': signal['position_size']['notional_usd'],
            'leverage': signal['position_size'].get('leverage', 10),
            'status': 'pending',
            'placed_at': datetime.utcnow().isoformat(),
            'fill_attempts': 0,
            'max_attempts': 6  # 30 minutes at 5-min scans
        }
        
        self.pending_orders[order_id] = order
        
        logger.info(f"📝 Limit order placed: {order['symbol']} {order['side'].upper()} "
                   f"@ ${order['limit_price']:,.2f} | Size: ${order['size']:,.2f}")
        
        return order_id
    
    def place_market_order(self, signal: Dict) -> Tuple[str, Dict]:
        """
        Place and immediately fill a virtual market order
        
        Args:
            signal: Signal dict
            
        Returns:
            order_id, fill_data: Order ID and fill execution details
        """
        ticker = self.bitget.get_ticker(signal['symbol'])
        
        # Market order uses bid/ask with additional slippage
        if signal['direction'] == 'long':
            fill_price = ticker['ask'] * (1 + self.BASE_SLIPPAGE)
        else:  # short
            fill_price = ticker['bid'] * (1 - self.BASE_SLIPPAGE)
        
        order_id = f"PAPER_{signal['signal_id']}_MARKET"
        
        size = signal['position_size']['notional_usd']
        leverage = signal['position_size'].get('leverage', 10)
        
        # Calculate and apply taker fee
        fee_amount = size * self.TAKER_FEE
        self.account.deduct_fees(fee_amount)
        
        fill_data = {
            'order_id': order_id,
            'signal_id': signal['signal_id'],
            'symbol': signal['symbol'],
            'side': signal['direction'],
            'fill_price': fill_price,
            'size': size,
            'leverage': leverage,
            'fee': fee_amount,
            'fee_rate': self.TAKER_FEE,
            'slippage': abs(fill_price - signal['entry_price']) / signal['entry_price'],
            'filled_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Market order filled: {fill_data['symbol']} {fill_data['side'].upper()} "
                   f"@ ${fill_price:,.2f} | Fee: ${fee_amount:.2f} | "
                   f"Slippage: {fill_data['slippage']*100:.3f}%")
        
        return order_id, fill_data
    
    def check_pending_orders(self) -> List[Dict]:
        """
        Check if any pending limit orders should be filled based on current market prices
        
        Returns:
            List of filled order dicts
        """
        filled_orders = []
        orders_to_remove = []
        
        for order_id, order in self.pending_orders.items():
            if order['status'] != 'pending':
                continue
            
            try:
                ticker = self.bitget.get_ticker(order['symbol'])
                order['fill_attempts'] += 1
                
                # Check if limit order would have filled
                filled = False
                fill_price = order['limit_price']
                fee_type = 'maker'  # Assume maker fee for passive fill
                
                if order['side'] == 'long':
                    # Long limit buy fills when ask <= limit price
                    if ticker['ask'] <= order['limit_price']:
                        filled = True
                        # Check if crossed spread (would be taker)
                        if ticker['bid'] < order['limit_price'] <= ticker['ask']:
                            fee_type = 'maker'
                        else:
                            fee_type = 'taker'
                else:  # short
                    # Short limit sell fills when bid >= limit price
                    if ticker['bid'] >= order['limit_price']:
                        filled = True
                        if ticker['ask'] > order['limit_price'] >= ticker['bid']:
                            fee_type = 'maker'
                        else:
                            fee_type = 'taker'
                
                if filled:
                    # Apply appropriate fee
                    fee_rate = self.MAKER_FEE if fee_type == 'maker' else self.TAKER_FEE
                    fee_amount = order['size'] * fee_rate
                    self.account.deduct_fees(fee_amount)
                    
                    fill_data = {
                        'order_id': order_id,
                        'signal_id': order['signal_id'],
                        'symbol': order['symbol'],
                        'side': order['side'],
                        'fill_price': fill_price,
                        'size': order['size'],
                        'leverage': order['leverage'],
                        'fee': fee_amount,
                        'fee_rate': fee_rate,
                        'fee_type': fee_type,
                        'slippage': 0.0,  # Limit filled at exact price
                        'filled_at': datetime.utcnow().isoformat()
                    }
                    
                    filled_orders.append(fill_data)
                    orders_to_remove.append(order_id)
                    
                    logger.info(f"✅ Limit order filled: {fill_data['symbol']} {fill_data['side'].upper()} "
                               f"@ ${fill_price:,.2f} | Fee: ${fee_amount:.2f} ({fee_type})")
                
                # Timeout: cancel and convert to market order
                elif order['fill_attempts'] >= order['max_attempts']:
                    logger.warning(f"⏰ Limit order timeout {order['symbol']} - converting to market order")
                    orders_to_remove.append(order_id)
                    # Caller will handle market order conversion
                    
            except Exception as e:
                logger.error(f"Error checking order {order_id}: {e}")
        
        # Remove filled/cancelled orders
        for order_id in orders_to_remove:
            del self.pending_orders[order_id]
        
        return filled_orders
    
    def add_position(self, fill_data: Dict, signal: Dict) -> Dict:
        """
        Create a virtual position after order fill
        
        Args:
            fill_data: Order fill execution data
            signal: Original signal with SL/TP levels
            
        Returns:
            position: Position dict with all tracking data
        """
        # Calculate liquidation price
        liq_price = self.margin_calc.calculate_liquidation_price(
            fill_data['fill_price'],
            fill_data['leverage'],
            fill_data['side']
        )
        
        # Calculate required margin
        margin_required = self.margin_calc.calculate_position_margin(
            fill_data['fill_price'],
            fill_data['size'],
            fill_data['leverage']
        )
        
        position = {
            'symbol': fill_data['symbol'],
            'signal_id': fill_data['signal_id'],
            'side': fill_data['side'],
            'entry_price': fill_data['fill_price'],
            'size': fill_data['size'],
            'leverage': fill_data['leverage'],
            'margin_used': margin_required,
            'liquidation_price': liq_price,
            'stop_loss': signal['stop_loss'],
            'take_profits': signal['take_profits'],
            'remaining_percent': 100,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'fees_paid': fill_data['fee'],
            'funding_costs': 0.0,
            'entry_slippage': fill_data['slippage'],
            'opened_at': fill_data['filled_at'],
            'last_funding_time': datetime.utcnow().isoformat()
        }
        
        # Update account
        self.account.add_position(position)
        
        logger.info(f"📈 Position opened: {position['symbol']} {position['side'].upper()} "
                   f"${position['size']:,.2f} @ ${position['entry_price']:,.2f} | "
                   f"Leverage: {position['leverage']}× | Liq: ${liq_price:,.2f}")
        
        return position
    
    def check_exit_conditions(self, position: Dict, signal: Dict) -> Optional[Dict]:
        """
        Check if position should exit via TP or SL
        
        Args:
            position: Current position data
            signal: Signal with tracked TP/SL states
            
        Returns:
            exit_data: Dict with exit details if exit triggered, else None
        """
        try:
            ticker = self.bitget.get_ticker(position['symbol'])
            current_price = ticker['last']
            
            # Update unrealized PnL
            position['unrealized_pnl'] = self._calculate_unrealized_pnl(position, current_price)
            
            # Check liquidation first
            if self._check_liquidation(position, current_price):
                return self._execute_liquidation(position, current_price)
            
            # Check stop loss
            if self._check_stop_loss(position, current_price):
                return self._execute_stop_loss(position, ticker)
            
            # Check take profits
            tp_exit = self._check_take_profits(position, signal, ticker)
            if tp_exit:
                return tp_exit
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking exit conditions for {position['symbol']}: {e}")
            return None
    
    def _calculate_unrealized_pnl(self, position: Dict, current_price: float) -> float:
        """Calculate unrealized P&L for position"""
        if position['side'] == 'long':
            pnl = (current_price - position['entry_price']) / position['entry_price']
        else:  # short
            pnl = (position['entry_price'] - current_price) / position['entry_price']
        
        # Apply leverage
        pnl *= position['leverage']
        
        # Calculate dollar amount
        pnl_usd = position['size'] * pnl * (position['remaining_percent'] / 100)
        
        return pnl_usd
    
    def _check_liquidation(self, position: Dict, current_price: float) -> bool:
        """Check if position hit liquidation price"""
        if position['side'] == 'long':
            return current_price <= position['liquidation_price']
        else:  # short
            return current_price >= position['liquidation_price']
    
    def _execute_liquidation(self, position: Dict, current_price: float) -> Dict:
        """Execute position liquidation"""
        loss = position['size'] * (position['remaining_percent'] / 100)
        
        exit_data = {
            'exit_type': 'liquidation',
            'exit_price': position['liquidation_price'],
            'percent_closed': position['remaining_percent'],
            'realized_pnl': -loss,  # Full loss
            'fee': 0.0,  # No fee on liquidation
            'slippage': 0.0,
            'exited_at': datetime.utcnow().isoformat()
        }
        
        # Update account
        self.account.add_realized_pnl(-loss)
        self.account.close_position(position)
        
        logger.error(f"💀 LIQUIDATED: {position['symbol']} @ ${current_price:,.2f} | Loss: ${loss:.2f}")
        
        return exit_data
    
    def _check_stop_loss(self, position: Dict, current_price: float) -> bool:
        """Check if stop loss was hit"""
        if position['side'] == 'long':
            return current_price <= position['stop_loss']
        else:  # short
            return current_price >= position['stop_loss']
    
    def _execute_stop_loss(self, position: Dict, ticker: Dict) -> Dict:
        """Execute stop loss exit"""
        # Stop losses fill as market orders with slippage
        if position['side'] == 'long':
            # Selling to close long
            exit_price = ticker['bid'] * (1 - self.STOP_SLIPPAGE)
        else:  # short
            # Buying to close short
            exit_price = ticker['ask'] * (1 + self.STOP_SLIPPAGE)
        
        # Calculate P&L
        if position['side'] == 'long':
            pnl_pct = (exit_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - exit_price) / position['entry_price']
        
        pnl_pct *= position['leverage']
        pnl_usd = position['size'] * pnl_pct * (position['remaining_percent'] / 100)
        
        # Apply taker fee
        close_size = position['size'] * (position['remaining_percent'] / 100)
        fee = close_size * self.TAKER_FEE
        self.account.deduct_fees(fee)
        
        exit_data = {
            'exit_type': 'stop_loss',
            'exit_price': exit_price,
            'percent_closed': position['remaining_percent'],
            'realized_pnl': pnl_usd - fee,
            'fee': fee,
            'slippage': self.STOP_SLIPPAGE,
            'exited_at': datetime.utcnow().isoformat()
        }
        
        # Update account
        self.account.add_realized_pnl(pnl_usd - fee)
        self.account.close_position(position)
        
        logger.warning(f"🛑 Stop Loss: {position['symbol']} @ ${exit_price:,.2f} | "
                      f"P&L: ${pnl_usd-fee:.2f} | Fee: ${fee:.2f}")
        
        return exit_data
    
    def _check_take_profits(self, position: Dict, signal: Dict, ticker: Dict) -> Optional[Dict]:
        """Check and execute take profit levels"""
        take_profits = signal.get('take_profits', {})
        
        # Check each TP level that hasn't been hit
        for tp_level in ['tp1', 'tp2', 'tp3']:
            if signal.get(f'{tp_level}_hit', False):
                continue  # Already hit
            
            tp_data = take_profits.get(tp_level)
            if not tp_data:
                continue
            
            tp_price = tp_data['price']
            tp_percent = tp_data['percent']
            
            # Check if TP hit
            tp_hit = False
            if position['side'] == 'long':
                tp_hit = ticker['bid'] >= tp_price
            else:  # short
                tp_hit = ticker['ask'] <= tp_price
            
            if tp_hit:
                return self._execute_take_profit(position, tp_price, tp_percent, tp_level)
        
        return None
    
    def _execute_take_profit(self, position: Dict, tp_price: float, 
                            tp_percent: float, tp_level: str) -> Dict:
        """Execute take profit exit"""
        # TP fills as limit order (maker fee)
        exit_price = tp_price
        
        # Calculate P&L for this portion
        if position['side'] == 'long':
            pnl_pct = (exit_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - exit_price) / position['entry_price']
        
        pnl_pct *= position['leverage']
        
        # Calculate for portion being closed
        close_size = position['size'] * (tp_percent / 100)
        pnl_usd = close_size * pnl_pct
        
        # Apply maker fee
        fee = close_size * self.MAKER_FEE
        self.account.deduct_fees(fee)
        
        exit_data = {
            'exit_type': tp_level,
            'exit_price': exit_price,
            'percent_closed': tp_percent,
            'realized_pnl': pnl_usd - fee,
            'fee': fee,
            'slippage': 0.0,  # Limit order filled at exact price
            'exited_at': datetime.utcnow().isoformat()
        }
        
        # Update account
        self.account.add_realized_pnl(pnl_usd - fee)
        
        # Update position remaining percent
        position['remaining_percent'] -= tp_percent
        position['realized_pnl'] += (pnl_usd - fee)
        position['fees_paid'] += fee
        
        # If fully closed, remove position
        if position['remaining_percent'] <= 0:
            self.account.close_position(position)
        
        logger.info(f"🎯 {tp_level.upper()}: {position['symbol']} @ ${exit_price:,.2f} | "
                   f"Closed {tp_percent}% | P&L: ${pnl_usd-fee:.2f} | Fee: ${fee:.2f}")
        
        return exit_data
    
    def apply_funding_rate(self, position: Dict) -> float:
        """
        Apply perpetual futures funding rate to position
        
        Args:
            position: Position dict
            
        Returns:
            funding_cost: Dollar amount deducted/added
        """
        try:
            funding_rate = self.bitget.get_funding_rate(position['symbol'])
            
            # Calculate funding cost (negative = pay, positive = receive)
            position_value = position['size'] * (position['remaining_percent'] / 100)
            funding_cost = position_value * funding_rate
            
            # Deduct from account
            self.account.deduct_funding(funding_cost)
            
            # Update position tracking
            position['funding_costs'] += funding_cost
            position['last_funding_time'] = datetime.utcnow().isoformat()
            
            logger.debug(f"💸 Funding applied: {position['symbol']} | "
                        f"Rate: {funding_rate*100:.4f}% | Cost: ${funding_cost:.2f}")
            
            return funding_cost
            
        except Exception as e:
            logger.error(f"Error applying funding rate for {position['symbol']}: {e}")
            return 0.0
    
    def get_pending_orders(self) -> Dict[str, Dict]:
        """Get all pending orders"""
        return self.pending_orders
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        if order_id in self.pending_orders:
            order = self.pending_orders[order_id]
            logger.info(f"❌ Order cancelled: {order['symbol']} {order['side']} @ ${order['limit_price']:,.2f}")
            del self.pending_orders[order_id]
            return True
        return False
