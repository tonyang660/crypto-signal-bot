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
        reason: str
    ) -> bool:
        """Send new signal notification"""
        try:
            # Calculate risk/reward
            risk = abs(entry_price - stop_loss)
            tp1_reward = abs(take_profits['tp1']['price'] - entry_price)
            rr_ratio = tp1_reward / risk if risk > 0 else 0
            
            # Determine color based on direction
            color = 0x00FF00 if direction == 'long' else 0xFF0000  # Green for long, Red for short
            
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
                        "value": f"${position_size['notional_usd']:.2f} ({position_size['leverage']:.1f}×)",
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
                        "value": f"{rr_ratio:.2f}R",
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
        new_stop_loss: float = None
    ) -> bool:
        """Send TP hit notification"""
        try:
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
                    "name": "Remaining Position",
                    "value": f"{remaining_percent}%",
                    "inline": True
                }
            ]
            
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
        total_pnl: float
    ) -> bool:
        """Send stop loss hit notification"""
        try:
            embed = {
                "title": f"🛑 STOP LOSS HIT - {symbol}",
                "color": 0xFF0000,  # Red
                "fields": [
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
                        "name": "Total PnL",
                        "value": f"${total_pnl:+.2f}",
                        "inline": False
                    }
                ],
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
    
    def send_order_filled(self, symbol: str, fill_data: Dict) -> bool:
        """Send order fill notification for paper trading"""
        try:
            embed = {
                "title": f"✅ Order Filled - {symbol}",
                "color": 0x00FF00 if fill_data['side'] == 'long' else 0xFF0000,
                "fields": [
                    {
                        "name": "📊 Execution Type",
                        "value": f"Paper Trading ({fill_data.get('fee_type', 'market')})",
                        "inline": True
                    },
                    {
                        "name": "💰 Fill Price",
                        "value": self._format_price(fill_data['fill_price']),
                        "inline": True
                    },
                    {
                        "name": "📏 Position Size",
                        "value": f"${fill_data['size']:,.2f}",
                        "inline": True
                    },
                    {
                        "name": "💸 Fee",
                        "value": f"${fill_data['fee']:.2f} ({fill_data['fee_rate']*100:.2f}%)",
                        "inline": True
                    },
                    {
                        "name": "📈 Slippage",
                        "value": f"{fill_data['slippage']*100:.3f}%",
                        "inline": True
                    },
                    {
                        "name": "⚡ Leverage",
                        "value": f"{fill_data['leverage']}×",
                        "inline": True
                    }
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {"embeds": [embed]}
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Error sending order filled notification: {e}")
            return False
    
    def send_exit_notification(self, symbol: str, exit_type: str, exit_data: Dict, signal: Dict) -> bool:
        """Send position exit notification for paper trading"""
        try:
            # Determine title and color based on exit type
            if exit_type == 'liquidation':
                title = f"💀 LIQUIDATED - {symbol}"
                color = 0x000000  # Black
            elif exit_type == 'stop_loss':
                title = f"🛑 Stop Loss Hit - {symbol}"
                color = 0xFF0000  # Red
            else:  # TP1, TP2, TP3
                title = f"🎯 {exit_type.upper()} Hit - {symbol}"
                color = 0x00FF00  # Green
            
            # Calculate total P&L including fees
            total_pnl = exit_data['realized_pnl']
            pnl_emoji = "💚" if total_pnl > 0 else "❤️"
            
            fields = [
                {
                    "name": "💰 Exit Price",
                    "value": self._format_price(exit_data['exit_price']),
                    "inline": True
                },
                {
                    "name": "📊 Closed",
                    "value": f"{exit_data['percent_closed']}%",
                    "inline": True
                },
                {
                    "name": f"{pnl_emoji} P&L",
                    "value": f"${total_pnl:+,.2f}",
                    "inline": True
                }
            ]
            
            # Add fee and slippage if applicable
            if exit_data.get('fee', 0) > 0:
                fields.append({
                    "name": "💸 Fee",
                    "value": f"${exit_data['fee']:.2f}",
                    "inline": True
                })
            
            if exit_data.get('slippage', 0) > 0:
                fields.append({
                    "name": "📉 Slippage",
                    "value": f"{exit_data['slippage']*100:.2f}%",
                    "inline": True
                })
            
            # Add remaining position info
            remaining = signal.get('remaining_percent', 0)
            if remaining > 0:
                fields.append({
                    "name": "📦 Remaining",
                    "value": f"{remaining}% still open",
                    "inline": False
                })
            
            # Add total realized P&L
            total_realized = signal.get('realized_pnl', 0)
            total_fees = signal.get('fees_paid', 0)
            if total_realized != 0:
                fields.append({
                    "name": "💰 Total Realized P&L",
                    "value": f"${total_realized:+,.2f} (Fees: ${total_fees:.2f})",
                    "inline": False
                })
            
            embed = {
                "title": title,
                "color": color,
                "fields": fields,
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {"embeds": [embed]}
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Error sending exit notification: {e}")
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