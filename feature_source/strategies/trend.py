"""
Trend Strategy - 방향성/역추세 통합 매매 전략

전략 모드:
- directional: BTC가 행사가 위면 UP, 아래면 DOWN (edge_threshold 이상)
- contrarian: BTC가 행사가 위지만 DOWN edge 범위, 아래지만 UP edge 범위
- auto: 상황에 따라 둘 중 더 유리한 쪽 선택

전략 개요:
1. 진입: 모드에 따라 directional/contrarian 중 하나 선택
2. 청산: Edge가 1% 미만으로 좁혀지면 청산
3. 손절: Edge가 -10% 이하면 청산
4. 시간 청산: 남은 시간 5분 미만이면 청산
5. 수익 실현(contrarian): 포지션이 take_profit_pct% 이상이면 청산
"""

from dataclasses import dataclass
from typing import Optional, Dict, Callable
from enum import Enum


class TrendMode(Enum):
    DIRECTIONAL = "directional"
    CONTRARIAN = "contrarian"
    AUTO = "auto"


@dataclass
class TrendConfig:
    """Trend 전략 설정"""

    mode: str = "auto"  # "directional", "contrarian", "auto"

    # 진입 조건
    edge_threshold_pct: float = 3.0  # directional 최소 edge %
    contrarian_entry_edge_min: float = 3.0  # contrarian 최소 edge %
    contrarian_entry_edge_max: float = 10.0  # contrarian 최대 edge %

    # 청산 조건
    exit_edge_threshold: float = 1.0  # Edge 기준 청산 (%)
    stoploss_edge_pct: float = -10.0  # 스탑로스 edge (%)
    time_exit_seconds: int = 300  # 시간 청산 기준 (초)

    # 포지션 설정
    bet_amount_usdc: float = 10.0
    max_position_size: float = 100.0
    use_kelly: bool = False

    # Contrarian 전용
    contrarian_take_profit_pct: float = 3.0  # 수익 실현 기준 (%)


@dataclass
class TrendSignal:
    """Trend 시그널"""

    action: str = "HOLD"  # BUY, SELL, HOLD
    direction: str = ""  # UP, DOWN
    strategy: str = ""  # "directional" or "contrarian"
    edge: float = 0.0
    reason: str = ""
    kelly_fraction: float = 0.0
    suggested_size: float = 0.0


