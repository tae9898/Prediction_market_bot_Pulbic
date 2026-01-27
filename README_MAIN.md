# Main.py - Trading Bot Entry Point

## Overview

The new `main.py` is the unified entry point for the trading bot, replacing the legacy `feature_source/main.py`. It uses the modular `core/` architecture with the registry system for exchanges and strategies.

## Architecture

```
main.py
├── TradingEngine          # Main orchestrator
│   ├── Exchanges          # From exchange registry
│   ├── Strategies         # From strategy registry
│   └── Contexts           # Per-wallet execution contexts
├── Config System          # config/load_config()
├── CLI Interface          # Rich-based dashboard
└── Web Server             # FastAPI/Uvicorn
```

## Key Components

### TradingEngine

The `TradingEngine` class orchestrates:
- **Multiple exchanges**: Binance, Polymarket, etc.
- **Multiple strategies**: Trend, Arbitrage, Edge Hedge, Expiry Sniper
- **Multiple wallets**: Each with its own execution context
- **Event callbacks**: Logging, signals, trades, errors

### Execution Context

Each wallet has its own `ExecutionContext` from `core/context`:
- Bot state management (IDLE, RUNNING, STOPPING, STOPPED, ERROR)
- Strategy state storage
- Asset and position tracking
- Log buffers with callbacks
- Signal and trade events

### Registry System

Uses `core/registry` for dynamic component loading:
- `strategy_registry`: Registered strategy classes
- `exchange_registry`: Registered exchange classes

## CLI Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `--dry-run` | flag | Simulation mode (no real trades) |
| `--wallet WALLET` | string | Run specific wallet only |
| `--web-only` | flag | Web interface only, no CLI |
| `--port PORT` | int | Custom web server port |
| `--config PATH` | string | Path to config.json (default: config.json) |
| `--log-level LEVEL` | string | Logging level: DEBUG, INFO, WARNING, ERROR |

## Usage Examples

### Basic Usage

```bash
# Run with CLI and Web interfaces
python main.py

# Dry-run mode (simulate trades)
python main.py --dry-run

# Web interface only
python main.py --web-only

# Custom port
python main.py --port 8080

# Single wallet
python main.py --wallet main

# Custom config file
python main.py --config /path/to/config.json

# Verbose logging
python main.py --log-level DEBUG
```

### Combined Options

```bash
# Dry-run with custom port and verbose logging
python main.py --dry-run --port 9000 --log-level DEBUG

# Web-only mode for specific wallet
python main.py --wallet wallet_1 --web-only --port 8080
```

## Configuration

### Config File Structure

The bot loads configuration from `config.json` (or custom path via `--config`).

Example structure:
```json
{
  "exchanges": {
    "polymarket": {
      "name": "polymarket",
      "enabled": true,
      "host": "https://clob.polymarket.com",
      "chain_id": 137,
      "signature_type": 2,
      "credentials": {},
      "settings": {
        "timeout": 30,
        "max_retries": 3
      }
    },
    "binance": {
      "name": "binance",
      "enabled": true,
      "host": "https://api.binance.com",
      "credentials": {
        "api_key": "${BINANCE_API_KEY}",
        "api_secret": "${BINANCE_API_SECRET}"
      }
    }
  },
  "strategies": {
    "trend": {
      "name": "trend",
      "enabled": true,
      "parameters": {
        "mode": "directional",
        "edge_threshold_pct": 3.0,
        "min_confidence": 0.6
      },
      "exchanges": ["polymarket"]
    },
    "arbitrage": {
      "name": "arbitrage",
      "enabled": true,
      "parameters": {
        "min_profit_rate": 0.02
      },
      "exchanges": ["polymarket"]
    }
  },
  "wallets": {
    "main": {
      "name": "main",
      "private_key": "${PRIVATE_KEY}",
      "strategies": ["trend", "arbitrage"],
      "enabled": true
    }
  },
  "global_settings": {},
  "assets": ["BTC", "ETH"],
  "web_port": 3001,
  "web3_rpc_url": "https://rpc.ankr.com/polygon",
  "log_level": "INFO"
}
```

### Environment Variables

The config supports environment variable expansion using `${VAR}` syntax:

```bash
# .env file
PRIVATE_KEY=0x...
POLYMARKET_HOST=https://clob.polymarket.com
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
```

