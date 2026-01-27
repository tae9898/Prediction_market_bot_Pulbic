# Main.py Quick Reference

## Installation & Setup

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (if needed)
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and settings

# Create config file
cp config.example.json config.json
# Edit config.json with your preferences
```

## Basic Commands

```bash
# Run bot with CLI and Web interfaces
python main.py

# Dry-run mode (test without real trades)
python main.py --dry-run

# Web interface only (no CLI dashboard)
python main.py --web-only

# Run specific wallet
python main.py --wallet main

# Custom web port
python main.py --port 8080

# Debug logging
python main.py --log-level DEBUG

# Combined options
python main.py --dry-run --port 9000 --log-level DEBUG
```

## CLI Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--dry-run` | Simulation mode (no real trades) | `--dry-run` |
| `--wallet WALLET` | Run specific wallet only | `--wallet main` |
| `--web-only` | Web interface only, no CLI | `--web-only` |
| `--port PORT` | Custom web server port | `--port 8080` |
| `--config PATH` | Path to config file | `--config /path/to/config.json` |
| `--log-level LEVEL` | Logging level | `--log-level DEBUG` |

## Trading Modes

### Live Trading
```bash
python main.py
```
- Executes real trades on configured exchanges
- Requires valid API keys and private keys
- Auto-trade must be enabled in config

### Dry-Run Mode
```bash
python main.py --dry-run
```
- Simulates trades without execution
- All signals and analysis work normally
- Logs show `[DRY RUN]` prefix for simulated actions

### Web-Only Mode
```bash
python main.py --web-only
```
- Runs web server without CLI dashboard
- Useful for running as a service
- Access dashboard at `http://localhost:<port>`

## Configuration

### Minimal config.json

```json
{
  "exchanges": {
    "polymarket": {
      "name": "polymarket",
      "enabled": true,
      "host": "https://clob.polymarket.com"
    }
  },
  "strategies": {
    "trend": {
      "name": "trend",
      "enabled": true,
      "parameters": {
        "mode": "directional",
        "edge_threshold_pct": 3.0
      }
    }
  },
  "wallets": {
    "main": {
      "name": "main",
      "private_key": "${PRIVATE_KEY}",
      "strategies": ["trend"],
      "enabled": true
    }
  },
  "web_port": 3001
}
```

### Environment Variables (.env)

```bash
# Required
PRIVATE_KEY=0x...your_wallet_private_key

# Optional
POLYMARKET_HOST=https://clob.polymarket.com
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret

# Web
WEB_PORT=3001
LOG_LEVEL=INFO
```

## Key Features

### Multi-Wallet Support

Configure multiple wallets in config.json:

```json
{
  "wallets": {
    "main": {
      "private_key": "${PRIVATE_KEY}",
      "strategies": ["trend", "arbitrage"]
    },
    "wallet_1": {
      "private_key": "${WALLET_1_PRIVATE_KEY}",
      "strategies": ["edge_hedge"]
    }
  }
}
```

Run specific wallet:
```bash
python main.py --wallet wallet_1
```

### Strategy Configuration

Available strategies:
- **trend**: Directional/contrarian trading based on price vs strike
- **arbitrage**: Sure-bet arbitrage when YES/NO prices sum < 1
- **edge_hedge**: Probability-based hedging
- **expiry_sniper**: High-probability bets near market close

Enable strategies in config.json:
```json
{
  "strategies": {
    "trend": {
      "enabled": true,
      "parameters": {
        "mode": "directional",
        "edge_threshold_pct": 3.0
      }
    },
    "arbitrage": {
      "enabled": true,
      "parameters": {
        "min_profit_rate": 0.02
      }
    }
  }
}
```

### Per-Wallet Strategy Assignment

Assign strategies to specific wallets:

```json
{
  "wallets": {
    "main": {
      "strategies": ["trend", "arbitrage"]
    },
    "conservative": {
      "strategies": ["arbitrage"]
    },
    "aggressive": {
      "strategies": ["trend", "edge_hedge", "expiry_sniper"]
    }
  }
}
```

## Monitoring

### CLI Dashboard

The Rich-based dashboard shows:
- Bot status (running/stopped)
- Trading mode (live/dry-run)
- Number of active exchanges
- Per-wallet status and state

Press `Ctrl+C` to gracefully shutdown.

### Web Interface

Access the web dashboard at:
```
http://localhost:3001
```

(or your custom port with `--port`)

Web interface provides:
- Real-time bot status
- Per-wallet metrics
- Strategy performance
- P&L tracking
- Signal history

### Logs

Logs are stored in `logs/` directory:
- `trading_bot.log`: Main bot log
- Rotating file handler (10MB per file, 5 backup files)

## Troubleshooting

### "Config file not found"

Create a config.json file:
```bash
cp config.example.json config.json
# Edit with your settings
```

Or use environment variables in `.env` file.

### "No active wallets found"

Ensure at least one wallet has:
- `enabled: true`
- Valid `private_key`

### "Exchange connection failed"

Check:
- API keys are correct
- Exchange URL is accessible
- Network/firewall settings
- Exchange is enabled in config

### Import errors

Ensure virtual environment is activated:
```bash
source .venv/bin/activate
python main.py
```

### Strategy not running

Check:
- Strategy is enabled in config
- Wallet has strategy in its `strategies` list
- Strategy parameters are valid
- Check logs with `--log-level DEBUG`

## Advanced Usage

### Custom Config File

```bash
python main.py --config /path/to/custom_config.json
```

### Debug Mode

```bash
python main.py --log-level DEBUG --dry-run
```

### Running as Service

```bash
# Web-only mode, no CLI
python main.py --web-only --port 8080
```

Use with systemd, supervisor, or process manager for production.

## Architecture

```
main.py
├── TradingEngine (orchestrator)
│   ├── Exchanges (from registry)
│   │   ├── Binance (price feed)
│   │   └── Polymarket (trading)
│   ├── Strategies (from registry)
│   │   ├── Trend
│   │   ├── Arbitrage
│   │   ├── Edge Hedge
│   │   └── Expiry Sniper
│   └── Contexts (per-wallet)
│       ├── Bot State
│       ├── Strategy State
│       ├── Positions
│       └── Logs
├── CLI Interface (Rich)
└── Web Server (FastAPI)
```

## Migration from Legacy

If you're coming from `feature_source/main.py`:

1. **Config migration**: Old configs are automatically migrated
2. **Same functionality**: All features from legacy version are available
3. **New architecture**: Uses `core/` registry system
4. **Better modularity**: Easier to add exchanges and strategies

Your existing config.json and .env files should work without changes.

## Help

```bash
python main.py --help
```

Shows all available options with descriptions.
