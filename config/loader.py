"""
Configuration loader with environment variable expansion and validation.

Supports:
- Loading from config.json
- Loading from .env files
- Environment variable expansion (${VAR} syntax)
- Legacy config migration
- Validation
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv

from .base_config import (
    BaseConfig,
    ExchangeConfig,
    StrategyConfig,
    WalletConfig,
    SignatureType,
)


def expand_env_vars(value: Any) -> Any:
    """
    Expand environment variables in string values.

    Supports ${VAR} and $VAR syntax.
    Nested expansion: ${${VAR}_suffix} -> expands VAR first, then appends _suffix

    Args:
        value: Any value (strings are processed, others returned as-is)

    Returns:
        Value with environment variables expanded
    """
    if not isinstance(value, str):
        return value

    # Pattern to match ${VAR} or $VAR
    pattern = r'\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)'

    def replace_env_var(match):
        var_name = match.group(1) or match.group(2)
        env_value = os.environ.get(var_name, "")
        # Recursively expand nested variables
        return expand_env_vars(env_value)

    # Keep replacing until no more changes (handles nested variables)
    result = value
    max_iterations = 10  # Prevent infinite loops
    for _ in range(max_iterations):
        new_result = re.sub(pattern, replace_env_var, result)
        if new_result == result:
            break
        result = new_result

    return result


def load_dotenv_files(project_dir: Optional[Path] = None) -> None:
    """
    Load .env files in order of precedence.

    Order:
    1. .env.local (highest priority, git-ignored)
    2. .env (user-specific, git-ignored)
    3. .env.example (template, in git)

    Args:
        project_dir: Project directory (default: current working directory)
    """
    if project_dir is None:
        project_dir = Path.cwd()

    dotenv_files = [
        project_dir / ".env.example",
        project_dir / ".env",
        project_dir / ".env.local",
    ]

    for dotenv_file in dotenv_files:
        if dotenv_file.exists():
            load_dotenv(dotenv_file, override=True)


def migrate_legacy_config(legacy_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate legacy config format to new modular structure.

    Legacy format has:
    - Flat settings with _1, _2 suffixes for wallet overrides
    - Strategy settings like surebet_enabled, contrarian_enabled

    New format has:
    - exchanges: {polymarket: {...}}
    - strategies: {trend: {...}, arbitrage: {...}, ...}
    - wallets: {main: {...}}

    Args:
        legacy_config: Legacy configuration dictionary

    Returns:
        New format configuration dictionary
    """
    new_config = {
        "exchanges": {},
        "strategies": {},
        "wallets": {},
        "global_settings": {},
        "assets": legacy_config.get("enabled_assets", ["BTC", "ETH"]),
        "web_port": legacy_config.get("web_port", 3001),
        "web3_rpc_url": legacy_config.get("web3_rpc_url", "https://rpc.ankr.com/polygon"),
    }

    # Migrate Polymarket exchange
    polymarket_host = os.environ.get("POLYMARKET_HOST", "https://clob.polymarket.com")
    new_config["exchanges"]["polymarket"] = {
        "name": "polymarket",
        "enabled": True,
        "host": polymarket_host,
        "chain_id": legacy_config.get("CHAIN_ID", 137),
        "signature_type": legacy_config.get("SIGNATURE_TYPE", SignatureType.PROXY.value),
        "credentials": {},
        "settings": {
            "timeout": legacy_config.get("timeout_seconds", 30),
            "max_retries": legacy_config.get("max_retries", 3),
        }
    }

    # Migrate Binance exchange (if configured)
    if any(k.startswith("BINANCE_") for k in os.environ.keys()):
        new_config["exchanges"]["binance"] = {
            "name": "binance",
            "enabled": bool(os.environ.get("BINANCE_API_KEY")),
            "host": os.environ.get("BINANCE_HOST", "https://api.binance.com"),
            "credentials": {
                "api_key": os.environ.get("BINANCE_API_KEY", ""),
                "api_secret": os.environ.get("BINANCE_API_SECRET", ""),
            },
            "settings": {
                "timeout": 30,
                "max_retries": 3,
            }
        }

    # Migrate strategies
    # Map legacy settings to strategy configs
    strategy_mappings = {
        "arbitrage": {
            "legacy_key": "surebet_enabled",
            "description": "Sure-bet arbitrage when YES/NO prices sum < 1",
            "parameters": {},
        },
        "contrarian": {
            "legacy_key": "contrarian_enabled",
            "description": "Contrarian strategy - bet against the crowd",
            "parameters": {
                "entry_edge_min": "contrarian_entry_edge_min",
                "entry_edge_max": "contrarian_entry_edge_max",
                "exit_edge": "contrarian_exit_edge",
                "take_profit_pct": "contrarian_take_profit_pct",
            },
        },
        "edge_hedge": {
            "legacy_key": "edge_hedge_enabled",
            "description": "Edge hedge - profit from probability differences",
            "parameters": {
                "min_edge_pct": "edge_hedge_min_edge_pct",
                "profit_threshold_pct": "edge_hedge_profit_threshold_pct",
                "stoploss_pct": "edge_hedge_stoploss_pct",
            },
        },
        "expiry_sniper": {
            "legacy_key": "expiry_sniper_enabled",
            "description": "Expiry sniper - enter positions near market close",
            "parameters": {
                "minutes_before": "expiry_sniper_minutes_before",
                "prob_threshold": "expiry_sniper_prob_threshold",
                "amount_usdc": "expiry_sniper_amount_usdc",
                "max_times": "expiry_sniper_max_times",
                "interval_seconds": "expiry_sniper_interval_seconds",
            },
        },
    }

    for strategy_name, mapping in strategy_mappings.items():
        legacy_enabled_key = mapping["legacy_key"]
        parameters = {}

        # Build parameters from legacy config
        for param_key, legacy_key in mapping["parameters"].items():
            if legacy_key in legacy_config:
                parameters[param_key] = legacy_config[legacy_key]

        new_config["strategies"][strategy_name] = {
            "name": strategy_name,
            "enabled": legacy_config.get(legacy_enabled_key, False),
            "parameters": parameters,
            "exchanges": ["polymarket"],  # These are Polymarket-specific
            "description": mapping["description"],
        }

    # Migrate wallets from environment variables
    # Pattern: WALLET_<LABEL>_<FIELD>
    wallet_prefix = "WALLET_"
    wallets_data: Dict[str, Dict[str, Any]] = {}

    for env_key, env_value in os.environ.items():
        if env_key.startswith(wallet_prefix):
            # Parse WALLET_<LABEL>_<FIELD>
            parts = env_key[len(wallet_prefix):].split("_", 1)
            if len(parts) == 2:
                label, field = parts
                if label not in wallets_data:
                    wallets_data[label] = {"name": label, "exchanges": {}, "strategies": []}
                wallets_data[label][field.lower()] = env_value

    # If no wallets in env, create main wallet from legacy config
    if not wallets_data:
        wallets_data["main"] = {
            "name": "main",
            "private_key": os.environ.get("PRIVATE_KEY", ""),
            "exchanges": {},
            "strategies": [],
        }

    # Assign strategies to wallets based on legacy _1, _2 suffixes
    # Default wallet gets all strategies unless overridden
    main_wallet_strategies = []
    for strategy_name in strategy_mappings.keys():
        main_wallet_strategies.append(strategy_name)

    # Check for wallet-specific overrides
    for wallet_label, wallet_data in wallets_data.items():
        if wallet_label == "main":
            wallet_data["strategies"] = main_wallet_strategies
        else:
            # Check for _1, _2 suffix overrides
            wallet_num = wallet_label.replace("wallet_", "")
            try:
                wallet_idx = int(wallet_num) if wallet_num else 1
            except ValueError:
                wallet_idx = 1

            strategies_for_wallet = []
            for strategy_name in strategy_mappings.keys():
                legacy_key = f"{strategy_mappings[strategy_name]['legacy_key']}_{wallet_idx}"
                if legacy_config.get(legacy_key, legacy_config.get(strategy_mappings[strategy_name]['legacy_key'], False)):
                    strategies_for_wallet.append(strategy_name)

            wallet_data["strategies"] = strategies_for_wallet

    # Add wallet exchange credentials from env
    for wallet_label, wallet_data in wallets_data.items():
        # Add Polymarket credentials
        polymarket_creds = {}
        for key in ["API_KEY", "API_SECRET", "API_PASSPHRASE", "SIGNATURE_TYPE"]:
            env_key = f"WALLET_{wallet_label}_API_{key}" if wallet_label != "main" else f"API_{key}"
            if env_key in os.environ:
                polymarket_creds[key.lower()] = os.environ[env_key]

        if polymarket_creds:
            wallet_data["exchanges"]["polymarket"] = polymarket_creds

    # Add wallets to config
    for wallet_label, wallet_data in wallets_data.items():
        wallet_data["enabled"] = bool(wallet_data.get("private_key"))
        new_config["wallets"][wallet_label] = wallet_data

    # Migrate global settings
    global_setting_keys = [
        "bet_amount_usdc",
        "max_position_size",
        "use_kelly",
        "edge_threshold_pct",
        "subtract_spread_from_edge",
        "volatility_window_minutes",
        "auto_redeem_enabled",
        "global_stoploss_pct",
        "emergency_cleanup_on_start",
    ]

    for key in global_setting_keys:
        if key in legacy_config:
            new_config["global_settings"][key] = legacy_config[key]

    return new_config


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    project_dir: Optional[Union[str, Path]] = None,
    use_env: bool = True,
) -> BaseConfig:
    """
    Load configuration from file and environment.

    Priority (highest to lowest):
    1. Environment variables (if use_env=True)
    2. config.json (if exists)
    3. .env files (if use_env=True)

    Args:
        config_path: Path to config.json (default: <project_dir>/config.json)
        project_dir: Project directory (default: current working directory)
        use_env: Whether to load environment variables

    Returns:
        BaseConfig instance

    Raises:
        FileNotFoundError: If config.json doesn't exist
        ValueError: If configuration is invalid
    """
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    if config_path is None:
        config_path = project_dir / "config.json"
    else:
        config_path = Path(config_path)

    # Load environment variables
    if use_env:
        load_dotenv_files(project_dir)

    # Load config file
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r') as f:
        raw_config = json.load(f)

    # Check if this is a legacy config format
    is_legacy = "exchanges" not in raw_config

    if is_legacy:
        # Migrate to new format
        raw_config = migrate_legacy_config(raw_config)

    # Expand environment variables in all string values
    config = expand_env_vars_in_dict(raw_config)

    # Parse into BaseConfig
    base_config = parse_config(config)

    # Validate
    errors = base_config.validate()
    if errors:
        raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    return base_config


