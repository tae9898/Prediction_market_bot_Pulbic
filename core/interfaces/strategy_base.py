"""
전략 기반 인터페이스

모든 트레이딩 전략이 따라야 할 추상 기본 클래스와 데이터 모델을 정의합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, Callable
import logging


class SignalAction(Enum):
    """시그널 액션 타입"""
    ENTER = "enter"  # 진입
    EXIT = "exit"  # 청산
    HOLD = "hold"  # 유지
    ADJUST = "adjust"  # 포지션 조정


class SignalDirection(Enum):
    """시그널 방향"""
    LONG = "long"  # 롱 (UP)
    SHORT = "short"  # 숏 (DOWN)
    FLAT = "flat"  # 중립


@dataclass
class MarketSignal:
    """
    시장 시그널 데이터 클래스

    Attributes:
        action: 시그널 액션 (진입/청산/유지/조정)
        direction: 방향 (롱/숏/중립)
        confidence: 신뢰도 (0.0 ~ 1.0)
        edge: 에지 값 (%)
        reason: 시그널 생성 이유
        metadata: 추가 메타데이터
        timestamp: 시그널 생성 타임스탬프
    """
    action: SignalAction
    direction: SignalDirection
    confidence: float
    edge: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        """초기화 검증"""
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"신뢰도는 0.0 ~ 1.0 사이여야 합니다: {self.confidence}")

        if self.edge < 0:
            raise ValueError(f"에지는 음수일 수 없습니다: {self.edge}")

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "action": self.action.value,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "edge": self.edge,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class StrategyConfig:
    """
    전략 설정 기본 데이터 클래스

    Attributes:
        enabled: 활성화 여부
        name: 전략 이름
        min_edge_pct: 최소 에지 (%)
        min_confidence: 최소 신뢰도 (0.0 ~ 1.0)
        max_position_size: 최대 포지션 크기
        risk_per_trade: 트레이드당 리스크 (%)
    """
    enabled: bool = True
    name: str = "base_strategy"
    min_edge_pct: float = 5.0
    min_confidence: float = 0.6
    max_position_size: float = 100.0
    risk_per_trade: float = 2.0

    def __post_init__(self):
        """설정값 검증"""
        if self.min_edge_pct < 0:
            raise ValueError(f"최소 에지는 음수일 수 없습니다: {self.min_edge_pct}")

        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(f"최소 신뢰도는 0.0 ~ 1.0 사이여야 합니다: {self.min_confidence}")

        if self.max_position_size <= 0:
            raise ValueError(f"최대 포지션 크기는 양수여야 합니다: {self.max_position_size}")

        if self.risk_per_trade <= 0 or self.risk_per_trade > 100:
            raise ValueError(f"리스크 비율은 0 ~ 100 사이여야 합니다: {self.risk_per_trade}")


class BaseStrategy(ABC):
    """
    전략 기본 추상 클래스

    모든 트레이딩 전략은 이 클래스를 상속받아야 합니다.
    """

    def __init__(self, config: StrategyConfig, logger: Optional[logging.Logger] = None):
        """
        초기화

        Args:
            config: 전략 설정
            logger: 로거 (선택)
        """
        self.config = config
        self.logger = logger or logging.getLogger(f"strategy.{config.name}")

        if not self.config.enabled:
            self.logger.info(f"{self.config.name} 전략이 비활성화되어 있습니다")

    @abstractmethod
    def validate_config(self) -> bool:
        """
        설정값 검증

        Returns:
            bool: 유효한 설정 여부
        """
        pass

    @abstractmethod
    def analyze(
        self,
        market_data: Dict[str, Any],
        position: Optional[Dict[str, Any]] = None
    ) -> Optional[MarketSignal]:
        """
        시장 분석 및 시그널 생성

        Args:
            market_data: 시장 데이터 딕셔너리
            position: 현재 포지션 정보 (선택)

        Returns:
            MarketSignal: 생성된 시그널 (없으면 None)
        """
        pass

    def on_entry(self, signal: MarketSignal, position: Dict[str, Any]) -> None:
        """
        진입 시 호출되는 콜백

        Args:
            signal: 진입 시그널
            position: 생성된 포지션 정보
        """
        self.logger.info(
            f"진입: {signal.direction.value} | "
            f"에지: {signal.edge:.2f}% | "
            f"신뢰도: {signal.confidence:.2f} | "
            f"이유: {signal.reason}"
        )

    def on_exit(self, signal: MarketSignal, position: Dict[str, Any], pnl: float) -> None:
        """
        청산 시 호출되는 콜백

        Args:
            signal: 청산 시그널
            position: 청산된 포지션 정보
            pnl: 손익 (USDC)
        """
        pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
        self.logger.info(
            f"청산: {signal.direction.value} | "
            f"손익: {pnl_str} USDC | "
            f"이유: {signal.reason}"
        )

    def get_position_size(
        self,
        balance: float,
        risk_amount: Optional[float] = None
    ) -> float:
        """
        리스크 기반 포지션 사이징

        Args:
            balance: 사용 가능한 잔액
            risk_amount: 리스크 금액 (선택, 없으면 config 사용)

        Returns:
            float: 포지션 크기
        """
        if risk_amount is None:
            risk_amount = balance * (self.config.risk_per_trade / 100)

        # 최대 포지션 크기 제한
        position_size = min(risk_amount, self.config.max_position_size)

        # 잔액 초과 방지
        position_size = min(position_size, balance)

        return position_size

    def should_enter(self, signal: MarketSignal) -> bool:
        """
        진입 조건 확인

        Args:
            signal: 시장 시그널

        Returns:
            bool: 진입 여부
        """
        if signal.action != SignalAction.ENTER:
            return False

        if signal.confidence < self.config.min_confidence:
            self.logger.debug(
                f"신뢰도 부족: {signal.confidence:.2f} < {self.config.min_confidence:.2f}"
            )
            return False

        if signal.edge < self.config.min_edge_pct:
            self.logger.debug(
                f"에지 부족: {signal.edge:.2f}% < {self.config.min_edge_pct:.2f}%"
            )
            return False

        return True

    def should_exit(self, signal: MarketSignal, position: Dict[str, Any]) -> bool:
        """
        청산 조건 확인

        Args:
            signal: 시장 시그널
            position: 현재 포지션

        Returns:
            bool: 청산 여부
        """
        return signal.action == SignalAction.EXIT

    def __repr__(self) -> str:
        """문자열 표현"""
        return f"BaseStrategy(name={self.config.name}, enabled={self.config.enabled})"
