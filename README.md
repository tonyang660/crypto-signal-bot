# BitGet Futures Signal Bot

Automated trading signal bot for BitGet perpetual futures, designed for 10-15× leverage trading with strict risk management.

## Features

- ✅ Multi-timeframe analysis (4H, 15M, 5M)
- ✅ Technical indicator-based entries (EMA, MACD, ATR, RSI)
- ✅ Signal quality scoring (0-100)
- ✅ Automated stop loss & take profit calculation
- ✅ Position sizing based on fixed risk (1% per trade)
- ✅ Daily & weekly loss limits
- ✅ Discord webhook notifications
- ✅ Active signal tracking (max 1 per pair, max 1 BTC signal)
- ✅ Performance logging & statistics

## Trading Pairs

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

## Installation

1. **Clone repository**
```bash
git clone https://github.com/yourusername/bitget-signal-bot.git
cd bitget-signal-bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

4. **Create BitGet API keys**
   - Go to https://www.bitget.com/en/api-doc
   - Create API key with READ-ONLY permissions
   - Add API key, secret, and passphrase to `.env`

5. **Create Discord webhook**
   - Server Settings > Integrations > Webhooks
   - Copy webhook URL to `.env`

## Configuration

Edit `.env` file:
```env
BITGET_API_KEY=your_api_key
BITGET_SECRET_KEY=your_secret
BITGET_PASSPHRASE=your_passphrase

DISCORD_WEBHOOK_URL=your_webhook_url

INITIAL_CAPITAL=2000
RISK_PER_TRADE=0.01
MAX_DAILY_LOSS=0.02
MAX_WEEKLY_LOSS=0.06
```

## Usage

**Run locally:**
```bash
python -m src.main
```

**Check active signals status:**
```bash
python check_signals.py
```

**Remove historical signals (reverts equity/PnL impact):**
```bash
# Interactive mode - select which signals to remove
python remove_signals.py

# List all historical signals
python remove_signals.py --list

# Remove specific signal by ID
python remove_signals.py --id SIGNAL_123456
```

**Run with Docker:**
```bash
docker build -t bitget-signal-bot .
docker run -d --env-file .env bitget-signal-bot
```

## Active Signal Monitoring

The bot **continuously monitors active signals even when trading is disabled** for the day (e.g., due to daily loss limits or consecutive losses). This ensures:

- ✅ Take profit targets are always monitored
- ✅ Stop losses are always enforced
- ✅ Signals are properly closed when TP/SL is hit
- ✅ Performance tracking remains accurate

**To check your active signals at any time:**
```bash
python check_signals.py
```

This displays:
- Current price vs entry price
- Distance to stop loss
- Distance to each take profit level
- Realized and unrealized P&L
- Position size and duration

## Risk Management

- **Max risk per trade:** 1% ($20 on $2000 account)
- **Consecutive loss protection:** 3 losses triggers 4-hour cooldown ⭐ PRIMARY
- **Max weekly loss:** 6% ($120) - Hard stop for the week
- **Max leverage:** 3× effective
- **Max active signals:** 3 total, 1 per pair, 1 BTC max

**Note:** Daily loss limit removed in favor of consecutive loss cooldown, which is more responsive to actual trading conditions.

## Signal Rules

✅ **Creates signal when:**
- HTF trend aligns with direction
- Volatility within acceptable range (0.7-2.0× avg ATR)
- **MACD momentum confirms direction AND is strengthening** ⭐ NEW
- Price near EMA21 pullback
- **Clear distance from recent swing highs/lows (0.5× ATR minimum)** ⭐ NEW
- Volume above average
- Signal score ≥ 70 (or 85 during drawdown)

🛑 **Closes signal when:**
- TP1 hit (closes 50%)
- TP2 hit (closes 30%)
- TP3 hit (closes remaining 20%)
- Stop loss hit (closes all - now 2.0× ATR for better survivability) ⭐ IMPROVED

## Discord Notifications

Bot sends alerts for:
- 🚀 New signals (with full details)
- 🎯 Take profit hits
- 🛑 Stop loss hits
- 📊 Daily performance reports
- ⚠️ Errors & warnings

## File Structure
```
data/
├── signals_active.json      # Currently active signals
├── signals_history.json     # Completed signals
├── performance.json         # Risk manager state
└── trade_history.json       # All completed trades

logs/
└── bot.log                  # Bot logs (rotated daily)
```

## Deployment (GitHub + Cloud)

See `.github/workflows/deploy.yml` for automated deployment.

Supports:
- GitHub Actions
- AWS EC2
- DigitalOcean Droplets
- Any VPS with Docker

## Disclaimer

⚠️ **This bot is for educational purposes only.**

- Trading futures involves significant risk
- Past performance does not guarantee future results
- Only trade with capital you can afford to lose
- This is a SIGNAL BOT, not an auto-trader
- Manual verification recommended before executing trades

## License

MIT License - See LICENSE file