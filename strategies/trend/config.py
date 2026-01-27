"""
Trend Strategy 설정 데이터 클래스

전략 파라미터와 진입/청산 조건을 정의합니다.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TrendMode(Enum):
    """Trend 전략 모드"""

    DIRECTIONAL = "directional"  # 방향성 추종
    CONTRARIAN = "contrarian"  # 역추세
    AUTO = "auto"  # 자동 선택


@dataclass
class TrendConfig:
    """
    Trend 전략 설정

    Attributes:
        enabled: 전략 활성화 여부
        name: 전략 이름
        mode: 전략 모드 (directional/contrarian/auto)

        # 진입 조건
        edge_threshold_pct: directional 최소 edge (%)
        contrarian_entry_edge_min: contrarian 최소 edge (%)
        contrarian_entry_edge_max: contrarian 최대 edge (%)

        # 청산 조건
        exit_edge_threshold: Edge 기준 청산 (%)
        stoploss_edge_pct: 스탑로스 edge (%)
        time_exit_seconds: 시간 청산 기준 (초)

        # 포지션 설정
        bet_amount_usdc: 기본 배팅 금액 (USDC)
        max_position_size: 최대 포지션 크기
        use_kelly: Kelly 공식 사용 여부
        min_confidence: 최소 신뢰도

        # Contrarian 전용
        contrarian_take_profit_pct: 수익 실현 기준 (%)

        # 리스크 관리
        risk_per_trade: 트레이드당 리스크 (%)
    """

    # 기본 설정
    enabled: bool = True
    name: str = "trend"
    mode: str = "auto"

    # 진입 조건
    edge_threshold_pct: float = 3.0
    contrarian_entry_edge_min: float = 3.0
    contrarian_entry_edge_max: float = 10.0

    # 청산 조건
    exit_edge_threshold: float = 1.0
    stoploss_edge_pct: float = -10.0
    time_exit_seconds: int = 300

    # 포지션 설정
    bet_amount_usdc: float = 10.0
    max_position_size: float = 100.0
    use_kelly: bool = False
    min_confidence: float = 0.6

    # Contrarian 전용
    contrarian_take_profit_pct: float = 3.0

    # 리스크 관리
    risk_per_trade: float = 2.0

    def __post_init__(self):
        """설정값 검증"""
        # 모드 검증
        valid_modes = [m.value for m in TrendMode]
        if self.mode not in valid_modes:
            raise ValueError(
                f"잘못된 모드: {self.mode}. "
                f"허용되는 모드: {valid_modes}"
            )

        # 진입 조건 검증
        if self.edge_threshold_pct < 0:
            raise ValueError(
                f"edge_threshold_pct는 음수일 수 없습니다: {self.edge_threshold_pct}"
            )

        if self.contrarian_entry_edge_min < 0:
            raise ValueError(
                f"contrarian_entry_edge_min는 음수일 수 없습니다: "
                f"{self.contrarian_entry_edge_min}"
            )

        if self.contrarian_entry_edge_max < self.contrarian_entry_edge_min:
            raise ValueError(
                f"contrarian_entry_edge_max({self.contrarian_entry_edge_max})는 "
                f"contrarian_entry_edge_min({self.contrarian_entry_edge_min})보다 "
                f"커야 합니다"
            )

        # 청산 조건 검증
        if self.exit_edge_threshold < 0:
            raise ValueError(
                f"exit_edge_threshold는 음수일 수 없습니다: {self.exit_edge_threshold}"
            )

        if self.stoploss_edge_pct > 0:
            raise ValueError(
                f"stoploss_edge_pct는 0 이하여야 합니다: {self.stoploss_edge_pct}"
            )

        if self.time_exit_seconds < 0:
            raise ValueError(
                f"time_exit_seconds는 음수일 수 없습니다: {self.time_exit_seconds}"
            )

        # 포지션 설정 검증
        if self.bet_amount_usdc <= 0:
            raise ValueError(
                f"bet_amount_usdc는 양수여야 합니다: {self.bet_amount_usdc}"
            )

        if self.max_position_size <= 0:
            raise ValueError(
                f"max_position_size는 양수여야 합니다: {self.max_position_size}"
            )

        # 신뢰도 검증
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(
                f"min_confidence는 0.0 ~ 1.0 사이여야 합니다: {self.min_confidence}"
            )

        # Contrarian 설정 검증
        if self.contrarian_take_profit_pct < 0:
            raise ValueError(
                f"contrarian_take_profit_pct는 음수일 수 없습니다: "
                f"{self.contrarian_take_profit_pct}"
            )

        # 리스크 비율 검증
        if self.risk_per_trade <= 0 or self.risk_per_trade > 100:
            raise ValueError(
                f"risk_per_trade는 0 ~ 100 사이여야 합니다: {self.risk_per_trade}"
            )

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "enabled": self.enabled,
            "name": self.name,
            "mode": self.mode,
            "edge_threshold_pct": self.edge_threshold_pct,
            "contrarian_entry_edge_min": self.contrarian_entry_edge_min,
            "contrarian_entry_edge_max": self.contrarian_entry_edge_max,
            "exit_edge_threshold": self.exit_edge_threshold,
            "stoploss_edge_pct": self.stoploss_edge_pct,
            "time_exit_seconds": self.time_exit_seconds,
            "bet_amount_usdc": self.bet_amount_usdc,
            "max_position_size": self.max_position_size,
            "use_kelly": self.use_kelly,
            "min_confidence": self.min_confidence,
            "contrarian_take_profit_pct": self.contrarian_take_profit_pct,
            "risk_per_trade": self.risk_per_trade,
        }
