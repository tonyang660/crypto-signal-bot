import requests
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
from src.core.config import Config

class DiscordNotifier:
    """Send trading signals and alerts via Discord webhook"""
    
    def __init__(self):
        self.webhook_url = Config.DISCORD_WEBHOOK_URL
    
    @staticmethod
    def _format_price(price: float) -> str:
        """Format price with appropriate decimal places based on magnitude"""
        if price >= 1000:
            return f"${price:,.2f}"  # BTC: $95,432.50
        elif price >= 10:
            return f"${price:.3f}"    # ETH: $3,234.567
        elif price >= 1:
            return f"${price:.4f}"     # SOL: $123.4567
        elif price >= 0.01:
            return f"${price:.5f}"     # DOGE: $0.12345
        else:
            return f"${price:.8f}"     # SHIB: $0.00001234
    
    def send_new_signal(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profits: Dict,
        position_size: Dict,
        score: int,
        reason: str,
        rr: float = 0.0,
        execution_costs: Dict = None
    ) -> bool:
        """Send new signal notification"""
        try:
            # Calculate risk/reward if not provided
            if rr == 0.0:
                risk = abs(entry_price - stop_loss)
                tp1_reward = abs(take_profits['tp1']['price'] - entry_price)
                rr_ratio = tp1_reward / risk if risk > 0 else 0
            else:
                rr_ratio = rr
            
            # Extract base asset and contracts
            base_asset = symbol[:-4]  # Remove USDT
            contracts = position_size.get('contracts', 0)
            
            # Determine color based on direction
            color = 0x00FF00 if direction == 'long' else 0xFF0000  # Green for long, Red for short
            execution_costs = execution_costs or {}
            
            # Create embed
            embed = {
                "title": f"🚀 NEW {direction.upper()} SIGNAL - {symbol}",
                "color": color,
                "fields": [
                    {
                        "name": "📊 Signal Quality",
                        "value": f"Score: **{score}/100** ({self._get_grade(score)})",
                        "inline": True
                    },
                    {
                        "name": "💰 Position Size",
                        "value": f"{contracts:.4f} {base_asset} (${position_size['notional_usd']:.2f} @ {position_size['leverage']:.1f}×)",
                        "inline": True
                    },
                    {
                        "name": "💵 Margin Used",
                        "value": f"${position_size.get('margin_used', 0):.2f} ({position_size.get('margin_percent', 0):.1f}%)",
                        "inline": True
                    },
                    {
                        "name": "📍 Entry",
                        "value": self._format_price(entry_price),
                        "inline": False
                    },
                    {
                        "name": "🛑 Stop Loss",
                        "value": f"{self._format_price(stop_loss)} (-{position_size['stop_distance_pct']:.2f}%)",
                        "inline": True
                    },
                    {
                        "name": "⚖️ Risk/Reward",
                        "value": f"**{rr_ratio:.2f}R**",
                        "inline": True
                    },
                    {
                        "name": "🎯 Take Profit 1",
                        "value": f"{self._format_price(take_profits['tp1']['price'])} (Close {take_profits['tp1']['close_percent']}%)",
                        "inline": False
                    },
                    {
                        "name": "🎯 Take Profit 2",
                        "value": f"{self._format_price(take_profits['tp2']['price'])} (Close {take_profits['tp2']['close_percent']}%)",
                        "inline": True
                    },
                    {
                        "name": "🎯 Take Profit 3",
                        "value": f"{self._format_price(take_profits['tp3']['price'])} (Trail {take_profits['tp3']['close_percent']}%)",
                        "inline": True
                    },
                    {
                        "name": "📝 Entry Reason",
                        "value": f"```{reason}```",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"BitGet Futures • Risk: ${position_size['risk_usd']:.2f}"
                },
                "timestamp": datetime.now().isoformat()
            }
            embed["fields"].append({
                "name": "Execution Costs",
                "value": (
                    f"Entry fee: ${execution_costs.get('entry_fee', 0):.2f}\n"
                    f"Spread cost: ${execution_costs.get('entry_spread_cost', 0):.2f}\n"
                    f"Total fees: ${execution_costs.get('total_fees', 0):.2f}"
                ),
                "inline": False
            })
            
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(self.webhook_url, json=payload)
            
            if response.status_code == 204:
                logger.info(f"✅ Discord notification sent for {symbol}")
                return True
            else:
                logger.error(f"Failed to send Discord notification: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
            return False
    
    def send_tp_hit(
        self,
        symbol: str,
        direction: str,
        tp_level: str,
        price: float,
        pnl: float,
        total_pnl: float,
        remaining_percent: int,
        new_stop_loss: float = None,
        contracts_remaining: float = None,
        contracts_closed: float = None,
        close_percent: float = None,
        exit_fee: float = None,
        total_fees: float = None,
        spread_cost: float = None,
        total_spread_cost: float = None
    ) -> bool:
        """Send TP hit notification"""
        try:
            base_asset = symbol[:-4]  # Remove USDT
            
            fields = [
                {
                    "name": "Direction",
                    "value": direction.upper(),
                    "inline": True
                },
                {
                    "name": "Exit Price",
                    "value": self._format_price(price),
                    "inline": True
                },
                {
                    "name": "Partial PnL",
                    "value": f"${pnl:+.2f}",
                    "inline": True
                },
                {
                    "name": "Total PnL",
                    "value": f"${total_pnl:+.2f}",
                    "inline": True
                },
                {
                    "name": "Closed",
                    "value": f"{contracts_closed:.4f} {base_asset} ({close_percent:.1f}%)" if contracts_closed is not None else f"{close_percent:.1f}%" if close_percent is not None else "N/A",
                    "inline": True
                },
                {
                    "name": "Remaining Position",
                    "value": f"{contracts_remaining:.4f} {base_asset} ({remaining_percent:.1f}%)" if contracts_remaining is not None else f"{remaining_percent:.1f}%",
                    "inline": True
                }
            ]
            fields.append({
                "name": "Fees",
                "value": f"Exit: ${exit_fee or 0:.2f}\nTotal: ${total_fees or 0:.2f}",
                "inline": True
            })
            fields.append({
                "name": "Spread Cost",
                "value": f"Exit: ${spread_cost or 0:.2f}\nTotal: ${total_spread_cost or 0:.2f}",
                "inline": True
            })
            
            # Add new stop loss if it was adjusted
            if new_stop_loss is not None:
                fields.append({
                    "name": "🛡️ New Stop Loss",
                    "value": self._format_price(new_stop_loss),
                    "inline": True
                })
            
            embed = {
                "title": f"🎯 {tp_level.upper()} HIT - {symbol}",
                "color": 0xFFD700,  # Gold
                "fields": fields,
                "footer": {
                    "text": "BitGet Futures Signal Bot"
                },
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {"embeds": [embed]}
            
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Error sending TP notification: {e}")
            return False
    
    def send_stop_hit(
        self,
        symbol: str,
        direction: str,
        price: float,
        total_pnl: float,
        contracts_closed: float = None,
        remaining_percent: float = None,
        exit_fee: float = None,
        total_fees: float = None,
        spread_cost: float = None,
        total_spread_cost: float = None
    ) -> bool:
        """Send stop loss hit notification"""
        try:
            base_asset = symbol[:-4]  # Remove USDT
            
            fields = [
                {
                    "name": "Direction",
                    "value": direction.upper(),
                    "inline": True
                },
                {
                    "name": "Exit Price",
                    "value": self._format_price(price),
                    "inline": True
                },
                {
                    "name": "Closed",
                    "value": f"{contracts_closed:.4f} {base_asset} ({remaining_percent:.1f}%)" if contracts_closed is not None else "N/A",
                    "inline": True
                },
                {
                    "name": "Total PnL",
                    "value": f"${total_pnl:+.2f}",
                    "inline": False
                }
            ]
            fields.append({
                "name": "Fees",
                "value": f"Exit: ${exit_fee or 0:.2f}\nTotal: ${total_fees or 0:.2f}",
                "inline": True
            })
            fields.append({
                "name": "Spread Cost",
                "value": f"Exit: ${spread_cost or 0:.2f}\nTotal: ${total_spread_cost or 0:.2f}",
                "inline": True
            })
            
            embed = {
                "title": f"🛑 STOP LOSS HIT - {symbol}",
                "color": 0xFF0000,  # Red
                "fields": fields,
                "footer": {
                    "text": "BitGet Futures Signal Bot"
                },
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {"embeds": [embed]}
            
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Error sending stop loss notification: {e}")
            return False
    
    def send_status_update(
        self,
        message: str,
        stats: Optional[Dict] = None
    ) -> bool:
        """Send general status update"""
        try:
            fields = []
            
            if stats:
                fields = [
                    {
                        "name": "Equity",
                        "value": f"${stats.get('equity', 0):.2f}",
                        "inline": True
                    },
                    {
                        "name": "Daily PnL",
                        "value": f"${stats.get('daily_pnl', 0):+.2f}",
                        "inline": True
                    },
                    {
                        "name": "Win Rate",
                        "value": f"{stats.get('win_rate', 0):.1f}%",
                        "inline": True
                    }
                ]
            
            embed = {
                "title": "📊 Bot Status Update",
                "description": message,
                "color": 0x3498DB,  # Blue
                "fields": fields,
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {"embeds": [embed]}
            
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Error sending status update: {e}")
            return False
    
    def send_error(self, error_message: str) -> bool:
        """Send error notification"""
        try:
            embed = {
                "title": "⚠️ Bot Error",
                "description": f"```{error_message}```",
                "color": 0xFF0000,
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {"embeds": [embed]}
            
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
            return False
    
    def _get_grade(self, score: int) -> str:
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