def expand_env_vars_in_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively expand environment variables in a dictionary."""
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = expand_env_vars_in_dict(value)
        elif isinstance(value, list):
            result[key] = [expand_env_vars(item) for item in value]
        else:
            result[key] = expand_env_vars(value)
    return result


def parse_config(data: Dict[str, Any]) -> BaseConfig:
    """Parse configuration dictionary into BaseConfig instance."""
    # Parse exchanges
    exchanges = {}
    for name, exc_data in data.get("exchanges", {}).items():
        exchanges[name] = ExchangeConfig(
            name=exc_data.get("name", name),
            enabled=exc_data.get("enabled", True),
            host=exc_data.get("host"),
            chain_id=exc_data.get("chain_id"),
            signature_type=exc_data.get("signature_type", SignatureType.PROXY.value),
            credentials=exc_data.get("credentials", {}),
            settings=exc_data.get("settings", {}),
        )

    # Parse strategies
    strategies = {}
    for name, strat_data in data.get("strategies", {}).items():
        strategies[name] = StrategyConfig(
            name=strat_data.get("name", name),
            enabled=strat_data.get("enabled", False),
            parameters=strat_data.get("parameters", {}),
            exchanges=strat_data.get("exchanges", []),
            description=strat_data.get("description", ""),
        )

    # Parse wallets
    wallets = {}
    for name, wallet_data in data.get("wallets", {}).items():
        wallets[name] = WalletConfig(
            name=wallet_data.get("name", name),
            private_key=wallet_data.get("private_key", ""),
            address=wallet_data.get("address"),
            exchanges=wallet_data.get("exchanges", {}),
            strategies=wallet_data.get("strategies", []),
            enabled=wallet_data.get("enabled", True),
        )

    # Create BaseConfig
    return BaseConfig(
        exchanges=exchanges,
        strategies=strategies,
        wallets=wallets,
        global_settings=data.get("global_settings", {}),
        assets=data.get("assets", []),
        web_port=data.get("web_port", 3001),
        web3_rpc_url=data.get("web3_rpc_url", "https://rpc.ankr.com/polygon"),
        log_level=data.get("log_level", "INFO"),
        timeout_seconds=data.get("timeout_seconds", 30),
        max_retries=data.get("max_retries", 3),
    )


def validate_config(config: BaseConfig) -> tuple[bool, list[str]]:
    """
    Validate configuration.

    Args:
        config: BaseConfig instance

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = config.validate()
    return (len(errors) == 0, errors)


def save_config(config: BaseConfig, config_path: Union[str, Path]) -> None:
    """
    Save configuration to file.

    Args:
        config: BaseConfig instance
        config_path: Path to save config.json
    """
    config_path = Path(config_path)

    # Convert to dictionary
    config_dict = config.to_dict()

    # Write to file with pretty formatting
    with open(config_path, 'w') as f:
        json.dump(config_dict, f, indent=2, sort_keys=False)
