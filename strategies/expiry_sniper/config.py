"""
Expiry Sniper Strategy Configuration

스나이퍼 전략을 위한 설정 데이터 클래스를 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Dict
from core.interfaces.strategy_base import StrategyConfig


@dataclass
class SniperState:
    """
    자산별 스나이퍼 상태

    Attributes:
        asset_type: 자산 타입 (심볼)
        executions_count: 실행 횟수
        last_execution_time: 마지막 실행 시간
        is_active: 현재 활성화 상태 (조건 충족 중)
        target_direction: 목표 방향 (LONG/SHORT)
    """
    asset_type: str = ""
    executions_count: int = 0
    last_execution_time: float = 0.0
    is_active: bool = False
    target_direction: str = ""

    def reset(self) -> None:
        """상태 리셋"""
        self.executions_count = 0
        self.last_execution_time = 0.0
        self.is_active = False
        self.target_direction = ""


@dataclass
class ExpirySniperConfig(StrategyConfig):
    """
    스나이퍼 전략 설정

    기본 StrategyConfig를 상속받아 스나이퍼 전용 설정을 추가합니다.

    Attributes:
        enabled: 활성화 여부
        name: 전략 이름
        time_entry_threshold_seconds: 진입 시간 임계값 (초) - A분 전
        time_exit_threshold_seconds: 청산 시간 임계값 (초)
        prob_threshold: 확률 임계값 (%) - B%
        amount_usdc: 매수 금액 (USDC) - C달러
        max_executions: 최대 실행 횟수 - D번
        execution_interval_seconds: 실행 간격 (초) - E초
        min_time_remaining_seconds: 최소 잔여 시간 (너무 짧으면 진입하지 않음)
        min_edge_pct: 최소 에지 (%)
        min_confidence: 최소 신뢰도 (0.0 ~ 1.0)
    """
    # 시간 관련 설정
    time_entry_threshold_seconds: int = 900  # 15분 = 900초
    time_exit_threshold_seconds: int = 30    # 30초
    min_time_remaining_seconds: int = 30     # 30초 미만은 위험해서 스킵

    # 확률 관련 설정
    prob_threshold: float = 98.0             # 98%

    # 포지션 관련 설정
    amount_usdc: float = 10.0                # 10 USDC
    max_executions: int = 3                  # 최대 3번
    execution_interval_seconds: int = 60     # 60초 간격

    # 기본 설정 (StrategyConfig에서 상속)
    enabled: bool = True
    name: str = "expiry_sniper"
    min_edge_pct: float = 2.0                # 확률이 높으므로 에지는 낮아도 됨
    min_confidence: float = 0.95             # 95% 신뢰도
    max_position_size: float = 100.0
    risk_per_trade: float = 2.0

    def __post_init__(self):
        """설정값 검증"""
        # 부모 클래스 검증
        StrategyConfig.__post_init__(self)

        # 스나이퍼 전용 검증
        if self.time_entry_threshold_seconds <= 0:
            raise ValueError(f"진입 시간 임계값은 양수여야 합니다: {self.time_entry_threshold_seconds}")

        if self.time_exit_threshold_seconds < 0:
            raise ValueError(f"청산 시간 임계값은 음수일 수 없습니다: {self.time_exit_threshold_seconds}")

        if self.min_time_remaining_seconds < 0:
            raise ValueError(f"최소 잔여 시간은 음수일 수 없습니다: {self.min_time_remaining_seconds}")

        if not 0.0 <= self.prob_threshold <= 100.0:
            raise ValueError(f"확률 임계값은 0 ~ 100 사이여야 합니다: {self.prob_threshold}")

        if self.amount_usdc <= 0:
            raise ValueError(f"매수 금액은 양수여야 합니다: {self.amount_usdc}")

        if self.max_executions <= 0:
            raise ValueError(f"최대 실행 횟수는 양수여야 합니다: {self.max_executions}")

        if self.execution_interval_seconds <= 0:
            raise ValueError(f"실행 간격은 양수여야 합니다: {self.execution_interval_seconds}")

        # 시간 관계 검증
        if self.time_exit_threshold_seconds > self.time_entry_threshold_seconds:
            raise ValueError(
                f"청산 시간 임계값({self.time_exit_threshold_seconds})은 "
                f"진입 시간 임계값({self.time_entry_threshold_seconds})보다 클 수 없습니다"
            )


@dataclass
class ExpirySniperContext:
    """
    스나이퍼 전략 실행 컨텍스트

    여러 자산에 대한 상태를 관리합니다.

    Attributes:
        states: 자산별 상태 딕셔너리
    """
    states: Dict[str, SniperState] = field(default_factory=dict)

    def get_state(self, asset_type: str) -> SniperState:
        """자산 상태 조회 (없으면 생성)"""
        if asset_type not in self.states:
            self.states[asset_type] = SniperState(asset_type=asset_type)
        return self.states[asset_type]

    def reset_state(self, asset_type: str) -> None:
        """자산 상태 리셋"""
        if asset_type in self.states:
            self.states[asset_type].reset()

    def reset_all(self) -> None:
        """모든 상태 리셋"""
        for state in self.states.values():
            state.reset()


__all__ = [
    "SniperState",
    "ExpirySniperConfig",
    "ExpirySniperContext",
]
