"""
Exchange Adapters - Universal Interface Implementation

This module provides adapter classes that implement the core interfaces
while wrapping the existing exchange implementations.

This approach maintains backward compatibility - existing code continues to work,
while new code can use the universal interface.
"""

import asyncio
import time
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from core.interfaces.exchange_base import (
    ExchangeClient,
    MarketData,
    OrderBook,
    OrderBookLevel,
    Position,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)

from core.interfaces.data_feed_base import (
    DataFeed,
    DataFeedConfig,
)

# Import existing implementations
from exchanges.binance import BinanceFeed, BinanceData
from exchanges.polymarket import PolymarketClient, MarketData as PolymarketMarketData, Position as PolymarketPosition


class PolymarketExchangeAdapter(ExchangeClient):
    """
    Adapter for PolymarketClient to implement ExchangeClient interface.

    Wraps the existing PolymarketClient and provides the universal interface
    while maintaining full backward compatibility.
    """

    def __init__(self, polymarket_client: PolymarketClient):
        """
        Initialize adapter with existing PolymarketClient instance.

        Args:
            polymarket_client: Existing PolymarketClient instance
        """
        super().__init__(exchange_name="polymarket", logger=None)
        self._client = polymarket_client

    async def connect(self) -> bool:
        """
        Connect to Polymarket.

        Returns:
            bool: Connection success
        """
        if not self._client.is_initialized:
            result = await self._client.initialize()
            self._connected = result
            return result
        return True

    async def disconnect(self) -> None:
        """Disconnect from Polymarket."""
        await self._client.close()
        self._connected = False

    async def buy(
        self,
        symbol: str,
        size: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET
    ) -> Order:
        """
        Execute buy order.

        Args:
            symbol: Symbol (e.g., "BTC-UP", "BTC-DOWN")
            size: Order size
            price: Price (for limit orders)
            order_type: Order type

        Returns:
            Order: Created order
        """
        # Parse direction from symbol
        direction = "UP" if "UP" in symbol.upper() else "DOWN"

        # Get current price if not specified
        if price is None:
            price = self._client.market.up_ask if direction == "UP" else self._client.market.down_ask

        # Execute buy using wrapper method (which calls _buy_internal)
        # We need to compute amount_usdc from size
        amount_usdc = size * price if price else 0.0
        success = await self._client.buy(
            direction=direction,
            amount_usdc=amount_usdc,
            size=size
        )

        # Create Order object
        order_id = f"poly_{int(time.time() * 1000)}"
        status = OrderStatus.FILLED if success else OrderStatus.REJECTED

        return Order(
            order_id=order_id,
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=order_type,
            price=price,
            size=size,
            filled_size=size if success else 0.0,
            status=status
        )

    async def sell(
        self,
        symbol: str,
        size: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET
    ) -> Order:
        """
        Execute sell order.

        Args:
            symbol: Symbol (e.g., "BTC-UP", "BTC-DOWN")
            size: Order size
            price: Price (for limit orders)
            order_type: Order type

        Returns:
            Order: Created order
        """
        # Parse direction from symbol
        direction = "UP" if "UP" in symbol.upper() else "DOWN"

        # Get current price if not specified
        if price is None:
            price = self._client.market.up_bid if direction == "UP" else self._client.market.down_bid

        # Execute sell using wrapper method (which calls _sell_internal)
        success = await self._client.sell(
            direction=direction,
            size=size
        )

        # Create Order object
        order_id = f"poly_{int(time.time() * 1000)}"
        status = OrderStatus.FILLED if success else OrderStatus.REJECTED

        return Order(
            order_id=order_id,
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=order_type,
            price=price,
            size=size,
            filled_size=size if success else 0.0,
            status=status
        )

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order.

        Note: Polymarket CLOB does not support order cancellation after posting.

        Args:
            order_id: Order ID

        Returns:
            bool: Cancellation success
        """
        # Not supported by Polymarket
        return False

    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for symbol.

        Args:
            symbol: Symbol

        Returns:
            Position: Position data or None
        """
        if not self._client.has_position:
            return None

        # Get current price
        current_price = (
            self._client.market.up_bid if self._client.position.direction == "UP"
            else self._client.market.down_bid
        )

        return Position(
            symbol=symbol,
            side="LONG",  # Polymarket positions are always LONG on outcome
            size=self._client.position.size,
            entry_price=self._client.position.avg_price,
            current_price=current_price,
            unrealized_pnl=self._client.position.unrealized_pnl,
            realized_pnl=self._client.realized_pnl,
            timestamp=time.time()
        )

    async def get_balance(self) -> Dict[str, float]:
        """
        Get account balances.

        Returns:
            Dict[str, float]: Asset balances (e.g., {"USDC": 1000.0})
        """
        usdc_balance = await self._client.get_usdc_balance()
        return {"USDC": usdc_balance}

    async def get_order_status(self, order_id: str) -> Order:
        """
        Get order status.

        Args:
            order_id: Order ID

        Returns:
            Order: Order status
        """
        # Polymarket orders are typically filled immediately
        return Order(
            order_id=order_id,
            symbol="",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=0.0,
            size=0.0,
            status=OrderStatus.FILLED
        )

    def is_connected(self) -> bool:
        """
        Check connection status.

        Returns:
            bool: Connected status
        """
        return self._client.is_initialized

    # Adapter methods to convert internal data to universal format

    def to_market_data(self) -> MarketData:
        """
        Convert internal PolymarketMarketData to universal MarketData.

        Returns:
            MarketData: Universal market data
        """
        symbol = f"{self._client.asset_type}-UP"
        avg_bid = (self._client.market.up_bid + self._client.market.down_bid) / 2
        avg_ask = (self._client.market.up_ask + self._client.market.down_ask) / 2

        return MarketData(
            symbol=symbol,
            price=avg_ask,
            volume=self._client.position.size,
            timestamp=self._client.market.last_update,
            bid=avg_bid if avg_bid > 0 else None,
            ask=avg_ask if avg_ask > 0 else None
        )

    def to_orderbook(self) -> OrderBook:
        """
        Convert internal orderbook to universal OrderBook.

        Returns:
            OrderBook: Universal order book
        """
        symbol = f"{self._client.asset_type}-UP"

        bids = [
            OrderBookLevel(price=float(b.get("price", 0)), size=float(b.get("size", 0)))
            for b in self._client.market.yes_bids[:10]
        ]
        asks = [
            OrderBookLevel(price=float(a.get("price", 0)), size=float(a.get("size", 0)))
            for a in self._client.market.yes_asks[:10]
        ]

        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=self._client.market.last_update
        )