Then reference in config.json:
```json
{
  "wallets": {
    "main": {
      "private_key": "${PRIVATE_KEY}"
    }
  },
  "exchanges": {
    "binance": {
      "credentials": {
        "api_key": "${BINANCE_API_KEY}",
        "api_secret": "${BINANCE_API_SECRET}"
      }
    }
  }
}
```

## Features

### Multi-Wallet Support

Run multiple wallets simultaneously, each with its own:
- Private key
- Strategy assignments
- Execution context
- P&L tracking

### Dry-Run Mode

Test strategies without risking real capital:
- Signals are generated but not executed
- All logging and callbacks work normally
- `[DRY RUN]` prefix in logs for simulated actions

### Graceful Shutdown

Handles `SIGINT` (Ctrl+C) and `SIGTERM`:
- Stops trading loop
- Closes positions (optional)
- Disconnects exchanges
- Cleans up resources

### CLI Interface (Rich)

Rich-based dashboard showing:
- Bot status (running/stopped)
- Mode (live/dry-run)
- Exchange connections
- Per-wallet status
- Live metrics

Press `Ctrl+C` to exit.

### Web Interface (FastAPI)

REST API for monitoring and control:
- Health check endpoint: `GET /health`
- Dashboard: `http://localhost:<port>`

## Migration from Legacy

### From feature_source/main.py

The new `main.py` is backward compatible with the legacy config format. Old configs are automatically migrated.

Key differences:
1. Uses `core/` architecture instead of `bot_core.py`
2. Uses `config/` package instead of `config.py`
3. Uses `exchanges/` package with registry system
4. Uses `strategies/` package with registry system
5. Per-wallet execution contexts instead of global state

### Config Migration

Legacy config format is automatically detected and migrated:

```python
# Old format (flat with _1, _2 suffixes)
{
  "surebet_enabled": true,
  "contrarian_enabled": true,
  "PRIVATE_KEY": "0x...",
  ...
}

# Automatically migrated to:
{
  "exchanges": {...},
  "strategies": {
    "arbitrage": {"enabled": true, ...},
    "trend": {"enabled": true, ...}
  },
  "wallets": {
    "main": {"private_key": "0x...", ...}
  }
}
```

## Troubleshooting

### Import Errors

If you get import errors, ensure you're in the virtual environment:
```bash
source .venv/bin/activate
python main.py
```

### Config Not Found

Create a `config.json` file or use `.env` variables:
```bash
cp config.example.json config.json
# Edit config.json with your settings
```

### Exchange Connection Errors

Check:
1. API keys are correct
2. Network connectivity
3. Exchange URLs in config
4. Firewall/proxy settings

### Strategy Errors

Enable debug logging:
```bash
python main.py --log-level DEBUG
```

Check strategy logs in `logs/trading_bot.log`.

## Development

### Adding New Strategies

1. Create strategy in `strategies/<name>/strategy.py`
2. Inherit from `BaseStrategy`
3. Register in `strategies/<name>/__init__.py`
4. Import in `main.py`
5. Add to `_create_strategy()` method

### Adding New Exchanges

1. Create exchange in `exchanges/<name>.py`
2. Inherit from `ExchangeClient`
3. Register in `exchanges/__init__.py`
4. Import in `main.py`
5. Add to `_initialize_exchanges()` method

## File Structure

```
root/
├── main.py                    # Main entry point (this file)
├── config/
│   ├── __init__.py
│   ├── base_config.py         # Config dataclasses
│   └── loader.py              # Config loading with env expansion
├── core/
│   ├── __init__.py
│   ├── context.py             # ExecutionContext class
│   ├── interfaces/
│   │   ├── strategy_base.py   # BaseStrategy abstract class
│   │   ├── exchange_base.py   # ExchangeClient abstract class
│   │   └── data_feed_base.py  # DataFeed abstract class
│   └── registry.py            # Strategy and exchange registries
├── exchanges/
│   ├── __init__.py
│   ├── binance.py             # Binance integration
│   ├── polymarket.py          # Polymarket integration
│   └── adapters.py            # Exchange adapters
├── strategies/
│   ├── trend/                 # Trend/Contrarian strategy
│   ├── arbitrage/             # Sure-bet arbitrage
│   ├── edge_hedge/            # Edge hedge strategy
│   └── expiry_sniper/         # Expiry sniper strategy
├── src/
│   └── utils/
│       └── logger.py          # Logging utilities
└── logs/                      # Log files directory
```

## License

See project LICENSE file.
