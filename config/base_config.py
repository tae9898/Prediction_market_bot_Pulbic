"""
Configuration dataclasses for the trading bot.

Provides type-safe configuration containers for:
- Base system configuration
- Exchange connections
- Strategy parameters
- Wallet management
"""

from dataclasses import dataclass, field, fields
from typing import Dict, List, Optional, Any, Union
from enum import Enum


class SignatureType(Enum):
    """Signature types for exchange authentication."""
    EOA = 0  # Externally Owned Account
    GNOSIS_SAFE = 1  # Gnosis Safe wallet
    PROXY = 2  # Proxy wallet (default for Polymarket)


@dataclass
class ExchangeConfig:
    """
    Configuration for a single exchange connection.

    Attributes:
        name: Exchange identifier (polymarket, binance, etc.)
        enabled: Whether this exchange is active
        host: API host URL
        credentials: Dict of API keys/secrets
        settings: Exchange-specific settings (timeout, retry limits, etc.)
    """
    name: str
    enabled: bool = True
    host: Optional[str] = None
    chain_id: Optional[int] = None
    signature_type: int = SignatureType.PROXY.value
    credentials: Dict[str, str] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)

    def get_credential(self, key: str, default: str = "") -> str:
        """Get a credential value safely."""
        return self.credentials.get(key, default)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value safely."""
        return self.settings.get(key, default)


@dataclass
class StrategyConfig:
    """
    Configuration for a trading strategy.

    Attributes:
        name: Strategy identifier (trend, arbitrage, edge_hedge, expiry_sniper)
        enabled: Whether this strategy is active
        parameters: Strategy-specific parameters
        exchanges: List of exchanges this strategy can use (empty = all)
    """
    name: str
    enabled: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)
    exchanges: List[str] = field(default_factory=list)
    description: str = ""

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter value safely."""
        return self.parameters.get(key, default)

    def can_use_exchange(self, exchange_name: str) -> bool:
        """Check if strategy can use the given exchange."""
        if not self.exchanges:
            return True  # Empty list means all exchanges
        return exchange_name in self.exchanges


@dataclass
class WalletConfig:
    """
    Configuration for a single wallet.

    Attributes:
        name: Wallet identifier (main, wallet_1, etc.)
        private_key: Private key for signing (can be env var reference)
        address: Optional wallet address (for display)
        exchanges: Per-exchange credentials for this wallet
        strategies: List of strategy names enabled for this wallet
        enabled: Whether this wallet is active
    """
    name: str
    private_key: str
    address: Optional[str] = None
    exchanges: Dict[str, Dict[str, str]] = field(default_factory=dict)
    strategies: List[str] = field(default_factory=list)
    enabled: bool = True

    def get_exchange_credentials(self, exchange_name: str) -> Dict[str, str]:
        """Get credentials for a specific exchange."""
        return self.exchanges.get(exchange_name, {})

    def has_strategy(self, strategy_name: str) -> bool:
        """Check if wallet has this strategy enabled."""
        return strategy_name in self.strategies

    def is_active(self) -> bool:
        """Check if wallet is enabled and has private key."""
        return self.enabled and bool(self.private_key)


@dataclass
class BaseConfig:
    """
    Main configuration container for the trading bot.

    Attributes:
        exchanges: Dict of exchange configurations by name
        strategies: Dict of strategy configurations by name
        wallets: Dict of wallet configurations by name
        global_settings: Global bot settings (timeout, retry, logging, etc.)
        assets: List of enabled assets (BTC, ETH, etc.)
    """
    exchanges: Dict[str, ExchangeConfig] = field(default_factory=dict)
    strategies: Dict[str, StrategyConfig] = field(default_factory=dict)
    wallets: Dict[str, WalletConfig] = field(default_factory=dict)
    global_settings: Dict[str, Any] = field(default_factory=dict)
    assets: List[str] = field(default_factory=list)

    # Common global settings with defaults
    web_port: int = 3001
    web3_rpc_url: str = "https://rpc.ankr.com/polygon"
    log_level: str = "INFO"
    timeout_seconds: int = 30
    max_retries: int = 3

    def get_exchange(self, name: str) -> Optional[ExchangeConfig]:
        """Get exchange configuration by name."""
        return self.exchanges.get(name)

    def get_strategy(self, name: str) -> Optional[StrategyConfig]:
        """Get strategy configuration by name."""
        return self.strategies.get(name)

    def get_wallet(self, name: str) -> Optional[WalletConfig]:
        """Get wallet configuration by name."""
        return self.wallets.get(name)

    def get_enabled_exchanges(self) -> List[ExchangeConfig]:
        """Get all enabled exchanges."""
        return [e for e in self.exchanges.values() if e.enabled]

    def get_enabled_strategies(self) -> List[StrategyConfig]:
        """Get all enabled strategies."""
        return [s for s in self.strategies.values() if s.enabled]

    def get_active_wallets(self) -> List[WalletConfig]:
        """Get all active wallets."""
        return [w for w in self.wallets.values() if w.is_active()]

    def get_wallets_for_strategy(self, strategy_name: str) -> List[WalletConfig]:
        """Get all wallets that have this strategy enabled."""
        return [w for w in self.wallets.values() if w.has_strategy(strategy_name)]

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a global setting value."""
        return self.global_settings.get(key, default)

    def validate(self) -> List[str]:
        """
        Validate configuration and return list of errors.

        Returns:
            Empty list if valid, list of error messages otherwise.
        """
        errors = []

        # Check at least one exchange is configured
        if not self.exchanges:
            errors.append("No exchanges configured")
        else:
            for name, exchange in self.exchanges.items():
                if exchange.enabled and not exchange.host:
                    errors.append(f"Exchange '{name}' is enabled but has no host")

        # Check at least one strategy is configured
        if not self.strategies:
            errors.append("No strategies configured")

        # Check at least one wallet is configured
        if not self.wallets:
            errors.append("No wallets configured")
        else:
            for name, wallet in self.wallets.items():
                if wallet.enabled and not wallet.private_key:
                    errors.append(f"Wallet '{name}' is enabled but has no private_key")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            "exchanges": {
                name: {
                    "name": exc.name,
                    "enabled": exc.enabled,
                    "host": exc.host,
                    "chain_id": exc.chain_id,
                    "signature_type": exc.signature_type,
                    "credentials": exc.credentials,
                    "settings": exc.settings,
                }
                for name, exc in self.exchanges.items()
            },
            "strategies": {
                name: {
                    "name": strat.name,
                    "enabled": strat.enabled,
                    "parameters": strat.parameters,
                    "exchanges": strat.exchanges,
                    "description": strat.description,
                }
                for name, strat in self.strategies.items()
            },
            "wallets": {
                name: {
                    "name": wallet.name,
                    "private_key": "***REDACTED***" if wallet.private_key else None,
                    "address": wallet.address,
                    "exchanges": wallet.exchanges,
                    "strategies": wallet.strategies,
                    "enabled": wallet.enabled,
                }
                for name, wallet in self.wallets.items()
            },
            "global_settings": self.global_settings,
            "assets": self.assets,
            "web_port": self.web_port,
            "web3_rpc_url": self.web3_rpc_url,
            "log_level": self.log_level,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
        }
