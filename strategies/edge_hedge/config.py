"""
Edge Hedge Strategy Configuration

Configuration dataclass for Edge Hedge strategy parameters.
"""

from dataclasses import dataclass
from core.interfaces.strategy_base import StrategyConfig


@dataclass
class EdgeHedgeConfig(StrategyConfig):
    """
    Edge Hedge Strategy Configuration

    Strategy Overview:
    1. Entry: Enter when FAIR probability > Market probability (edge >= threshold)
    2. Profit Taking: Hedge with opposite position when price rises to lock in profit
    3. Stop Loss: Hedge with opposite position when price drops to limit losses

    Attributes:
        enabled: Strategy activation status
        name: Strategy identifier
        min_edge_pct: Minimum edge percentage required for entry (default: 10.0%)
        profit_hedge_threshold_pct: Price increase % for profit-taking hedge (default: 7.0%)
        stoploss_trigger_pct: Price decrease % for stop-loss hedge (default: 15.0%)
        position_size_usdc: Position size in USDC (default: 10.0)
        entry_cooldown_sec: Minimum seconds between entries (default: 30.0)
        min_confidence: Minimum confidence threshold (default: 0.6)
        max_position_size: Maximum position size limit (default: 100.0)
        risk_per_trade: Risk percentage per trade (default: 2.0)
    """

    # Entry conditions
    min_edge_pct: float = 10.0

    # Profit-taking hedge condition
    profit_hedge_threshold_pct: float = 7.0

    # Stop-loss hedge condition
    stoploss_trigger_pct: float = 15.0

    # Position settings
    position_size_usdc: float = 10.0

    # Cooldown
    entry_cooldown_sec: float = 30.0

    def __post_init__(self):
        """Validate configuration parameters"""
        # Set default name if not provided
        if self.name == "base_strategy":
            self.name = "edge_hedge"

        # Call parent validation
        super().__post_init__()

        # Validate edge thresholds
        if self.min_edge_pct < 0:
            raise ValueError(f"min_edge_pct must be non-negative: {self.min_edge_pct}")

        if self.profit_hedge_threshold_pct < 0:
            raise ValueError(
                f"profit_hedge_threshold_pct must be non-negative: "
                f"{self.profit_hedge_threshold_pct}"
            )

        if self.stoploss_trigger_pct < 0:
            raise ValueError(
                f"stoploss_trigger_pct must be non-negative: {self.stoploss_trigger_pct}"
            )

        # Validate position size
        if self.position_size_usdc <= 0:
            raise ValueError(
                f"position_size_usdc must be positive: {self.position_size_usdc}"
            )

        # Validate cooldown
        if self.entry_cooldown_sec < 0:
            raise ValueError(
                f"entry_cooldown_sec must be non-negative: {self.entry_cooldown_sec}"
            )

        # Validate logical relationship
        if self.profit_hedge_threshold_pct >= self.stoploss_trigger_pct:
            raise ValueError(
                f"profit_hedge_threshold_pct ({self.profit_hedge_threshold_pct}%) "
                f"must be less than stoploss_trigger_pct ({self.stoploss_trigger_pct}%)"
            )