class BinanceFeedAdapter(DataFeed):
    """
    Adapter for BinanceFeed to implement DataFeed interface.

    Wraps the existing BinanceFeed and provides the universal interface
    while maintaining full backward compatibility.
    """

    def __init__(self, binance_feed: BinanceFeed):
        """
        Initialize adapter with existing BinanceFeed instance.

        Args:
            binance_feed: Existing BinanceFeed instance
        """
        config = DataFeedConfig(
            name=f"binance_{binance_feed.symbol}",
            enable_websocket=True,
            symbols=[binance_feed.symbol]
        )
        super().__init__(config=config, logger=None)
        self._feed = binance_feed

    async def connect(self) -> bool:
        """
        Connect to Binance WebSocket.

        Returns:
            bool: Connection success
        """
        try:
            # Start the feed in background
            asyncio.create_task(self._feed.start())
            await asyncio.sleep(1)  # Give it a moment to connect
            self._connected = self._feed.is_connected
            return self._connected
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Binance."""
        await self._feed.stop()
        self._connected = False

    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get market data for symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Dict: Market data or None
        """
        if symbol.upper() != self._feed.symbol.upper():
            return None

        return {
            "symbol": self._feed.symbol,
            "price": self._feed.get_price(),
            "volume_24h": self._feed.data.volume_24h,
            "change_24h": self._feed.data.price_change_24h,
            "change_pct_24h": self._feed.data.price_change_pct_24h,
            "high_24h": self._feed.data.high_24h,
            "low_24h": self._feed.data.low_24h,
            "timestamp": self._feed.data.last_update,
            "volatility": self._feed.calculate_volatility(),
            "momentum": self._feed.get_momentum()
        }

    async def get_orderbook(self, symbol: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """
        Get orderbook for symbol.

        Note: BinanceFeed doesn't currently store full orderbook.
        This returns aggregated bid/ask from ticker data.

        Args:
            symbol: Trading symbol
            limit: Depth (not currently used)

        Returns:
            Dict: Orderbook data or None
        """
        if symbol.upper() != self._feed.symbol.upper():
            return None

        # Return best bid/ask from ticker
        stats = self._feed.get_24h_stats()

        return {
            "symbol": symbol,
            "bids": [{"price": stats.get("high", 0), "size": 1.0}],  # Placeholder
            "asks": [{"price": stats.get("low", 0), "size": 1.0}],   # Placeholder
            "timestamp": time.time()
        }

    async def _data_loop(self) -> None:
        """
        Data receive loop.

        Overrides base implementation to notify subscribers of price updates.
        """
        while self._running:
            try:
                # Notify subscribers with current data
                if self._feed.symbol in self._subscriptions:
                    data = await self.get_market_data(self._feed.symbol)
                    if data:
                        await self._notify_subscribers(self._feed.symbol, data)

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Data loop error: {e}")
                await asyncio.sleep(self.config.reconnect_interval)


# Factory functions for creating adapters

def create_polymarket_adapter(private_key: str, **kwargs) -> PolymarketExchangeAdapter:
    """
    Create Polymarket adapter with client.

    Args:
        private_key: Wallet private key
        **kwargs: Additional arguments for PolymarketClient

    Returns:
        PolymarketExchangeAdapter: Configured adapter
    """
    client = PolymarketClient(private_key=private_key, **kwargs)
    return PolymarketExchangeAdapter(client)


def create_binance_adapter(symbol: str = "BTC", **kwargs) -> BinanceFeedAdapter:
    """
    Create Binance adapter with feed.

    Args:
        symbol: Trading symbol
        **kwargs: Additional arguments for BinanceFeed

    Returns:
        BinanceFeedAdapter: Configured adapter
    """
    feed = BinanceFeed(symbol=symbol, **kwargs)
    return BinanceFeedAdapter(feed)


__all__ = [
    "PolymarketExchangeAdapter",
    "BinanceFeedAdapter",
    "create_polymarket_adapter",
    "create_binance_adapter",
]
