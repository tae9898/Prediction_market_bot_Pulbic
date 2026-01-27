"""
거래소 기반 인터페이스

모든 거래소 클라이언트가 구현해야 할 추상 기본 클래스와 데이터 모델을 정의합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
import logging


class OrderSide(Enum):
    """주문 방향"""
    BUY = "buy"  # 매수 (UP)
    SELL = "sell"  # 매도 (DOWN)


class OrderType(Enum):
    """주문 타입"""
    MARKET = "market"  # 시장가
    LIMIT = "limit"  # 지정가
    IOC = "ioc"  # Immediate-or-Cancel


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "pending"  # 대기 중
    OPEN = "open"  # 체결 대기
    FILLED = "filled"  # 전체 체결
    PARTIALLY_FILLED = "partially_filled"  # 부분 체결
    CANCELLED = "cancelled"  # 취소
    REJECTED = "rejected"  # 거부
    EXPIRED = "expired"  # 만료


@dataclass
class MarketData:
    """
    시장 데이터 클래스

    Attributes:
        symbol: 심볼
        price: 현재 가격
        volume: 거래량
        timestamp: 타임스탬프
        bid: 매수 호가
        ask: 매도 호가
        spread: 스프레드
    """
    symbol: str
    price: float
    volume: float
    timestamp: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread: Optional[float] = None

    def __post_init__(self):
        """스프레드 계산"""
        if self.bid is not None and self.ask is not None:
            self.spread = self.ask - self.bid


@dataclass
class OrderBookLevel:
    """
    오더북 레벨

    Attributes:
        price: 가격
        size: 사이즈
        orders: 주문 수 (선택)
    """
    price: float
    size: float
    orders: Optional[int] = None


@dataclass
class OrderBook:
    """
    오더북 데이터 클래스

    Attributes:
        symbol: 심볼
        bids: 매수 호가 (내림차순)
        asks: 매도 호가 (오름차순)
        timestamp: 타임스탬프
        sequence: 시퀀스 번호 (선택)
    """
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: float
    sequence: Optional[int] = None

    def get_best_bid(self) -> Optional[OrderBookLevel]:
        """최우선 매수 호가"""
        return self.bids[0] if self.bids else None

    def get_best_ask(self) -> Optional[OrderBookLevel]:
        """최우선 매도 호가"""
        return self.asks[0] if self.asks else None

    def get_spread(self) -> Optional[float]:
        """스프레드 계산"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask.price - best_bid.price
        return None

    def get_mid_price(self) -> Optional[float]:
        """중간 가격 계산"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (best_bid.price + best_ask.price) / 2
        return None


@dataclass
class Order:
    """
    주문 정보

    Attributes:
        order_id: 주문 ID
        symbol: 심볼
        side: 방향 (매수/매도)
        order_type: 주문 타입
        price: 가격 (지정가의 경우)
        size: 사이즈
        filled_size: 체결된 사이즈
        status: 주문 상태
        timestamp: 생성 타임스탬프
        updated_at: 마지막 업데이트 타임스탬프
    """
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Optional[float]
    size: float
    filled_size: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    timestamp: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        """초기화 검증"""
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()
        if self.updated_at == 0.0:
            self.updated_at = self.timestamp

    @property
    def is_filled(self) -> bool:
        """전체 체결 여부"""
        return self.status == OrderStatus.FILLED

    @property
    def is_open(self) -> bool:
        """미체결 여부"""
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)

    @property
    def fill_ratio(self) -> float:
        """체결 비율"""
        if self.size == 0:
            return 0.0
        return self.filled_size / self.size


@dataclass
class Position:
    """
    포지션 정보

    Attributes:
        symbol: 심볼
        side: 방향 (롱/숏)
        size: 포지션 크기
        entry_price: 진입 가격
        current_price: 현재 가격
        unrealized_pnl: 미실현 손익
        realized_pnl: 실현 손익
        timestamp: 진입 타임스탬프
        updated_at: 마지막 업데이트 타임스탬프
    """
    symbol: str
    side: str  # "LONG" or "SHORT"
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        """손익 계산"""
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()
        if self.updated_at == 0.0:
            self.updated_at = self.timestamp
        self._calculate_pnl()

    def _calculate_pnl(self) -> None:
        """손익 계산"""
        if self.side == "LONG":
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.size
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - self.current_price) * self.size

    @property
    def pnl_percentage(self) -> float:
        """손익률 (%)"""
        if self.entry_price == 0:
            return 0.0
        return (self.unrealized_pnl / (self.entry_price * self.size)) * 100

    def update_price(self, new_price: float) -> None:
        """
        현재 가격 업데이트

        Args:
            new_price: 새로운 가격
        """
        self.current_price = new_price
        import time
        self.updated_at = time.time()
        self._calculate_pnl()


class ExchangeClient(ABC):
    """
    거래소 클라이언트 추상 기본 클래스

    모든 거래소 어댑터는 이 클래스를 상속받아야 합니다.
    """

    def __init__(
        self,
        exchange_name: str,
        logger: Optional[logging.Logger] = None
    ):
        """
        초기화

        Args:
            exchange_name: 거래소 이름
            logger: 로거 (선택)
        """
        self.exchange_name = exchange_name
        self.logger = logger or logging.getLogger(f"exchange.{exchange_name}")

    @abstractmethod
    async def connect(self) -> bool:
        """
        거래소 연결

        Returns:
            bool: 연결 성공 여부
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """연결 해제"""
        pass

    @abstractmethod
    async def buy(
        self,
        symbol: str,
        size: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET
    ) -> Order:
        """
        매수 주문

        Args:
            symbol: 심볼
            size: 사이즈
            price: 가격 (지정가의 경우)
            order_type: 주문 타입

        Returns:
            Order: 생성된 주문
        """
        pass

    @abstractmethod
    async def sell(
        self,
        symbol: str,
        size: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET
    ) -> Order:
        """
        매도 주문

        Args:
            symbol: 심볼
            size: 사이즈
            price: 가격 (지정가의 경우)
            order_type: 주문 타입

        Returns:
            Order: 생성된 주문
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        주문 취소

        Args:
            order_id: 주문 ID

        Returns:
            bool: 취소 성공 여부
        """
        pass

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        포지션 조회

        Args:
            symbol: 심볼

        Returns:
            Position: 포지션 정보 (없으면 None)
        """
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, float]:
        """
        잔액 조회

        Returns:
            Dict[str, float]: 자산별 잔액 (예: {"USDC": 1000.0})
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """
        주문 상태 조회

        Args:
            order_id: 주문 ID

        Returns:
            Order: 주문 정보
        """
        pass

    def is_connected(self) -> bool:
        """
        연결 상태 확인 (기본 구현)

        Returns:
            bool: 연결 여부
        """
        return True

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"ExchangeClient(name={self.exchange_name})"
