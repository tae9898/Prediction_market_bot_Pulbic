"""
데이터 피드 기반 인터페이스

모든 데이터 피드가 구현해야 할 추상 기본 클래스를 정의합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, Awaitable
import logging
import asyncio


# 콜백 함수 타입 정의
SubscriptionCallback = Callable[[Dict[str, Any]], Awaitable[None]]


@dataclass
class DataFeedConfig:
    """
    데이터 피드 설정

    Attributes:
        name: 피드 이름
        reconnect_interval: 재연결 간격 (초)
        max_retries: 최대 재연결 시도 횟수
        enable_websocket: 웹소켓 사용 여부
        symbols: 구독할 심볼 리스트
    """
    name: str = "default_feed"
    reconnect_interval: float = 5.0
    max_retries: int = 3
    enable_websocket: bool = True
    symbols: list[str] = field(default_factory=list)

    def __post_init__(self):
        """설정값 검증"""
        if self.reconnect_interval <= 0:
            raise ValueError(f"재연결 간격은 양수여야 합니다: {self.reconnect_interval}")

        if self.max_retries < 0:
            raise ValueError(f"최대 재시도 횟수는 0 이상이어야 합니다: {self.max_retries}")


class DataFeed(ABC):
    """
    데이터 피드 추상 기본 클래스

    모든 데이터 피드는 이 클래스를 상속받아야 합니다.
    """

    def __init__(
        self,
        config: DataFeedConfig,
        logger: Optional[logging.Logger] = None
    ):
        """
        초기화

        Args:
            config: 피드 설정
            logger: 로거 (선택)
        """
        self.config = config
        self.logger = logger or logging.getLogger(f"datafeed.{config.name}")

        self._connected: bool = False
        self._subscriptions: Dict[str, list[SubscriptionCallback]] = {}
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

    @abstractmethod
    async def connect(self) -> bool:
        """
        데이터 피드 연결

        Returns:
            bool: 연결 성공 여부
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """연결 해제"""
        pass

    @abstractmethod
    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        시장 데이터 조회 (REST API)

        Args:
            symbol: 심볼

        Returns:
            Dict: 시장 데이터 (없으면 None)
        """
        pass

    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """
        오더북 조회 (REST API)

        Args:
            symbol: 심볼
            limit: 깊이

        Returns:
            Dict: 오더북 데이터 (없으면 None)
        """
        pass

    async def subscribe(
        self,
        symbol: str,
        callback: SubscriptionCallback
    ) -> bool:
        """
        실시간 데이터 구독

        Args:
            symbol: 심볼
            callback: 데이터 수신 시 호출할 콜백 함수

        Returns:
            bool: 구독 성공 여부
        """
        if not self.config.enable_websocket:
            self.logger.warning("웹소켓이 비활성화되어 있습니다")
            return False

        if symbol not in self._subscriptions:
            self._subscriptions[symbol] = []

        self._subscriptions[symbol].append(callback)
        self.logger.info(f"구독 시작: {symbol} (총 {len(self._subscriptions[symbol])}개 콜백)")

        return True

    async def unsubscribe(
        self,
        symbol: str,
        callback: Optional[SubscriptionCallback] = None
    ) -> bool:
        """
        실시간 데이터 구독 취소

        Args:
            symbol: 심볼
            callback: 취소할 콜백 (None이면 해당 심볼의 모든 콜백 제거)

        Returns:
            bool: 구독 취소 성공 여부
        """
        if symbol not in self._subscriptions:
            self.logger.warning(f"구독되지 않은 심볼: {symbol}")
            return False

        if callback is None:
            # 모든 콜백 제거
            del self._subscriptions[symbol]
            self.logger.info(f"모든 구독 취소: {symbol}")
        else:
            # 특정 콜백만 제거
            try:
                self._subscriptions[symbol].remove(callback)
                self.logger.info(f"구독 취소: {symbol}")

                # 남은 콜백이 없으면 키 제거
                if not self._subscriptions[symbol]:
                    del self._subscriptions[symbol]
            except ValueError:
                self.logger.warning(f"콜백을 찾을 수 없습니다: {symbol}")
                return False

        return True

    async def start(self) -> None:
        """데이터 피드 시작"""
        if self._running:
            self.logger.warning("이미 실행 중입니다")
            return

        self._running = True
        self.logger.info("데이터 피드 시작")

        # 연결
        if not await self.connect():
            self.logger.error("연결 실패")
            self._running = False
            return

        # 데이터 수지 루프 시작
        self._task = asyncio.create_task(self._data_loop())

    async def stop(self) -> None:
        """데이터 피드 중지"""
        if not self._running:
            return

        self._running = False
        self.logger.info("데이터 피드 중지")

        # 태스크 취소
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # 연결 해제
        await self.disconnect()

    async def _data_loop(self) -> None:
        """
        데이터 수신 루프 (기본 구현)

        서브클래스에서 오버라이드하여 실시간 데이터 처리 구현
        """
        while self._running:
            try:
                # 폴링 방식 기본 구현
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"데이터 루프 오류: {e}")
                await asyncio.sleep(self.config.reconnect_interval)

    async def _notify_subscribers(self, symbol: str, data: Dict[str, Any]) -> None:
        """
        구독자에게 데이터 알림

        Args:
            symbol: 심볼
            data: 데이터
        """
        if symbol not in self._subscriptions:
            return

        for callback in self._subscriptions[symbol]:
            try:
                await callback(data)
            except Exception as e:
                self.logger.error(f"콜백 실행 오류 ({symbol}): {e}")

    def is_connected(self) -> bool:
        """
        연결 상태 확인

        Returns:
            bool: 연결 여부
        """
        return self._connected

    def is_running(self) -> bool:
        """
        실행 상태 확인

        Returns:
            bool: 실행 여부
        """
        return self._running

    @property
    def subscribed_symbols(self) -> list[str]:
        """
        구독 중인 심볼 목록

        Returns:
            list[str]: 심볼 리스트
        """
        return list(self._subscriptions.keys())

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"DataFeed(name={self.config.name}, "
            f"connected={self._connected}, "
            f"subscriptions={len(self._subscriptions)})"
        )
