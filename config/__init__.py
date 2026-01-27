"""
Modular Configuration System for Trading Bot

This package provides a flexible configuration system supporting:
- Multiple exchanges (Polymarket, Binance, etc.)
- Multiple strategies (Trend, Arbitrage, Edge Hedge, Expiry Sniper)
- Multiple wallets with per-wallet strategy assignments
- Environment variable expansion (${VAR} syntax)
- Backward compatibility with legacy config format
"""

from .base_config import (
    BaseConfig,
    ExchangeConfig,
    StrategyConfig,
    WalletConfig,
)
from .loader import (
    load_config,
    expand_env_vars,
    validate_config,
    migrate_legacy_config,
)

__all__ = [
    # Base config classes
    'BaseConfig',
    'ExchangeConfig',
    'StrategyConfig',
    'WalletConfig',
    # Loader functions
    'load_config',
    'expand_env_vars',
    'validate_config',
    'migrate_legacy_config',
]

__version__ = '1.0.0'
