"""
Edge Hedge Strategy Implementation

Edge-based entry with dynamic hedging strategy for binary options trading.

Strategy Overview:
1. Entry: Enter when FAIR probability > Market probability (edge >= min_edge_pct%)
2. Profit Taking: Hedge with opposite position when price rises (profit_hedge_threshold_pct%)
3. Stop Loss: Hedge with opposite position when price drops (stoploss_trigger_pct%)
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from core.interfaces.strategy_base import (
    BaseStrategy,
    StrategyConfig,
    MarketSignal,
    SignalAction,
    SignalDirection,
)
from core.registry import register_strategy
from strategies.edge_hedge.config import EdgeHedgeConfig


@dataclass
class EdgeHedgePosition:
    """
    Edge Hedge Position State

    Tracks current position and hedging status for each asset.

    Attributes:
        asset_type: Asset symbol (e.g., "BTC", "ETH")
        direction: Position direction ("UP" or "DOWN")
        entry_price: Entry price (market probability at entry)
        entry_fair: FAIR probability at entry
        entry_edge: Edge value at entry
        size: Position size
        cost: Position cost
        entry_time: Entry timestamp
        is_hedged: Whether position is hedged
        hedge_direction: Hedge direction (opposite of entry)
        hedge_price: Price at which hedge was executed
        hedge_size: Size of hedge position
        hedge_cost: Cost of hedge position
        hedge_type: Hedge type ("PROFIT" or "STOPLOSS")
        expected_profit: Expected profit from hedge
    """
    asset_type: str = ""
    direction: str = ""  # "UP" or "DOWN"
    entry_price: float = 0.0
    entry_fair: float = 0.0
    entry_edge: float = 0.0
    size: float = 0.0
    cost: float = 0.0
    entry_time: float = 0.0

    # Hedge state
    is_hedged: bool = False
    hedge_direction: str = ""
    hedge_price: float = 0.0
    hedge_size: float = 0.0
    hedge_cost: float = 0.0
    hedge_type: str = ""  # "PROFIT" or "STOPLOSS"

    # Expected P&L
    expected_profit: float = 0.0


@register_strategy("edge_hedge", validate=True)
class EdgeHedgeStrategy(BaseStrategy):
    """
    Edge Hedge Strategy

    Implements edge-based entry with dynamic hedging for binary options trading.

    Key Features:
    - Edge-based entry using FAIR vs Market probability
    - Profit-taking hedge when position appreciates
    - Stop-loss hedge when position depreciates
    - Position state management via ExecutionContext
    - Universal MarketData and OrderBook format support
    """

    def __init__(self, config: EdgeHedgeConfig, logger=None):
        """
        Initialize Edge Hedge Strategy

        Args:
            config: EdgeHedgeConfig instance
            logger: Optional logger instance
        """
        # Initialize with parent class
        super().__init__(config, logger)

        # Cast config to proper type
        if not isinstance(config, EdgeHedgeConfig):
            raise TypeError(f"config must be EdgeHedgeConfig, got {type(config)}")

        self.config: EdgeHedgeConfig = config

        # Position tracking (will be stored in execution context)
        self._positions: Dict[str, EdgeHedgePosition] = {}

        # Entry timing tracking
        self._last_entry_time: Dict[str, float] = {}

    def validate_config(self) -> bool:
        """
        Validate strategy configuration

        Returns:
            bool: True if configuration is valid
        """
        try:
            # Config validation happens in __post_init__
            # Additional runtime validation here

            # Check for reasonable parameter relationships
            if self.config.profit_hedge_threshold_pct >= self.config.stoploss_trigger_pct:
                self.logger.error(
                    f"Invalid hedge thresholds: profit ({self.config.profit_hedge_threshold_pct}%) "
                    f"must be less than stoploss ({self.config.stoploss_trigger_pct}%)"
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def analyze(
        self,
        market_data: Dict[str, Any],
        position: Optional[Dict[str, Any]] = None
    ) -> Optional[MarketSignal]:
        """
        Analyze market data and generate trading signals

        Args:
            market_data: Dictionary containing market data
                Expected keys:
                    - "symbol": Asset symbol (e.g., "BTC", "ETH")
                    - "fair_up": FAIR probability for UP
                    - "fair_down": FAIR probability for DOWN
                    - "market_up": Market probability for UP (bid)
                    - "market_down": Market probability for DOWN (bid)
                    - "orderbook": Optional OrderBook object for ask prices
            position: Current position info (optional)

        Returns:
            MarketSignal: Generated signal or None
        """
        # Check if strategy is enabled
        if not self.config.enabled:
            return None

        # Extract symbol
        symbol = market_data.get("symbol", "")
        if not symbol:
            self.logger.warning("Market data missing 'symbol' key")
            return None

        # Get current position
        current_position = self._positions.get(symbol)

        # Extract market probabilities
        fair_up = market_data.get("fair_up", 0.0)
        fair_down = market_data.get("fair_down", 0.0)
        market_up = market_data.get("market_up", 0.0)
        market_down = market_data.get("market_down", 0.0)

        # Validate inputs
        if not all([fair_up, fair_down, market_up, market_down]):
            self.logger.warning(f"[{symbol}] Missing probability data")
            return None

        # Check if we have an open position
        if current_position and current_position.size > 0 and not current_position.is_hedged:
            # Analyze hedge opportunities
            signal = self._analyze_hedge_opportunities(
                symbol,
                current_position,
                market_data
            )
            if signal:
                return signal

        # Analyze entry opportunities (only if no open position)
        if not current_position or current_position.size <= 0:
            # Check cooldown for entries
            if self._is_in_cooldown(symbol):
                self.logger.debug(f"[{symbol}] In cooldown period")
                return None

            signal = self._analyze_entry_opportunity(
                symbol,
                fair_up,
                fair_down,
                market_up,
                market_down
            )
            if signal:
                return signal

        return None

    def _is_in_cooldown(self, symbol: str) -> bool:
        """
        Check if symbol is in cooldown period

        Args:
            symbol: Asset symbol

        Returns:
            bool: True if in cooldown
        """
        last_entry = self._last_entry_time.get(symbol, 0)
        return (time.time() - last_entry) < self.config.entry_cooldown_sec

    def _analyze_entry_opportunity(
        self,
        symbol: str,
        fair_up: float,
        fair_down: float,
        market_up: float,
        market_down: float
    ) -> Optional[MarketSignal]:
        """
        Analyze entry opportunities

        Args:
            symbol: Asset symbol
            fair_up: FAIR UP probability
            fair_down: FAIR DOWN probability
            market_up: Market UP probability
            market_down: Market DOWN probability

        Returns:
            MarketSignal: Entry signal or None
        """
        # Calculate edges
        edge_up = (fair_up - market_up) * 100
        edge_down = (fair_down - market_down) * 100

        # Choose direction with higher FAIR probability
        if fair_up > fair_down:
            # UP more likely
            if edge_up >= self.config.min_edge_pct:
                confidence = min(0.9, 0.5 + (edge_up / 100))  # Scale confidence with edge

                self.logger.info(
                    f"[{symbol}] Entry opportunity: UP | "
                    f"Edge: +{edge_up:.2f}% | "
                    f"FAIR: {fair_up*100:.1f}% | Market: {market_up*100:.1f}%"
                )

                return MarketSignal(
                    action=SignalAction.ENTER,
                    direction=SignalDirection.LONG,
                    confidence=confidence,
                    edge=edge_up,
                    reason=f"FAIR UP ({fair_up*100:.1f}%) > Market UP ({market_up*100:.1f}%) with edge {edge_up:.1f}%",
                    metadata={
                        "fair_price": fair_up,
                        "market_price": market_up,
                        "opposite_market": market_down,
                        "asset_type": symbol,
                    }
                )
            else:
                self.logger.debug(
                    f"[{symbol}] Skip UP: Edge {edge_up:.2f}% < {self.config.min_edge_pct}%"
                )
        else:
            # DOWN more likely
            if edge_down >= self.config.min_edge_pct:
                confidence = min(0.9, 0.5 + (edge_down / 100))

                self.logger.info(
                    f"[{symbol}] Entry opportunity: DOWN | "
                    f"Edge: +{edge_down:.2f}% | "
                    f"FAIR: {fair_down*100:.1f}% | Market: {market_down*100:.1f}%"
                )

                return MarketSignal(
                    action=SignalAction.ENTER,
                    direction=SignalDirection.SHORT,
                    confidence=confidence,
                    edge=edge_down,
                    reason=f"FAIR DOWN ({fair_down*100:.1f}%) > Market DOWN ({market_down*100:.1f}%) with edge {edge_down:.1f}%",
                    metadata={
                        "fair_price": fair_down,
                        "market_price": market_down,
                        "opposite_market": market_up,
                        "asset_type": symbol,
                    }
                )
            else:
                self.logger.debug(
                    f"[{symbol}] Skip DOWN: Edge {edge_down:.2f}% < {self.config.min_edge_pct}%"
                )

        return None

    def _analyze_hedge_opportunities(
        self,
        symbol: str,
        position: EdgeHedgePosition,
        market_data: Dict[str, Any]
    ) -> Optional[MarketSignal]:
        """
        Analyze hedge opportunities (profit-taking or stop-loss)

        Args:
            symbol: Asset symbol
            position: Current position
            market_data: Market data dictionary

        Returns:
            MarketSignal: Hedge signal or None
        """
        # Extract orderbook for ask prices
        orderbook = market_data.get("orderbook")
        if not orderbook:
            self.logger.debug(f"[{symbol}] No orderbook data for hedge analysis")
            return None

        market_up = market_data.get("market_up", 0.0)
        market_down = market_data.get("market_down", 0.0)

        # Get best bid/ask from orderbook
        # Using orderbook methods if available, otherwise use market data
        if hasattr(orderbook, "get_best_bid") and hasattr(orderbook, "get_best_ask"):
            best_up_bid = orderbook.get_best_bid()
            best_up_ask = orderbook.get_best_ask()
            market_up_bid = best_up_bid.price if best_up_bid else market_up
            market_up_ask = best_up_ask.price if best_up_ask else market_up

            # For DOWN options, use symmetric logic (1 - UP price)
            # since binary options are complementary
            market_down_bid = 1.0 - market_up_ask if market_up_ask else market_down
            market_down_ask = 1.0 - market_up_bid if market_up_bid else market_down
        else:
            market_up_bid = market_up
            market_up_ask = market_up
            market_down_bid = market_down
            market_down_ask = market_down

        # Check profit-taking hedge first
        profit_signal = self._analyze_profit_hedge(
            symbol,
            position,
            market_up_bid,
            market_down_bid,
            market_up_ask,
            market_down_ask
        )
        if profit_signal:
            return profit_signal

        # Check stop-loss hedge
        stoploss_signal = self._analyze_stoploss_hedge(
            symbol,
            position,
            market_up_bid,
            market_down_bid,
            market_up_ask,
            market_down_ask
        )
        if stoploss_signal:
            return stoploss_signal

        return None

    def _analyze_profit_hedge(
        self,
        symbol: str,
        position: EdgeHedgePosition,
        market_up_bid: float,
        market_down_bid: float,
        market_up_ask: float,
        market_down_ask: float
    ) -> Optional[MarketSignal]:
        """
        Analyze profit-taking hedge opportunity

        Args:
            symbol: Asset symbol
            position: Current position
            market_up_bid: Current UP bid price
            market_down_bid: Current DOWN bid price
            market_up_ask: Current UP ask price
            market_down_ask: Current DOWN ask price

        Returns:
            MarketSignal: Hedge signal or None
        """
        # Determine current value price and hedge cost price
        if position.direction == "UP":
            current_val_price = market_up_bid
            hedge_cost_price = market_down_ask
            hedge_direction = SignalDirection.SHORT
        else:  # DOWN
            current_val_price = market_down_bid
            hedge_cost_price = market_up_ask
            hedge_direction = SignalDirection.LONG

        # Calculate price change percentage
        price_change_pct = ((current_val_price - position.entry_price) / position.entry_price) * 100

        # Check profit-taking threshold
        if price_change_pct >= self.config.profit_hedge_threshold_pct:
            # Calculate total cost and expected profit
            total_cost = position.entry_price + hedge_cost_price
            expected_profit_pct = (1.0 - total_cost) * 100

            # Critical check: total cost must be < 100% for profit
            if total_cost >= 1.0:
                self.logger.debug(
                    f"[{symbol}] Cannot hedge profitably: total cost {total_cost*100:.1f}% >= 100%"
                )
                return None

            if expected_profit_pct > 0:
                self.logger.info(
                    f"[{symbol}] PROFIT HEDGE: {hedge_direction.value.upper()} | "
                    f"Gain: +{price_change_pct:.1f}% | "
                    f"Expected: +{expected_profit_pct:.2f}%"
                )

                return MarketSignal(
                    action=SignalAction.ADJUST,
                    direction=hedge_direction,
                    confidence=0.8,
                    edge=expected_profit_pct,
                    reason=f"Profit hedge: Position up {price_change_pct:.1f}%, expected profit {expected_profit_pct:.2f}%",
                    metadata={
                        "hedge_type": "PROFIT",
                        "hedge_price": hedge_cost_price,
                        "expected_profit_pct": expected_profit_pct,
                        "position_gain_pct": price_change_pct,
                        "total_cost": total_cost,
                        "asset_type": symbol,
                    }
                )

        return None

    def _analyze_stoploss_hedge(
        self,
        symbol: str,
        position: EdgeHedgePosition,
        market_up_bid: float,
        market_down_bid: float,
        market_up_ask: float,
        market_down_ask: float
    ) -> Optional[MarketSignal]:
        """
        Analyze stop-loss hedge opportunity

        Args:
            symbol: Asset symbol
            position: Current position
            market_up_bid: Current UP bid price
            market_down_bid: Current DOWN bid price
            market_up_ask: Current UP ask price
            market_down_ask: Current DOWN ask price

        Returns:
            MarketSignal: Hedge signal or None
        """
        # Determine current value price and hedge cost price
        if position.direction == "UP":
            current_val_price = market_up_bid
            hedge_cost_price = market_down_ask
            hedge_direction = SignalDirection.SHORT
        else:  # DOWN
            current_val_price = market_down_bid
            hedge_cost_price = market_up_ask
            hedge_direction = SignalDirection.LONG

        # Calculate price change percentage
        price_change_pct = ((current_val_price - position.entry_price) / position.entry_price) * 100

        # Debug log for losses > 5%
        if price_change_pct <= -5.0:
            self.logger.debug(
                f"[{symbol}] Loss: {price_change_pct:.1f}% "
                f"(Entry: {position.entry_price:.3f}, Current: {current_val_price:.3f})"
            )

        # Check stop-loss threshold
        if price_change_pct <= -self.config.stoploss_trigger_pct:
            # Calculate total cost and expected P&L
            total_cost = position.entry_price + hedge_cost_price
            expected_pnl_pct = (1.0 - total_cost) * 100

            self.logger.info(
                f"[{symbol}] STOPLOSS HEDGE: {hedge_direction.value.upper()} | "
                f"Loss: {price_change_pct:.1f}% | "
                f"Expected: {'+' if expected_pnl_pct >= 0 else ''}{expected_pnl_pct:.2f}%"
            )

            return MarketSignal(
                action=SignalAction.ADJUST,
                direction=hedge_direction,
                confidence=0.9,  # High confidence for stop-loss
                edge=abs(price_change_pct),
                reason=f"Stop-loss hedge: Position down {abs(price_change_pct):.1f}%, expected P&L {expected_pnl_pct:.2f}%",
                metadata={
                    "hedge_type": "STOPLOSS",
                    "hedge_price": hedge_cost_price,
                    "expected_pnl_pct": expected_pnl_pct,
                    "position_loss_pct": price_change_pct,
                    "total_cost": total_cost,
                    "asset_type": symbol,
                }
            )

        return None

    def record_entry(
        self,
        symbol: str,
        direction: SignalDirection,
        entry_price: float,
        fair_price: float,
        edge: float,
        size: float,
        cost: float
    ) -> None:
        """
        Record entry into position

        Args:
            symbol: Asset symbol
            direction: Entry direction
            entry_price: Entry price
            fair_price: FAIR price at entry
            edge: Edge value at entry
            size: Position size
            cost: Position cost
        """
        direction_str = "UP" if direction == SignalDirection.LONG else "DOWN"

        self._positions[symbol] = EdgeHedgePosition(
            asset_type=symbol,
            direction=direction_str,
            entry_price=entry_price,
            entry_fair=fair_price,
            entry_edge=edge,
            size=size,
            cost=cost,
            entry_time=time.time()
        )

        self._last_entry_time[symbol] = time.time()

        self.logger.info(
            f"[{symbol}] Entry: {direction_str} @{entry_price * 100:.1f}% "
            f"(Edge: +{edge:.1f}%, Size: ${size:.2f})"
        )

    def record_hedge(
        self,
        symbol: str,
        hedge_type: str,
        hedge_direction: SignalDirection,
        hedge_price: float,
        hedge_size: float,
        hedge_cost: float,
        expected_profit: float
    ) -> None:
        """
        Record hedge execution

        Args:
            symbol: Asset symbol
            hedge_type: Hedge type ("PROFIT" or "STOPLOSS")
            hedge_direction: Hedge direction
            hedge_price: Hedge execution price
            hedge_size: Hedge size
            hedge_cost: Hedge cost
            expected_profit: Expected profit/loss
        """
        position = self._positions.get(symbol)
        if not position:
            self.logger.warning(f"[{symbol}] No position to hedge")
            return

        hedge_direction_str = "UP" if hedge_direction == SignalDirection.LONG else "DOWN"

        position.is_hedged = True
        position.hedge_type = hedge_type
        position.hedge_direction = hedge_direction_str
        position.hedge_price = hedge_price
        position.hedge_size = hedge_size
        position.hedge_cost = hedge_cost
        position.expected_profit = expected_profit

        profit_str = f"+{expected_profit:.2f}" if expected_profit >= 0 else f"{expected_profit:.2f}"

        self.logger.info(
            f"[{symbol}] {hedge_type} Hedge: {hedge_direction_str} "
            f"@{hedge_price * 100:.1f}% "
            f"(Expected: {profit_str}%)"
        )

    def clear_position(self, symbol: str) -> None:
        """
        Clear position (e.g., after market expiry)

        Args:
            symbol: Asset symbol
        """
        if symbol in self._positions:
            del self._positions[symbol]
            self.logger.info(f"[{symbol}] Position cleared (market expiry)")

    def get_position_status(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current position status

        Args:
            symbol: Asset symbol

        Returns:
            Dict with position status or None
        """
        position = self._positions.get(symbol)
        if not position or position.size <= 0:
            return None

        return {
            "direction": position.direction,
            "entry_price": position.entry_price,
            "entry_fair": position.entry_fair,
            "entry_edge": position.entry_edge,
            "size": position.size,
            "cost": position.cost,
            "entry_time": position.entry_time,
            "is_hedged": position.is_hedged,
            "hedge_type": position.hedge_type,
            "hedge_direction": position.hedge_direction,
            "hedge_price": position.hedge_price,
            "hedge_size": position.hedge_size,
            "hedge_cost": position.hedge_cost,
            "expected_profit": position.expected_profit,
        }

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all positions

        Returns:
            Dict mapping symbols to position status
        """
        return {
            symbol: self.get_position_status(symbol)
            for symbol in self._positions
            if self.get_position_status(symbol) is not None
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"EdgeHedgeStrategy("
            f"name={self.config.name}, "
            f"enabled={self.config.enabled}, "
            f"positions={len(self._positions)})"
        )
