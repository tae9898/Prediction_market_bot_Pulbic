"""
Expiry Sniper Strategy Implementation

마감 직전 고확률 배팅 전략을 구현합니다.
"""

import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from core.interfaces.strategy_base import (
    BaseStrategy,
    StrategyConfig,
    MarketSignal,
    SignalAction,
    SignalDirection,
)
from core.registry import register_strategy
from strategies.expiry_sniper.config import (
    ExpirySniperConfig,
    SniperState,
    ExpirySniperContext,
)


@register_strategy("expiry_sniper")
class ExpirySniperStrategy(BaseStrategy):
    """
    마감 직전 고확률 스나이핑 전략

    전략 로직:
    1. 마감 A분 전 (예: 15분) 진입 시작
    2. 확률 B% 이상 (예: 98%) - 한쪽 방향이 확실할 때
    3. C 달러만큼 매수
    4. 최대 D번 진입
    5. E초 간격으로 분할 매수

    Attributes:
        config: 스나이퍼 전략 설정
        context: 실행 컨텍스트 (자산별 상태)
    """

    def __init__(
        self,
        config: ExpirySniperConfig,
        logger: Optional[logging.Logger] = None,
        context: Optional[ExpirySniperContext] = None
    ):
        """
        초기화

        Args:
            config: 스나이퍼 전략 설정
            logger: 로거 (선택)
            context: 실행 컨텍스트 (선택, 없으면 새로 생성)
        """
        super().__init__(config, logger)
        self.config: ExpirySniperConfig = config
        self.context = context or ExpirySniperContext()

        if self.config.enabled:
            self.logger.info(
                f"Expiry Sniper Strategy 초기화: "
                f"{self.config.time_entry_threshold_seconds}초 전, "
                f"{self.config.prob_threshold}% 이상, "
                f"{self.config.amount_usdc} USDC, "
                f"최대 {self.config.max_executions}번"
            )

    def validate_config(self) -> bool:
        """
        설정값 검증

        Returns:
            bool: 유효한 설정 여부
        """
        try:
            # ExpirySniperConfig의 __post_init__에서 검증 수행
            if not isinstance(self.config, ExpirySniperConfig):
                self.logger.error(f"설정은 ExpirySniperConfig 타입이어야 합니다")
                return False

            # 추가 검증이 필요하면 여기에 추가
            return True

        except Exception as e:
            self.logger.error(f"설정 검증 실패: {e}")
            return False

    def analyze(
        self,
        market_data: Dict[str, Any],
        position: Optional[Dict[str, Any]] = None
    ) -> Optional[MarketSignal]:
        """
        스나이핑 기회 분석

        Args:
            market_data: 시장 데이터 딕셔너리
                - symbol: str - 심볼 (예: "BTC/USDC")
                - time_remaining: int - 잔여 시간 (초)
                - up_ask: float - UP 매수 가격 (확률)
                - down_ask: float - DOWN 매수 가격 (확률)
                - has_position: bool - 포지션 보유 여부
            position: 현재 포지션 정보 (선택)

        Returns:
            MarketSignal: 생성된 시그널 (없으면 None)
        """
        if not self.config.enabled:
            return None

        # 시장 데이터 파싱
        symbol = market_data.get("symbol", "")
        time_remaining = market_data.get("time_remaining", 0)
        up_ask = market_data.get("up_ask", 0.0)
        down_ask = market_data.get("down_ask", 0.0)
        has_position = market_data.get("has_position", False)

        # 필수 데이터 검증
        if not symbol or time_remaining <= 0:
            return None

        if up_ask <= 0 or down_ask <= 0:
            return None

        # 상태 조회/초기화
        state = self.context.get_state(symbol)

        # 1. 시간 조건 체크 (A분 전)
        minutes_remaining = time_remaining / 60

        if minutes_remaining > (self.config.time_entry_threshold_seconds / 60):
            # 아직 시간 안됨 - 상태 리셋 (새로운 마켓 등)
            if state.executions_count > 0 and minutes_remaining > (self.config.time_entry_threshold_seconds / 60) * 2:
                # 시간이 아주 많이 남았으면(다음 마켓) 카운트 리셋
                self.logger.debug(f"[{symbol}] 시간이 많이 남아 상태 리셋: {minutes_remaining:.1f}분")
                state.reset()
            return None

        # 최소 잔여 시간 체크 (너무 짧으면 위험)
        if time_remaining < self.config.min_time_remaining_seconds:
            self.logger.debug(f"[{symbol}] 잔여 시간이 너무 짧음: {time_remaining}초")
            return None

        # 포지션이 있으면 진입하지 않음
        if has_position:
            self.logger.debug(f"[{symbol}] 이미 포지션 보유 중")
            return None

        # 2. 확률 조건 체크 (B% 이상)
        # Ask 가격을 확률로 간주 (매수 비용)
        prob_up = up_ask * 100
        prob_down = down_ask * 100

        target_direction = None
        target_prob = 0.0

        if prob_up >= self.config.prob_threshold:
            target_direction = SignalDirection.LONG
            target_prob = prob_up
        elif prob_down >= self.config.prob_threshold:
            target_direction = SignalDirection.SHORT
            target_prob = prob_down

        if target_direction is None:
            self.logger.debug(
                f"[{symbol}] 확률 부족: UP={prob_up:.1f}%, DOWN={prob_down:.1f}% "
                f"< {self.config.prob_threshold}%"
            )
            return None

        # 3. 횟수 제한 체크 (최대 D번)
        if state.executions_count >= self.config.max_executions:
            self.logger.debug(
                f"[{symbol}] 최대 실행 횟수 도달: {state.executions_count}/{self.config.max_executions}"
            )
            return None

        # 4. 간격 체크 (E초)
        current_time = time.time()
        if current_time - state.last_execution_time < self.config.execution_interval_seconds:
            remaining_wait = self.config.execution_interval_seconds - (current_time - state.last_execution_time)
            self.logger.debug(f"[{symbol}] 실행 간격 대기 중: {remaining_wait:.1f}초 남음")
            return None

        # 5. 신뢰도 및 에지 계산
        confidence = target_prob / 100.0
        edge = target_prob - (100 - target_prob)  # 에지 = 확률 - 반대확률

        # 실행 결정
        reason = (
            f"Expiry Sniper: {minutes_remaining:.1f}m left, "
            f"Prob {target_prob:.1f}% >= {self.config.prob_threshold}%, "
            f"Executions {state.executions_count}/{self.config.max_executions}"
        )

        self.logger.info(f"[{symbol}] {reason}")

        return MarketSignal(
            action=SignalAction.ENTER,
            direction=target_direction,
            confidence=confidence,
            edge=edge,
            reason=reason,
            metadata={
                "symbol": symbol,
                "time_remaining": time_remaining,
                "prob_up": prob_up,
                "prob_down": prob_down,
                "target_prob": target_prob,
                "execution_count": state.executions_count,
                "amount": self.config.amount_usdc,
            }
        )

    def on_entry(self, signal: MarketSignal, position: Dict[str, Any]) -> None:
        """
        진입 시 호출되는 콜백

        진입 후 실행 횟수를 기록합니다.

        Args:
            signal: 진입 시그널
            position: 생성된 포지션 정보
        """
        super().on_entry(signal, position)

        # 실행 기록
        symbol = signal.metadata.get("symbol", "")
        state = self.context.get_state(symbol)
        state.executions_count += 1
        state.last_execution_time = time.time()
        state.is_active = True
        state.target_direction = signal.direction.value

        self.logger.info(
            f"[{symbol}] Sniper 실행 완료 ({state.executions_count}/{self.config.max_executions})"
        )

    def on_exit(self, signal: MarketSignal, position: Dict[str, Any], pnl: float) -> None:
        """
        청산 시 호출되는 콜백

        Args:
            signal: 청산 시그널
            position: 청산된 포지션 정보
            pnl: 손익 (USDC)
        """
        super().on_exit(signal, position, pnl)

        # 상태 업데이트
        symbol = signal.metadata.get("symbol", "")
        state = self.context.get_state(symbol)
        state.is_active = False

        # 손익 기록
        pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
        self.logger.info(f"[{symbol}] 손익: {pnl_str} USDC (총 {state.executions_count}번 실행)")

    def should_exit(
        self,
        market_data: Dict[str, Any],
        position: Dict[str, Any]
    ) -> bool:
        """
        청산 조건 확인

        시간이 너무 짧으면 자동 청산합니다.

        Args:
            market_data: 시장 데이터
            position: 현재 포지션

        Returns:
            bool: 청산 여부
        """
        time_remaining = market_data.get("time_remaining", 0)

        # 시간이 임계값 이하면 청산
        if time_remaining <= self.config.time_exit_threshold_seconds:
            symbol = market_data.get("symbol", "")
            self.logger.info(
                f"[{symbol}] 청산 시간 도달: {time_remaining}초 <= "
                f"{self.config.time_exit_threshold_seconds}초"
            )
            return True

        return False

    def get_position_size(
        self,
        balance: float,
        risk_amount: Optional[float] = None
    ) -> float:
        """
        포지션 사이징

        스나이퍼 전략은 고정 금액을 사용합니다.

        Args:
            balance: 사용 가능한 잔액
            risk_amount: 리스크 금액 (무시, config.amount_usdc 사용)

        Returns:
            float: 포지션 크기
        """
        # 잔액 확인
        position_size = min(self.config.amount_usdc, balance)

        if position_size < self.config.amount_usdc:
            self.logger.warning(
                f"잔액 부족: {balance:.2f} USDC < {self.config.amount_usdc} USDC"
            )

        return position_size

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"ExpirySniperStrategy("
            f"name={self.config.name}, "
            f"enabled={self.config.enabled}, "
            f"threshold={self.config.time_entry_threshold_seconds}s, "
            f"prob={self.config.prob_threshold}%, "
            f"amount={self.config.amount_usdc} USDC)"
        )


__all__ = [
    "ExpirySniperStrategy",
]
