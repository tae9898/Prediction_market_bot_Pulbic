"""
Exchange Module

General-purpose exchange integration module for:
- Binance: Real-time cryptocurrency price feeds
- Polymarket: Prediction market trading via CLOB

This module provides exchange-agnostic interfaces for market data
and trading operations.

Both exchanges now implement core interfaces:
- BinanceFeed implements DataFeed
- PolymarketClient implements ExchangeClient

Backward compatibility is maintained - existing code continues to work.
"""

from .binance import BinanceFeed, BinanceData
from .polymarket import (
    PolymarketClient,
    MarketData as PolymarketMarketData,
    Position as PolymarketPosition,
)

# Backward compatibility aliases
MarketData = PolymarketMarketData
Position = PolymarketPosition

# Adapters for universal interface
try:
    from .adapters import (
        PolymarketExchangeAdapter,
        BinanceFeedAdapter,
        create_polymarket_adapter,
        create_binance_adapter,
    )
    HAS_ADAPTERS = True
except ImportError:
    HAS_ADAPTERS = False

__all__ = [
    # Original classes (backward compatible)
    "BinanceFeed",
    "BinanceData",
    "PolymarketClient",
    "MarketData",
    "Position",
]

# Add adapters if available
if HAS_ADAPTERS:
    __all__.extend([
        "PolymarketExchangeAdapter",
        "BinanceFeedAdapter",
        "create_polymarket_adapter",
        "create_binance_adapter",
    ])
