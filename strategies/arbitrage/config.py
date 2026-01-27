"""
Arbitrage Strategy Configuration

Configuration dataclass for the sure-bet arbitrage strategy.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ArbitrageConfig:
    """
    Arbitrage strategy configuration.

    Attributes:
        enabled: Strategy enabled flag
        name: Strategy name
        min_profit_rate: Minimum profit rate threshold (%)
        max_profit_rate: Maximum profit rate for safety (%)
        max_total_cost: Maximum total cost for position (USDC)
        slippage_tolerance: Slippage tolerance for orders (decimal)
        min_size: Minimum order size (shares)
        max_search_size: Maximum size to search in orderbook
        search_step: Step size for orderbook search
        panic_mode_enabled: Enable panic mode on leg failure
        panic_slippage: Additional slippage for panic orders
    """
    enabled: bool = True
    name: str = "arbitrage"
    min_profit_rate: float = 1.0
    max_profit_rate: float = 10.0
    max_total_cost: float = 1000.0
    slippage_tolerance: float = 0.005
    min_size: float = 5.0
    max_search_size: float = 1000.0
    search_step: float = 1.0
    panic_mode_enabled: bool = True
    panic_slippage: float = 0.01

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.min_profit_rate < 0:
            raise ValueError(f"min_profit_rate must be non-negative: {self.min_profit_rate}")

        if self.max_profit_rate <= self.min_profit_rate:
            raise ValueError(
                f"max_profit_rate must be greater than min_profit_rate: "
                f"{self.max_profit_rate} <= {self.min_profit_rate}"
            )

        if self.max_total_cost <= 0:
            raise ValueError(f"max_total_cost must be positive: {self.max_total_cost}")

        if not (0 <= self.slippage_tolerance <= 0.1):
            raise ValueError(f"slippage_tolerance must be 0-0.1: {self.slippage_tolerance}")

        if self.min_size <= 0:
            raise ValueError(f"min_size must be positive: {self.min_size}")

        if self.max_search_size < self.min_size:
            raise ValueError(
                f"max_search_size must be >= min_size: "
                f"{self.max_search_size} < {self.min_size}"
            )

        if self.search_step <= 0:
            raise ValueError(f"search_step must be positive: {self.search_step}")

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "enabled": self.enabled,
            "name": self.name,
            "min_profit_rate": self.min_profit_rate,
            "max_profit_rate": self.max_profit_rate,
            "max_total_cost": self.max_total_cost,
            "slippage_tolerance": self.slippage_tolerance,
            "min_size": self.min_size,
            "max_search_size": self.max_search_size,
            "search_step": self.search_step,
            "panic_mode_enabled": self.panic_mode_enabled,
            "panic_slippage": self.panic_slippage,
        }
