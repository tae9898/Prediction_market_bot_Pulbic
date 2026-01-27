"""
Sure-Bet Arbitrage Strategy

Implements arbitrage strategy for binary prediction markets.
Analyzes orderbook for YES/NO token price discrepancies and executes
simultaneous buy orders when profit is guaranteed.

References:
    - Original implementation: feature_source/strategies/arbitrage.py
    - Base interface: core/interfaces/strategy_base.py
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces.strategy_base import (
    BaseStrategy,
    StrategyConfig,
    MarketSignal,
    SignalAction,
    SignalDirection,
)
from core.interfaces.exchange_base import (
    OrderBook,
    OrderBookLevel,
    ExchangeClient,
    OrderSide,
    OrderType,
)
from core.registry import register_strategy
from .config import ArbitrageConfig


class ArbitrageSignalType(Enum):
    """Arbitrage specific signal types."""
    OPPORTUNITY = "opportunity"  # Profitable opportunity found
    EXECUTED = "executed"  # Arbitrage executed
    PANIC = "panic"  # Panic mode triggered


@dataclass
class ArbitrageOpportunity:
    """
    Arbitrage opportunity analysis result.

    Attributes:
        vwap_yes: VWAP price for YES tokens
        vwap_no: VWAP price for NO tokens
        total_cost: Total cost for both legs (VWAP_YES + VWAP_NO)
        spread: Price spread (1.0 - total_cost)
        profit_rate: Profit rate percentage
        max_size: Maximum profitable size (shares)
        max_profit: Maximum profit amount (USDC)
        is_profitable: Whether opportunity meets profit threshold
        reason: Human-readable reason for status
        yes_liquidity: Total liquidity on YES side
        no_liquidity: Total liquidity on NO side
        timestamp: Analysis timestamp
    """
    vwap_yes: float = 0.0
    vwap_no: float = 0.0
    total_cost: float = 0.0
    spread: float = 0.0
    profit_rate: float = 0.0
    max_size: float = 0.0
    max_profit: float = 0.0
    is_profitable: bool = False
    reason: str = ""
    yes_liquidity: float = 0.0
    no_liquidity: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "vwap_yes": self.vwap_yes,
            "vwap_no": self.vwap_no,
            "total_cost": self.total_cost,
            "spread": self.spread,
            "profit_rate": self.profit_rate,
            "max_size": self.max_size,
            "max_profit": self.max_profit,
            "is_profitable": self.is_profitable,
            "reason": self.reason,
            "yes_liquidity": self.yes_liquidity,
            "no_liquidity": self.no_liquidity,
            "timestamp": self.timestamp,
        }


@dataclass
class SurebetExecutionParams:
    """
    Parameters for surebet execution.

    Attributes:
        yes_size: Size of YES token order
        yes_max_price: Maximum price for YES order
        no_size: Size of NO token order
        no_max_price: Maximum price for NO order
        expected_profit: Expected profit amount
        profit_rate: Expected profit rate
    """
    yes_size: float = 0.0
    yes_max_price: float = 0.0
    no_size: float = 0.0
    no_max_price: float = 0.0
    expected_profit: float = 0.0
    profit_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "yes_size": self.yes_size,
            "yes_max_price": self.yes_max_price,
            "no_size": self.no_size,
            "no_max_price": self.no_max_price,
            "expected_profit": self.expected_profit,
            "profit_rate": self.profit_rate,
        }


@register_strategy("arbitrage")
class SurebetEngine(BaseStrategy):
    """
    Sure-Bet Arbitrage Engine.

    Analyzes orderbook for YES/NO token arbitrage opportunities in
    binary prediction markets. Executes simultaneous buy orders when
    total cost < 1.0 guarantees profit.

    Features:
    - VWAP-based price calculation
    - Liquidity-aware sizing
    - Panic mode for leg failure handling
    - Slippage protection
    - Configurable profit thresholds

    Example:
        >>> config = ArbitrageConfig(min_profit_rate=1.0)
        >>> strategy = SurebetEngine(config)
        >>> signal = strategy.analyze(market_data)
        >>> if signal.action == SignalAction.ENTER:
        ...     # Execute arbitrage
    """

    def __init__(
        self,
        config: ArbitrageConfig,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize surebet engine.

        Args:
            config: Arbitrage configuration
            logger: Optional logger instance
        """
        # Use ArbitrageConfig but inherit from StrategyConfig
        base_config = StrategyConfig(
            enabled=config.enabled,
            name=config.name,
            min_edge_pct=config.min_profit_rate,
            min_confidence=0.8,  # High confidence for arbitrage
            max_position_size=config.max_total_cost,
            risk_per_trade=1.0,  # Low risk for arb
        )
        super().__init__(base_config, logger)

        self.arb_config = config
        self.logger.info(
            f"SurebetEngine initialized: min_profit={config.min_profit_rate}%, "
            f"max_cost=${config.max_total_cost}"
        )

    def validate_config(self) -> bool:
        """
        Validate configuration parameters.

        Returns:
            bool: True if configuration is valid
        """
        try:
            # Validate ArbitrageConfig
            self.arb_config.__post_init__()
            # Validate base StrategyConfig
            self.config.__post_init__()
            self.logger.debug("Configuration validation passed")
            return True
        except ValueError as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def analyze(
        self,
        market_data: Dict[str, Any],
        position: Optional[Dict[str, Any]] = None
    ) -> Optional[MarketSignal]:
        """
        Analyze market data for arbitrage opportunities.

        Args:
            market_data: Market data dictionary containing:
                - yes_orderbook: OrderBook for YES token
                - no_orderbook: OrderBook for NO token
            position: Current position (not used for arbitrage)

        Returns:
            MarketSignal: Signal if opportunity found, None otherwise
        """
        if not self.config.enabled:
            self.logger.debug("Strategy disabled, skipping analysis")
            return None

        # Extract orderbooks from market data
        yes_orderbook = market_data.get("yes_orderbook")
        no_orderbook = market_data.get("no_orderbook")

        if not yes_orderbook or not no_orderbook:
            self.logger.warning("Missing orderbook data in market_data")
            return None

        # Validate orderbook format
        if not isinstance(yes_orderbook, OrderBook) or not isinstance(no_orderbook, OrderBook):
            self.logger.error("Invalid orderbook format, expected OrderBook objects")
            return None

        # Analyze for arbitrage opportunity
        opportunity = self._analyze_arbitrage(yes_orderbook, no_orderbook)

        if not opportunity.is_profitable:
            self.logger.debug(f"No profitable opportunity: {opportunity.reason}")
            return None

        # Create market signal
        signal = MarketSignal(
            action=SignalAction.ENTER,
            direction=SignalDirection.FLAT,  # Market-neutral
            confidence=0.9,  # High confidence for guaranteed profit
            edge=opportunity.profit_rate,
            reason=f"Arbitrage: {opportunity.reason}",
            metadata={
                "opportunity": opportunity.to_dict(),
                "strategy": "arbitrage",
                "signal_type": ArbitrageSignalType.OPPORTUNITY.value,
            }
        )

        self.logger.info(
            f"Arbitrage opportunity found: profit={opportunity.profit_rate:.2f}%, "
            f"size={opportunity.max_size:.2f}, cost=${opportunity.total_cost:.2f}"
        )

        return signal

    def _analyze_arbitrage(
        self,
        yes_orderbook: OrderBook,
        no_orderbook: OrderBook
    ) -> ArbitrageOpportunity:
        """
        Analyze orderbooks for arbitrage opportunity.

        Args:
            yes_orderbook: YES token orderbook
            no_orderbook: OrderBook for NO token

        Returns:
            ArbitrageOpportunity: Analysis result
        """
        # Parse and validate orderbook levels
        yes_asks = self._parse_orderbook_levels(yes_orderbook.asks)
        no_asks = self._parse_orderbook_levels(no_orderbook.asks)

        if not yes_asks or not no_asks:
            return ArbitrageOpportunity(
                is_profitable=False,
                reason="Orderbook data missing"
            )

        # Calculate total liquidity
        yes_liquidity = sum(level.size for level in yes_asks)
        no_liquidity = sum(level.size for level in no_asks)
        max_possible = min(yes_liquidity, no_liquidity, self.arb_config.max_search_size)

        if max_possible < self.arb_config.min_size:
            return ArbitrageOpportunity(
                is_profitable=False,
                reason=f"Insufficient liquidity (YES: {yes_liquidity:.2f}, NO: {no_liquidity:.2f})",
                yes_liquidity=yes_liquidity,
                no_liquidity=no_liquidity,
            )

        # Search for maximum profitable size
        return self._find_max_profitable_size(yes_asks, no_asks, max_possible)

    def _parse_orderbook_levels(self, levels: List[OrderBookLevel]) -> List[OrderBookLevel]:
        """
        Parse and validate orderbook levels.

        Args:
            levels: List of OrderBookLevel objects

        Returns:
            List[OrderBookLevel]: Validated and sorted levels
        """
        validated = []
        for level in levels:
            if level.price > 0 and level.size > 0:
                validated.append(level)

        # Sort by price ascending (ask side)
        validated.sort(key=lambda x: x.price)
        return validated

    def _find_max_profitable_size(
        self,
        yes_asks: List[OrderBookLevel],
        no_asks: List[OrderBookLevel],
        max_possible: float
    ) -> ArbitrageOpportunity:
        """
        Find maximum profitable size by searching orderbooks.

        Args:
            yes_asks: YES token ask levels
            no_asks: NO token ask levels
            max_possible: Maximum possible size

        Returns:
            ArbitrageOpportunity: Best opportunity found
        """
        best_opportunity = None
        best_profit = 0.0

        current_size = self.arb_config.min_size

        while current_size <= max_possible:
            # Calculate VWAP for this size
            vwap_yes, actual_yes = self._calculate_vwap(yes_asks, current_size)
            vwap_no, actual_no = self._calculate_vwap(no_asks, current_size)

            # Check if both sides can fill the order
            actual_size = min(actual_yes, actual_no)
            if actual_size < current_size * 0.99:  # 99% fill ratio threshold
                break

            # Calculate profitability
            total_cost = vwap_yes + vwap_no
            spread = 1.0 - total_cost
            profit_rate = (spread / total_cost) * 100 if total_cost > 0 else 0

            # Check minimum profit threshold
            if profit_rate < self.arb_config.min_profit_rate:
                break

            # Check maximum profit threshold (safety)
            if profit_rate > self.arb_config.max_profit_rate:
                self.logger.warning(
                    f"Profit rate exceeds safety threshold: {profit_rate:.2f}% > "
                    f"{self.arb_config.max_profit_rate:.2f}%"
                )
                break

            # Track best opportunity
            potential_profit = actual_size * spread
            if potential_profit > best_profit:
                best_profit = potential_profit
                best_opportunity = ArbitrageOpportunity(
                    vwap_yes=vwap_yes,
                    vwap_no=vwap_no,
                    total_cost=total_cost,
                    spread=spread,
                    profit_rate=profit_rate,
                    max_size=actual_size,
                    max_profit=potential_profit,
                    is_profitable=True,
                    reason=f"Profit rate {profit_rate:.2f}% @ {actual_size:.2f} shares",
                    yes_liquidity=sum(level.size for level in yes_asks),
                    no_liquidity=sum(level.size for level in no_asks),
                )

            current_size += self.arb_config.search_step

        if best_opportunity:
            return best_opportunity

        # No profitable opportunity found
        vwap_yes, _ = self._calculate_vwap(yes_asks, self.arb_config.min_size)
        vwap_no, _ = self._calculate_vwap(no_asks, self.arb_config.min_size)
        total_cost = vwap_yes + vwap_no
        spread = 1.0 - total_cost
        profit_rate = (spread / total_cost) * 100 if total_cost > 0 else 0

        return ArbitrageOpportunity(
            vwap_yes=vwap_yes,
            vwap_no=vwap_no,
            total_cost=total_cost,
            spread=spread,
            profit_rate=profit_rate,
            max_size=0,
            max_profit=0,
            is_profitable=False,
            reason=f"Profit rate insufficient ({profit_rate:.2f}% < {self.arb_config.min_profit_rate}%)",
            yes_liquidity=sum(level.size for level in yes_asks),
            no_liquidity=sum(level.size for level in no_asks),
        )

    def _calculate_vwap(
        self,
        levels: List[OrderBookLevel],
        target_size: float
    ) -> Tuple[float, float]:
        """
        Calculate VWAP for target size.

        Args:
            levels: Orderbook levels (sorted ascending)
            target_size: Target size to calculate VWAP for

        Returns:
            Tuple[float, float]: (vwap_price, actual_size)
        """
        if not levels or target_size <= 0:
            return 0.0, 0.0

        total_cost = 0.0
        total_size = 0.0

        for level in levels:
            remaining = target_size - total_size
            if remaining <= 0:
                break

            take_size = min(level.size, remaining)
            total_cost += level.price * take_size
            total_size += take_size

        if total_size == 0:
            return 0.0, 0.0

        vwap = total_cost / total_size
        return vwap, total_size

    def calculate_execution_params(
        self,
        opportunity: ArbitrageOpportunity,
        amount_usdc: float
    ) -> SurebetExecutionParams:
        """
        Calculate order execution parameters.

        Args:
            opportunity: Arbitrage opportunity
            amount_usdc: Investment amount in USDC

        Returns:
            SurebetExecutionParams: Execution parameters
        """
        if not opportunity.is_profitable:
            return SurebetExecutionParams()

        # Calculate size based on opportunity and available capital
        max_size_by_cost = amount_usdc / opportunity.total_cost
        size = min(opportunity.max_size, max_size_by_cost)

        # Apply slippage tolerance
        yes_max_price = opportunity.vwap_yes * (1 + self.arb_config.slippage_tolerance)
        no_max_price = opportunity.vwap_no * (1 + self.arb_config.slippage_tolerance)

        expected_profit = size * opportunity.spread

        params = SurebetExecutionParams(
            yes_size=size,
            yes_max_price=yes_max_price,
            no_size=size,
            no_max_price=no_max_price,
            expected_profit=expected_profit,
            profit_rate=opportunity.profit_rate,
        )

        self.logger.debug(
            f"Execution params: YES={size:.2f}@{yes_max_price:.4f}, "
            f"NO={size:.2f}@{no_max_price:.4f}, profit=${expected_profit:.2f}"
        )

        return params

    def quick_check(self, best_yes_ask: float, best_no_ask: float) -> bool:
        """
        Quick opportunity check using best prices.

        Args:
            best_yes_ask: Best YES ask price
            best_no_ask: Best NO ask price

        Returns:
            bool: True if opportunity likely exists
        """
        if best_yes_ask <= 0 or best_no_ask <= 0:
            return False

        total = best_yes_ask + best_no_ask
        spread = 1.0 - total
        profit_rate = (spread / total) * 100

        # Account for slippage with extra margin
        return profit_rate >= (
            self.arb_config.min_profit_rate +
            self.arb_config.slippage_tolerance * 100
        )

    async def execute_arbitrage(
        self,
        exchange: ExchangeClient,
        params: SurebetExecutionParams
    ) -> Dict[str, Any]:
        """
        Execute arbitrage orders simultaneously.

        Args:
            exchange: Exchange client instance
            params: Execution parameters

        Returns:
            Dict with execution results
        """
        if not params.yes_size or not params.no_size:
            return {
                "success": False,
                "message": "Invalid execution parameters",
            }

        self.logger.info(
            f"Executing arbitrage: YES={params.yes_size:.2f}@{params.yes_max_price:.4f}, "
            f"NO={params.no_size:.2f}@{params.no_max_price:.4f}"
        )

        try:
            # Execute both legs simultaneously
            import asyncio

            yes_task = exchange.buy(
                symbol="YES_TOKEN",
                size=params.yes_size,
                price=params.yes_max_price,
                order_type=OrderType.LIMIT,
            )

            no_task = exchange.buy(
                symbol="NO_TOKEN",
                size=params.no_size,
                price=params.no_max_price,
                order_type=OrderType.LIMIT,
            )

            results = await asyncio.gather(yes_task, no_task, return_exceptions=True)

            yes_order = results[0]
            no_order = results[1]

            yes_filled = not isinstance(yes_order, Exception) and yes_order.is_filled
            no_filled = not isinstance(no_order, Exception) and no_order.is_filled

            if yes_filled and no_filled:
                self.logger.info(f"Arbitrage executed successfully: +{params.profit_rate:.2f}%")
                return {
                    "success": True,
                    "yes_filled": True,
                    "no_filled": True,
                    "panic_mode": False,
                    "message": f"Arbitrage success (+{params.profit_rate:.2f}%)",
                }

            # Handle panic mode if one leg failed
            if self.arb_config.panic_mode_enabled and (yes_filled != no_filled):
                filled_side = "YES" if yes_filled else "NO"
                filled_size = params.yes_size if yes_filled else params.no_size
                self.logger.warning(f"Panic mode triggered: {filled_side} filled only")

                # Attempt to close the filled leg
                await self._handle_panic_mode(exchange, filled_side, filled_size, params)

                return {
                    "success": False,
                    "yes_filled": yes_filled,
                    "no_filled": no_filled,
                    "panic_mode": True,
                    "message": f"Panic mode - {filled_side} only filled",
                }

            return {
                "success": False,
                "yes_filled": yes_filled,
                "no_filled": no_filled,
                "panic_mode": False,
                "message": "Both orders failed",
            }

        except Exception as e:
            self.logger.error(f"Arbitrage execution error: {e}")
            return {
                "success": False,
                "message": f"Execution error: {e}",
            }

    async def _handle_panic_mode(
        self,
        exchange: ExchangeClient,
        filled_side: str,
        filled_size: float,
        params: SurebetExecutionParams
    ) -> bool:
        """
        Handle panic mode by closing the filled leg.

        Args:
            exchange: Exchange client
            filled_side: Which side was filled ("YES" or "NO")
            filled_size: Size that was filled
            params: Original execution parameters

        Returns:
            bool: True if panic close succeeded
        """
        self.logger.info(f"Panic mode: Closing {filled_side} {filled_size:.2f} shares")

        try:
            # Calculate panic price with additional slippage
            if filled_side == "YES":
                panic_price = params.yes_max_price * (1 - self.arb_config.panic_slippage)
            else:
                panic_price = params.no_max_price * (1 - self.arb_config.panic_slippage)

            # Execute sell order
            order = await exchange.sell(
                symbol=f"{filled_side}_TOKEN",
                size=filled_size,
                price=panic_price,
                order_type=OrderType.IOC,  # Immediate-or-Cancel
            )

            if order.is_filled:
                self.logger.info(f"Panic mode: Successfully closed {filled_side} position")
                return True
            else:
                self.logger.error(f"Panic mode: Failed to close {filled_side} position")
                return False

        except Exception as e:
            self.logger.error(f"Panic mode error: {e}")
            return False

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SurebetEngine("
            f"enabled={self.config.enabled}, "
            f"min_profit={self.arb_config.min_profit_rate}%, "
            f"max_cost=${self.arb_config.max_total_cost})"
        )


__all__ = [
    "SurebetEngine",
    "ArbitrageConfig",
    "ArbitrageOpportunity",
    "SurebetExecutionParams",
    "ArbitrageSignalType",
]
