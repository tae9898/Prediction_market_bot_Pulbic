<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# src

## Purpose
**LEGACY** source code directory. This directory contains the original trading bot implementation that has been superseded by `feature_source/`. New development should happen in `feature_source/`.

## Key Files

| File | Description |
|------|-------------|
| `api/binance.py` | Binance API client using ccxt for order book data |
| `api/polymarket.py` | Polymarket API client for prediction market trading |
| `processes/trader.py` | Main trading bot orchestrator (legacy) |
| `processes/redeemer.py` | Redemption process handler (legacy) |
| `strategies/base.py` | Base strategy class with common interface |
| `strategies/simple_strategy.py` | Simple threshold-based trading strategy |
| `utils/config_loader.py` | Configuration loading from environment files |
| `utils/ctf_handler.py` | Cross-chain transfer handler |
| `utils/logger.py` | Logging utilities with rotation |
| `utils/market_resolver.py` | Market resolution logic |
| `utils/orderbook_manager.py` | Order book monitoring and management |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `api/` | Exchange API clients (Binance, Polymarket) |
| `processes/` | Main trading processes (trader, redeemer) |
| `strategies/` | Trading strategy implementations |
| `utils/` | Utility functions for configuration, logging, etc. |

## For AI Agents

### Working In This Directory
⚠️ **WARNING**: This is legacy code. Do not make changes here unless explicitly maintaining old functionality.
- For new features, work in `feature_source/`
- For bug fixes, check if the issue exists in `feature_source/` first
- Code here may be out of sync with `feature_source/`

### Code Patterns
- Uses class-based strategy pattern with inheritance
- Configuration via environment variables (.env files)
- Logging to both file and console
- Async/await patterns for API calls

### Migration Path
Most code from this directory has been refactored into `feature_source/` with:
- Better error handling
- Improved configuration management
- Enhanced logging
- Multi-wallet support

## Dependencies

### Internal
- No dependencies on other project directories
- Standalone implementation (legacy)

### External
- `ccxt` - Exchange integration
- `web3` - Blockchain interaction
- `python-dotenv` - Environment configuration
- `requests` - HTTP client

<!-- MANUAL: -->