class TrendStrategy:
    """방향성/역추세 통합 전략"""

    def __init__(
        self,
        config: TrendConfig = None,
        prob_model=None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.config = config or TrendConfig()
        self.prob_model = prob_model
        self._log_callback = log_callback

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)
        else:
            print(message)

    def analyze_entry(
        self,
        btc_price: float,
        strike_price: float,
        fair_up: float,
        fair_down: float,
        market_up: float,
        market_down: float,
        has_position: bool = False,
    ) -> Optional[Dict]:
        """
        진입 기회 분석

        Args:
            btc_price: 현재 BTC 가격
            strike_price: 행사가
            fair_up: UP 공정 확률
            fair_down: DOWN 공정 확률
            market_up: UP 시장 가격
            market_down: DOWN 시장 가격
            has_position: 포지션 보유 여부

        Returns:
            None: 진입 기회 없음
            Dict: {
                "direction": "UP" or "DOWN",
                "strategy": "directional" or "contrarian",
                "edge": edge 값,
                "fair": fair 확률,
                "market": market 확률,
                "amount_usdc": 매수 금액,
                "kelly_fraction": Kelly 비율
            }
        """
        if has_position:
            return None

        edge_up = (fair_up - market_up) * 100
        edge_down = (fair_down - market_down) * 100

        directional_signal = self._analyze_directional_entry(
            btc_price,
            strike_price,
            edge_up,
            edge_down,
            fair_up,
            fair_down,
            market_up,
            market_down,
        )
        contrarian_signal = self._analyze_contrarian_entry(
            btc_price,
            strike_price,
            edge_up,
            edge_down,
            fair_up,
            fair_down,
            market_up,
            market_down,
        )

        mode = self.config.mode

        if mode == "directional":
            return directional_signal
        elif mode == "contrarian":
            return contrarian_signal
        else:  # auto
            if directional_signal and contrarian_signal:
                direction_edge = abs(directional_signal["edge"])
                contrarian_edge = abs(contrarian_signal["edge"])
                if direction_edge >= contrarian_edge:
                    return directional_signal
                else:
                    return contrarian_signal
            else:
                return directional_signal or contrarian_signal

    def _analyze_directional_entry(
        self,
        btc_price: float,
        strike_price: float,
        edge_up: float,
        edge_down: float,
        fair_up: float,
        fair_down: float,
        market_up: float,
        market_down: float,
    ) -> Optional[Dict]:
        """Directional 진입 분석"""
        threshold = self.config.edge_threshold_pct

        if btc_price > strike_price:
            if edge_up >= threshold:
                kelly = 0.0
                if self.prob_model:
                    kelly = self.prob_model.calculate_kelly_fraction(fair_up, market_up)

                suggested_size = (
                    kelly * self.config.max_position_size
                    if self.config.use_kelly
                    else self.config.bet_amount_usdc
                )

                return {
                    "direction": "UP",
                    "strategy": "directional",
                    "edge": edge_up,
                    "fair": fair_up,
                    "market": market_up,
                    "amount_usdc": suggested_size,
                    "kelly_fraction": kelly,
                }
        else:
            if edge_down >= threshold:
                kelly = 0.0
                if self.prob_model:
                    kelly = self.prob_model.calculate_kelly_fraction(
                        fair_down, market_down
                    )

                suggested_size = (
                    kelly * self.config.max_position_size
                    if self.config.use_kelly
                    else self.config.bet_amount_usdc
                )

                return {
                    "direction": "DOWN",
                    "strategy": "directional",
                    "edge": edge_down,
                    "fair": fair_down,
                    "market": market_down,
                    "amount_usdc": suggested_size,
                    "kelly_fraction": kelly,
                }

        return None

    def _analyze_contrarian_entry(
        self,
        btc_price: float,
        strike_price: float,
        edge_up: float,
        edge_down: float,
        fair_up: float,
        fair_down: float,
        market_up: float,
        market_down: float,
    ) -> Optional[Dict]:
        """Contrarian 진입 분석"""
        min_edge = self.config.contrarian_entry_edge_min
        max_edge = self.config.contrarian_entry_edge_max

        if btc_price > strike_price:
            if min_edge <= edge_down <= max_edge:
                return {
                    "direction": "DOWN",
                    "strategy": "contrarian",
                    "edge": edge_down,
                    "fair": fair_down,
                    "market": market_down,
                    "amount_usdc": self.config.bet_amount_usdc,
                    "kelly_fraction": 0.0,
                }
        else:
            if min_edge <= edge_up <= max_edge:
                return {
                    "direction": "UP",
                    "strategy": "contrarian",
                    "edge": edge_up,
                    "fair": fair_up,
                    "market": market_up,
                    "amount_usdc": self.config.bet_amount_usdc,
                    "kelly_fraction": 0.0,
                }

        return None

    def analyze_exit(
        self,
        direction: str,
        strategy: str,
        edge: float,
        pnl_pct: float,
        time_remaining_seconds: int,
    ) -> Optional[Dict]:
        """
        청산 조건 분석

        Args:
            direction: 포지션 방향 ("UP" or "DOWN")
            strategy: 진입 전략 ("directional" or "contrarian")
            edge: 현재 edge (%)
            pnl_pct: 포지션 손익률 (%)
            time_remaining_seconds: 만료까지 남은 시간 (초)

        Returns:
            None: 청산 필요 없음
            Dict: {
                "action": "SELL",
                "direction": direction,
                "reason": 청산 사유
            }
        """
        if edge < self.config.exit_edge_threshold and edge > -5.0:
            return {
                "action": "SELL",
                "direction": direction,
                "reason": "Take Profit (Edge < 1%)",
            }

        if edge < self.config.stoploss_edge_pct:
            return {
                "action": "SELL",
                "direction": direction,
                "reason": "Stop Loss (Edge < -10%)",
            }

        if time_remaining_seconds < self.config.time_exit_seconds:
            return {
                "action": "SELL",
                "direction": direction,
                "reason": "Time Exit (< 5min)",
            }

        if (
            strategy == "contrarian"
            and pnl_pct >= self.config.contrarian_take_profit_pct
        ):
            return {
                "action": "SELL",
                "direction": direction,
                "reason": f"Contrarian Take Profit ({pnl_pct:.1f}%)",
            }

        return None
