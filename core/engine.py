"""
Trading Engine - Main Orchestration System

The TradingEngine orchestrates exchanges, strategies, and data feeds to execute
automated trading. It provides:
- Multi-strategy signal aggregation
- Multi-exchange execution with conflict resolution
- Position and P&L tracking
- Dry-run mode for testing
- Event-driven architecture with callbacks
- Graceful shutdown and error recovery
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Awaitable, Set
from enum import Enum
import logging

from core.interfaces.exchange_base import (
    ExchangeClient,
    Order,
    Position,
    OrderSide,
    OrderType,
    OrderStatus,
)
from core.interfaces.strategy_base import (
    BaseStrategy,
    MarketSignal,
    SignalAction,
    SignalDirection,
    StrategyConfig,
)
from core.interfaces.data_feed_base import DataFeed
from core.context import ExecutionContext, BotState
from core.registry import StrategyRegistry, ExchangeRegistry


class ConflictResolution(Enum):
    """시그널 충돌 해결 전략"""
    PRIORITY = "priority"  # 우선순위 기반
    MAJORITY = "majority"  # 다수결
    CONFIDENCE = "confidence"  # 신뢰도 기반
    FIRST = "first"  # 첫 번째 시그널 우선
    NONE = "none"  # 충돌 시 실행 안함


@dataclass
class EngineConfig:
    """
    트레이딩 엔진 설정

    Attributes:
        bot_id: 봇 식별자
        dry_run: 드라이런 모드 (실제 거래 안함)
        auto_trade: 자동 거래 활성화
        loop_interval: 트레이딩 루프 간격 (초)
        conflict_resolution: 충돌 해결 전략
        max_concurrent_orders: 최대 동시 주문 수
        enable_signal_aggregation: 시그널 집계 활성화
        shutdown_timeout: 종료 타임아웃 (초)
    """
    bot_id: str = "trading_bot"
    dry_run: bool = True
    auto_trade: bool = False
    loop_interval: float = 1.0
    conflict_resolution: ConflictResolution = ConflictResolution.CONFIDENCE
    max_concurrent_orders: int = 5
    enable_signal_aggregation: bool = True
    shutdown_timeout: float = 30.0

    def __post_init__(self):
        """설정값 검증"""
        if self.loop_interval <= 0:
            raise ValueError(f"루프 간격은 양수여야 합니다: {self.loop_interval}")

        if self.max_concurrent_orders <= 0:
            raise ValueError(f"최대 동시 주문 수는 양수여야 합니다: {self.max_concurrent_orders}")

        if self.shutdown_timeout <= 0:
            raise ValueError(f"종료 타임아웃은 양수여야 합니다: {self.shutdown_timeout}")


@dataclass
class AggregatedSignal:
    """
    집계된 시그널

    Attributes:
        action: 액션
        direction: 방향
        confidence: 평균 신뢰도
        edge: 평균 에지
        source_strategies: 소스 전략 목록
        timestamp: 생성 시간
        metadata: 추가 메타데이터
    """
    action: SignalAction
    direction: SignalDirection
    confidence: float
    edge: float
    source_strategies: List[str]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeResult:
    """
    거래 결과

    Attributes:
        success: 성공 여부
        order: 생성된 주문 (성공 시)
        error: 오류 메시지 (실패 시)
        timestamp: 실행 시간
    """
    success: bool
    order: Optional[Order]
    error: Optional[str]
    timestamp: float


class TradingEngine:
    """
    트레이딩 엔진

    exchanges, strategies, data feeds를 연결하고 자동화된 트레이딩을 실행합니다.
    """

    def __init__(
        self,
        config: EngineConfig,
        exchanges: Optional[Dict[str, ExchangeClient]] = None,
        strategies: Optional[Dict[str, BaseStrategy]] = None,
        data_feeds: Optional[Dict[str, DataFeed]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        초기화

        Args:
            config: 엔진 설정
            exchanges: 거래소 클라이언트 딕셔너리 {name: client}
            strategies: 전략 딕셔너리 {name: strategy}
            data_feeds: 데이터 피드 딕셔너리 {name: feed}
            logger: 로거 (선택)
        """
        self.config = config
        self.logger = logger or logging.getLogger(f"engine.{config.bot_id}")

        # 컴포넌트 초기화
        self.exchanges: Dict[str, ExchangeClient] = exchanges or {}
        self.strategies: Dict[str, BaseStrategy] = strategies or {}
        self.data_feeds: Dict[str, DataFeed] = data_feeds or {}

        # 실행 컨텍스트
        self.context = ExecutionContext(bot_id=config.bot_id, logger=self.logger)
        self.context.auto_trade = config.auto_trade

        # 상태 관리
        self._running = False
        self._initialized = False
        self._main_task: Optional[asyncio.Task] = None

        # 주문 추적
        self._active_orders: Dict[str, Order] = {}
        self._order_history: List[Order] = []

        # P&L 추적
        self._total_pnl: float = 0.0
        self._trade_count: int = 0
        self._win_count: int = 0

        # 시그널 이벤트 핸들러 연결
        self._setup_event_handlers()

        self.logger.info(f"트레이딩 엔진 초기화: {config.bot_id}")

    def _setup_event_handlers(self) -> None:
        """이벤트 핸들러 설정"""
        async def on_signal(strategy_name: str, signal: Dict[str, Any]) -> None:
            """시그널 이벤트 처리"""
            self.logger.debug(
                f"시그널 수신 [{strategy_name}]: {signal.get('action')} | "
                f"{signal.get('direction')}"
            )

        async def on_trade(strategy_name: str, trade: Dict[str, Any]) -> None:
            """거래 이벤트 처리"""
            self.logger.info(
                f"거래 체결 [{strategy_name}]: {trade.get('side')} | "
                f"사이즈: {trade.get('size')}"
            )

        def on_error(strategy_name: str, error: Exception) -> None:
            """에러 이벤트 처리"""
            self.logger.error(f"에러 발생 [{strategy_name}]: {error}")

        self.context.on_signal_callback = on_signal
        self.context.on_trade_callback = on_trade
        self.context.on_error_callback = on_error

    # ===== 초기화 및 시작/중지 =====

    async def initialize(self) -> bool:
        """
        엔진 초기화

        모든 거래소, 전략, 데이터 피드를 초기화합니다.

        Returns:
            bool: 초기화 성공 여부
        """
        self.logger.info("트레이딩 엔진 초기화 시작...")

        try:
            # 거래소 연결
            for name, exchange in self.exchanges.items():
                self.logger.info(f"거래소 연결 중: {name}")
                if not await exchange.connect():
                    self.logger.error(f"거래소 연결 실패: {name}")
                    return False
                self.logger.info(f"거래소 연결 성공: {name}")

            # 전략 설정 검증
            for name, strategy in self.strategies.items():
                self.logger.info(f"전략 검증 중: {name}")
                if not strategy.validate_config():
                    self.logger.error(f"전략 설정 검증 실패: {name}")
                    return False
                self.logger.info(f"전략 검증 성공: {name}")

            # 데이터 피드 시작
            for name, feed in self.data_feeds.items():
                self.logger.info(f"데이터 피드 시작 중: {name}")
                await feed.start()
                self.logger.info(f"데이터 피드 시작 성공: {name}")

            # 초기 잔액 조회
            await self._update_balances()

            self._initialized = True
            self.logger.info("트레이딩 엔진 초기화 완료")
            return True

        except Exception as e:
            self.logger.error(f"초기화 중 오류 발생: {e}", exc_info=True)
            return False

    async def start(self) -> None:
        """엔진 시작"""
        if self._running:
            self.logger.warning("이미 실행 중입니다")
            return

        if not self._initialized:
            self.logger.error("초기화되지 않았습니다. initialize()를 먼저 호출하세요.")
            return

        self.logger.info("트레이딩 엔진 시작...")
        self._running = True
        self.context.start()

        # 메인 루프 시작
        self._main_task = asyncio.create_task(self._trading_loop())

        self.logger.info("트레이딩 엔진 시작 완료")

    async def stop(self) -> None:
        """
        엔진 중지

        모든 포지션을 정리하고 연결을 종료합니다.
        """
        if not self._running:
            return

        self.logger.info("트레이딩 엔진 중지 중...")
        self._running = False
        self.context.set_bot_state(BotState.STOPPING)

        # 메인 태스크 중지
        if self._main_task:
            self._main_task.cancel()
            try:
                await asyncio.wait_for(self._main_task, timeout=self.config.shutdown_timeout)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # 모든 주문 취소 시도
        await self._cancel_all_orders()

        # 데이터 피드 중지
        for name, feed in self.data_feeds.items():
            try:
                await feed.stop()
                self.logger.info(f"데이터 피드 중지: {name}")
            except Exception as e:
                self.logger.error(f"데이터 피드 중지 실패 ({name}): {e}")

        # 거래소 연결 해제
        for name, exchange in self.exchanges.items():
            try:
                await exchange.disconnect()
                self.logger.info(f"거래소 연결 해제: {name}")
            except Exception as e:
                self.logger.error(f"거래소 연결 해제 실패 ({name}): {e}")

        self.context.stop()
        self.logger.info("트레이딩 엔진 중지 완료")

    # ===== 메인 트레이딩 루프 =====

    async def _trading_loop(self) -> None:
        """
        메인 트레이딩 루프

        주기적으로 시장 데이터를 수집하고 시그널을 생성하며 거래를 실행합니다.
        """
        self.logger.info("트레이딩 루프 시작")

        while self._running:
            try:
                # 컨텍스트 시간 업데이트
                self.context.update_time()

                # 시장 데이터 수집
                market_data = await self._collect_market_data()

                # 포지션 업데이트
                await self._update_positions()

                # 시그널 생성
                signals = await self._generate_signals(market_data)

                # 시그널 집계 (활성화된 경우)
                if self.config.enable_signal_aggregation and len(signals) > 1:
                    aggregated = self._aggregate_signals(signals)
                    if aggregated:
                        signals = [aggregated]

                # 시그널 실행
                for signal in signals:
                    await self._execute_signal(signal)

                # 주문 상태 확인
                await self._check_order_status()

                # 대기
                await asyncio.sleep(self.config.loop_interval)

            except asyncio.CancelledError:
                self.logger.info("트레이딩 루프 취소됨")
                break
            except Exception as e:
                self.logger.error(f"트레이딩 루프 오류: {e}", exc_info=True)
                await asyncio.sleep(self.config.loop_interval)

        self.logger.info("트레이딩 루프 종료")

    # ===== 시장 데이터 수집 =====

    async def _collect_market_data(self) -> Dict[str, Any]:
        """
        모든 데이터 피드에서 시장 데이터 수집

        Returns:
            Dict: 통합된 시장 데이터
        """
        market_data: Dict[str, Any] = {}

        for name, feed in self.data_feeds.items():
            try:
                # 각 피드에서 데이터 수집
                data = await feed.get_market_data("")
                if data:
                    market_data[name] = data
            except Exception as e:
                self.logger.warning(f"시장 데이터 수집 실패 ({name}): {e}")

        return market_data

    # ===== 시그널 생성 =====

    async def _generate_signals(self, market_data: Dict[str, Any]) -> List[MarketSignal]:
        """
        모든 전략에서 시그널 생성

        Args:
            market_data: 시장 데이터

        Returns:
            List[MarketSignal]: 생성된 시그널 리스트
        """
        signals: List[MarketSignal] = []

        for name, strategy in self.strategies.items():
            if not strategy.config.enabled:
                continue

            try:
                # 현재 포지션 조회
                position = self.context.get_position(name)

                # 시그널 생성
                signal = strategy.analyze(market_data, position)

                if signal:
                    # 시그널 이벤트 발생
                    await self.context.emit_signal(name, signal.to_dict())
                    signals.append(signal)

            except Exception as e:
                self.context.emit_error(name, e)

        return signals

    # ===== 시그널 집계 =====

    def _aggregate_signals(self, signals: List[MarketSignal]) -> Optional[AggregatedSignal]:
        """
        여러 시그널을 집계하여 단일 시그널 생성

        Args:
            signals: 집계할 시그널 리스트

        Returns:
            AggregatedSignal: 집계된 시그널 (충돌 시 None)
        """
        if not signals:
            return None

        # 단일 시그널은 그대로 반환
        if len(signals) == 1:
            signal = signals[0]
            return AggregatedSignal(
                action=signal.action,
                direction=signal.direction,
                confidence=signal.confidence,
                edge=signal.edge,
                source_strategies=["single"],
                timestamp=signal.timestamp,
                metadata=signal.metadata,
            )

        # 충돌 해결
        resolved = self._resolve_conflicts(signals)
        if not resolved:
            self.logger.debug("시그널 충돌로 인해 실행되지 않음")
            return None

        # 평균 계산
        avg_confidence = sum(s.confidence for s in signals) / len(signals)
        avg_edge = sum(s.edge for s in signals) / len(signals)

        return AggregatedSignal(
            action=resolved.action,
            direction=resolved.direction,
            confidence=avg_confidence,
            edge=avg_edge,
            source_strategies=[f"strategy_{i}" for i in range(len(signals))],
            timestamp=time.time(),
            metadata={
                "resolution_method": self.config.conflict_resolution.value,
                "signal_count": len(signals),
            },
        )

    def _resolve_conflicts(self, signals: List[MarketSignal]) -> Optional[MarketSignal]:
        """
        시그널 충돌 해결

        Args:
            signals: 충돌하는 시그널 리스트

        Returns:
            MarketSignal: 해결된 시그널 (없으면 None)
        """
        if not signals:
            return None

        resolution = self.config.conflict_resolution

        if resolution == ConflictResolution.FIRST:
            return signals[0]

        elif resolution == ConflictResolution.CONFIDENCE:
            # 가장 높은 신뢰도 선택
            return max(signals, key=lambda s: s.confidence)

        elif resolution == ConflictResolution.MAJORITY:
            # 다수결
            long_count = sum(1 for s in signals if s.direction == SignalDirection.LONG)
            short_count = sum(1 for s in signals if s.direction == SignalDirection.SHORT)

            if long_count > short_count:
                return signals[0]  # 첫 번째 LONG 시그널
            elif short_count > long_count:
                return signals[0]  # 첫 번째 SHORT 시그널
            else:
                return None  # 동률이면 실행 안함

        elif resolution == ConflictResolution.PRIORITY:
            # Edge 기준 우선순위
            return max(signals, key=lambda s: s.edge)

        else:  # NONE
            return None

    # ===== 시그널 실행 =====

    async def _execute_signal(self, signal: MarketSignal) -> None:
        """
        시그널 실행

        Args:
            signal: 실행할 시그널
        """
        if not self.config.auto_trade:
            self.logger.debug("자동 거래가 비활성화됨")
            return

        # 드라이런 모드 로그
        if self.config.dry_run:
            self.logger.info(
                f"[DRY RUN] 시그널 실행: {signal.action.value} | "
                f"{signal.direction.value} | 에지: {signal.edge:.2f}%"
            )
            return

        # 액션별 처리
        if signal.action == SignalAction.ENTER:
            await self._execute_entry(signal)
        elif signal.action == SignalAction.EXIT:
            await self._execute_exit(signal)
        elif signal.action == SignalAction.HOLD:
            self.logger.debug("HOLD 시그널 - 아무것도 하지 않음")
        elif signal.action == SignalAction.ADJUST:
            await self._execute_adjust(signal)

    async def _execute_entry(self, signal: MarketSignal) -> Optional[TradeResult]:
        """
        진입 실행

        Args:
            signal: 진입 시그널

        Returns:
            TradeResult: 거래 결과
        """
        # 거래소 선택 (첫 번째 거래소 사용)
        if not self.exchanges:
            self.logger.error("사용 가능한 거래소가 없음")
            return None

        exchange_name = list(self.exchanges.keys())[0]
        exchange = self.exchanges[exchange_name]

        # 방향 결정
        side = OrderSide.BUY if signal.direction == SignalDirection.LONG else OrderSide.SELL

        # 포지션 사이즈 계산
        balance = await exchange.get_balance()
        usdc_balance = balance.get("USDC", 0.0)

        # 시그널에서 전략 이름 찾기
        strategy_name = signal.metadata.get("strategy", "unknown")
        strategy = self.strategies.get(strategy_name)

        if strategy:
            size = strategy.get_position_size(usdc_balance)
        else:
            # 기본 계산
            size = min(usdc_balance * 0.1, 100.0)

        if size <= 0:
            self.logger.warning(f"잔액 부족: {usdc_balance} USDC")
            return None

        # 주문 생성
        try:
            order = await exchange.buy("", size) if side == OrderSide.BUY else await exchange.sell("", size)

            self._active_orders[order.order_id] = order
            self._order_history.append(order)

            self.logger.info(
                f"진입 주문 생성: {side.value} | 사이즈: {size} | "
                f"주문 ID: {order.order_id}"
            )

            return TradeResult(
                success=True,
                order=order,
                error=None,
                timestamp=time.time(),
            )

        except Exception as e:
            self.logger.error(f"진입 주문 실패: {e}")
            return TradeResult(
                success=False,
                order=None,
                error=str(e),
                timestamp=time.time(),
            )

    async def _execute_exit(self, signal: MarketSignal) -> Optional[TradeResult]:
        """
        청산 실행

        Args:
            signal: 청산 시그널

        Returns:
            TradeResult: 거래 결과
        """
        # 포지션 조회
        position = self.context.get_position("main")

        if not position:
            self.logger.warning("청산할 포지션이 없음")
            return None

        # 거래소 선택
        exchange_name = list(self.exchanges.keys())[0]
        exchange = self.exchanges[exchange_name]

        # 반대 방향 주문
        side = OrderSide.SELL if signal.direction == SignalDirection.LONG else OrderSide.BUY
        size = position.get("size", 0.0)

        try:
            order = await exchange.sell("", size) if side == OrderSide.SELL else await exchange.buy("", size)

            self._active_orders[order.order_id] = order
            self._order_history.append(order)

            # P&L 계산
            pnl = position.get("unrealized_pnl", 0.0)
            self._total_pnl += pnl
            self._trade_count += 1
            if pnl > 0:
                self._win_count += 1

            self.context.log_pnl(
                f"청산: {signal.direction.value} | 손익: {pnl:.2f} USDC"
            )

            # 포지션 제거
            self.context.positions.pop("main", None)

            self.logger.info(
                f"청산 주문 생성: {side.value} | 사이즈: {size} | "
                f"손익: {pnl:.2f} USDC"
            )

            return TradeResult(
                success=True,
                order=order,
                error=None,
                timestamp=time.time(),
            )

        except Exception as e:
            self.logger.error(f"청산 주문 실패: {e}")
            return TradeResult(
                success=False,
                order=None,
                error=str(e),
                timestamp=time.time(),
            )

    async def _execute_adjust(self, signal: MarketSignal) -> Optional[TradeResult]:
        """
        포지션 조정 실행

        Args:
            signal: 조정 시그널

        Returns:
            TradeResult: 거래 결과
        """
        self.logger.info("포지션 조정 시그널 수신 (구현 필요)")
        return None

    # ===== 주문 관리 =====

    async def _check_order_status(self) -> None:
        """활성 주문 상태 확인"""
        for order_id, order in list(self._active_orders.items()):
            try:
                exchange_name = list(self.exchanges.keys())[0]
                exchange = self.exchanges[exchange_name]

                updated_order = await exchange.get_order_status(order_id)

                if updated_order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
                    # 주문 완료 또는 취소됨
                    del self._active_orders[order_id]
                    self.logger.info(
                        f"주문 {order_id}: {updated_order.status.value}"
                    )

            except Exception as e:
                self.logger.warning(f"주문 상태 확인 실패 ({order_id}): {e}")

    async def _cancel_all_orders(self) -> None:
        """모든 활성 주문 취소"""
        for order_id in list(self._active_orders.keys()):
            try:
                exchange_name = list(self.exchanges.keys())[0]
                exchange = self.exchanges[exchange_name]

                success = await exchange.cancel_order(order_id)
                if success:
                    del self._active_orders[order_id]
                    self.logger.info(f"주문 취소 성공: {order_id}")
                else:
                    self.logger.warning(f"주문 취소 실패: {order_id}")

            except Exception as e:
                self.logger.error(f"주문 취소 오류 ({order_id}): {e}")

    # ===== 포지션 및 잔고 관리 =====

    async def _update_positions(self) -> None:
        """포지션 정보 업데이트"""
        for exchange_name, exchange in self.exchanges.items():
            try:
                # 각 심볼에 대한 포지션 조회
                position = await exchange.get_position("")
                if position:
                    self.context.update_position(
                        exchange_name,
                        {
                            "symbol": position.symbol,
                            "side": position.side,
                            "size": position.size,
                            "entry_price": position.entry_price,
                            "current_price": position.current_price,
                            "unrealized_pnl": position.unrealized_pnl,
                            "realized_pnl": position.realized_pnl,
                        }
                    )
            except Exception as e:
                self.logger.warning(f"포지션 업데이트 실패 ({exchange_name}): {e}")

    async def _update_balances(self) -> None:
        """잔고 정보 업데이트"""
        for exchange_name, exchange in self.exchanges.items():
            try:
                balance = await exchange.get_balance()
                self.context.update_asset(exchange_name, balance)
                self.logger.info(f"잔고 업데이트 ({exchange_name}): {balance}")
            except Exception as e:
                self.logger.warning(f"잔고 업데이트 실패 ({exchange_name}): {e}")

    # ===== 상태 조회 =====

    def get_status(self) -> Dict[str, Any]:
        """
        엔진 상태 조회

        Returns:
            Dict: 상태 정보
        """
        return {
            "bot_id": self.config.bot_id,
            "running": self._running,
            "initialized": self._initialized,
            "dry_run": self.config.dry_run,
            "auto_trade": self.config.auto_trade,
            "bot_state": self.context.get_bot_state().value,
            "exchanges": list(self.exchanges.keys()),
            "strategies": list(self.strategies.keys()),
            "data_feeds": list(self.data_feeds.keys()),
            "active_orders": len(self._active_orders),
            "total_pnl": self._total_pnl,
            "trade_count": self._trade_count,
            "win_count": self._win_count,
            "win_rate": self._win_count / self._trade_count if self._trade_count > 0 else 0.0,
            "positions": self.context.get_all_positions(),
            "assets": self.context.get_all_assets(),
        }

    # ===== 컴포넌트 추가/제거 =====

    def add_exchange(self, name: str, exchange: ExchangeClient) -> None:
        """
        거래소 추가

        Args:
            name: 거래소 이름
            exchange: 거래소 클라이언트
        """
        self.exchanges[name] = exchange
        self.logger.info(f"거래소 추가: {name}")

    def add_strategy(self, name: str, strategy: BaseStrategy) -> None:
        """
        전략 추가

        Args:
            name: 전략 이름
            strategy: 전략 인스턴스
        """
        self.strategies[name] = strategy
        self.logger.info(f"전략 추가: {name}")

    def add_data_feed(self, name: str, feed: DataFeed) -> None:
        """
        데이터 피드 추가

        Args:
            name: 피드 이름
            feed: 데이터 피드 인스턴스
        """
        self.data_feeds[name] = feed
        self.logger.info(f"데이터 피드 추가: {name}")

    def remove_exchange(self, name: str) -> bool:
        """
        거래소 제거

        Args:
            name: 거래소 이름

        Returns:
            bool: 제거 성공 여부
        """
        if name in self.exchanges:
            del self.exchanges[name]
            self.logger.info(f"거래소 제거: {name}")
            return True
        return False

    def remove_strategy(self, name: str) -> bool:
        """
        전략 제거

        Args:
            name: 전략 이름

        Returns:
            bool: 제거 성공 여부
        """
        if name in self.strategies:
            del self.strategies[name]
            self.logger.info(f"전략 제거: {name}")
            return True
        return False

    def remove_data_feed(self, name: str) -> bool:
        """
        데이터 피드 제거

        Args:
            name: 피드 이름

        Returns:
            bool: 제거 성공 여부
        """
        if name in self.data_feeds:
            del self.data_feeds[name]
            self.logger.info(f"데이터 피드 제거: {name}")
            return True
        return False

    # ===== 콜백 설정 =====

    def set_signal_callback(
        self,
        callback: Callable[[str, Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        시그널 콜백 설정

        Args:
            callback: 시그널 수신 시 호출할 함수
        """
        self.context.on_signal_callback = callback

    def set_trade_callback(
        self,
        callback: Callable[[str, Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        거래 콜백 설정

        Args:
            callback: 거래 체결 시 호출할 함수
        """
        self.context.on_trade_callback = callback

    def set_error_callback(
        self,
        callback: Callable[[str, Exception], None]
    ) -> None:
        """
        에러 콜백 설정

        Args:
            callback: 에러 발생 시 호출할 함수
        """
        self.context.on_error_callback = callback

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"TradingEngine("
            f"bot_id={self.config.bot_id}, "
            f"running={self._running}, "
            f"exchanges={len(self.exchanges)}, "
            f"strategies={len(self.strategies)}, "
            f"data_feeds={len(self.data_feeds)})"
        )


__all__ = [
    # 클래스
    "TradingEngine",
    # 데이터 클래스
    "EngineConfig",
    "AggregatedSignal",
    "TradeResult",
    # 열거형
    "ConflictResolution",
]
