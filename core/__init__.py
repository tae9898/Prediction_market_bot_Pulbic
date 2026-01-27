"""
코어 모듈

트레이딩 봇의 핵심 인터페이스와 기본 클래스를 제공합니다.
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

from core.registry import (
    StrategyRegistry,
    ExchangeRegistry,
    RegistrationError,
    ValidationError,
    strategy_registry,
    exchange_registry,
    register_strategy,
    register_exchange,
    get_strategy,
    get_exchange,
    list_strategies,
    list_exchanges,
)

from core.context import (
    ExecutionContext,
    BotState,
)

from core.engine import (
    TradingEngine,
    EngineConfig,
    AggregatedSignal,
    TradeResult,
    ConflictResolution,
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
    # Registry
    "StrategyRegistry",
    "ExchangeRegistry",
    "RegistrationError",
    "ValidationError",
    "strategy_registry",
    "exchange_registry",
    "register_strategy",
    "register_exchange",
    "get_strategy",
    "get_exchange",
    "list_strategies",
    "list_exchanges",
    # Context
    "ExecutionContext",
    "BotState",
    # Engine
    "TradingEngine",
    "EngineConfig",
    "AggregatedSignal",
    "TradeResult",
    "ConflictResolution",
]
