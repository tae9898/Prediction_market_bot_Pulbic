"""
코어 인터페이스 모듈

트레이딩 봇 아키텍처를 위한 추상 인터페이스를 정의합니다.
"""

from core.interfaces.strategy_base import (
    BaseStrategy,
    StrategyConfig,
    MarketSignal,
    SignalAction,
    SignalDirection,
)

from core.interfaces.exchange_base import (
    ExchangeClient,
    MarketData,
    OrderBook,
    Position,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)

from core.interfaces.data_feed_base import (
    DataFeed,
    DataFeedConfig,
    SubscriptionCallback,
)

__all__ = [
    # Strategy interfaces
    "BaseStrategy",
    "StrategyConfig",
    "MarketSignal",
    "SignalAction",
    "SignalDirection",
    # Exchange interfaces
    "ExchangeClient",
    "MarketData",
    "OrderBook",
    "Position",
    "Order",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    # Data feed interfaces
    "DataFeed",
    "DataFeedConfig",
    "SubscriptionCallback",
]
