"""
Trend Strategy - 방향성/역추세 통합 매매 전략 구현

이 전략은 BTC 가격과 행사가의 관계를 분석하여 UP/DONE 진입 여부를 결정합니다.
- Directional: 추세 방향으로 진입 (BTC > 행사가 → UP, BTC < 행사가 → DOWN)
- Contrarian: 역추세 방향으로 진입 (BTC > 행사가 → DOWN, BTC < 행사가 → UP)
- Auto: 상황에 따라 더 유리한 쪽 선택

진입 조건:
1. Directional: Edge >= edge_threshold_pct (기본 3%)
2. Contrarian: contrarian_entry_edge_min <= Edge <= contrarian_entry_edge_max

청산 조건:
1. Edge < exit_edge_threshold (기본 1%)
2. Edge < stoploss_edge_pct (기본 -10%)
3. 남은 시간 < time_exit_seconds (기본 300초)
4. Contrarian 전용: PnL >= contrarian_take_profit_pct (기본 3%)
"""

import logging
from typing import Optional, Dict, Any

from core.interfaces.strategy_base import (
    BaseStrategy,
    StrategyConfig,
    MarketSignal,
    SignalAction,
    SignalDirection,
)
from core.registry import register_strategy
from .config import TrendConfig, TrendMode


class TrendStrategy(BaseStrategy):
    """
    방향성/역추세 통합 전략

    이 전략은 BTC 가격과 행사가의 관계를 기반으로 매매 신호를 생성합니다.
    Kelly 공식을 지원하며, 세 가지 모드 (directional, contrarian, auto)를 제공합니다.
    """

    def __init__(
        self,
        config: TrendConfig,
        exchange_client: Optional[Any] = None,
        prob_model: Optional[Any] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        초기화

        Args:
            config: Trend 전략 설정
            exchange_client: 거래소 클라이언트 (선택)
            prob_model: 확률 모델 (Kelly 계산용, 선택)
            logger: 로거 (선택)
        """
        # BaseStrategy 초기화 (StrategyConfig로 변환)
        base_config = StrategyConfig(
            enabled=config.enabled,
            name=config.name,
            min_edge_pct=config.edge_threshold_pct,
            min_confidence=config.min_confidence,
            max_position_size=config.max_position_size,
            risk_per_trade=config.risk_per_trade,
        )
        super().__init__(base_config, logger)

        self.trend_config = config
        self.exchange_client = exchange_client
        self.prob_model = prob_model

        self.logger.info(f"Trend 전략 초기화 완료 (모드: {config.mode})")

    def validate_config(self) -> bool:
        """
        설정값 검증

        Returns:
            bool: 유효한 설정 여부
        """
        try:
            # TrendConfig 자체의 __post_init__에서 검증됨
            # 추가 검증이 필요하면 여기에 작성

            # 모드별 추가 검증
            if self.trend_config.mode == TrendMode.CONTRARIAN.value:
                if self.trend_config.contrarian_entry_edge_min <= 0:
                    self.logger.error(
                        "Contrarian 모드에서는 contrarian_entry_edge_min > 0 이어야 합니다"
                    )
                    return False

            self.logger.info("Trend 전략 설정 검증 통과")
            return True

        except Exception as e:
            self.logger.error(f"설정 검증 실패: {e}")
            return False

    def analyze(
        self,
        market_data: Dict[str, Any],
        position: Optional[Dict[str, Any]] = None,
    ) -> Optional[MarketSignal]:
        """
        시장 분석 및 시그널 생성

        Args:
            market_data: 시장 데이터 딕셔너리
                - btc_price: 현재 BTC 가격
                - strike_price: 행사가
                - fair_up: UP 공정 확률 (0~1)
                - fair_down: DOWN 공정 확률 (0~1)
                - market_up: UP 시장 가격 (0~1)
                - market_down: DOWN 시장 가격 (0~1)
                - time_remaining_seconds: 만료까지 남은 시간 (초, 선택)
            position: 현재 포지션 정보 (선택)
                - direction: "UP" or "DOWN"
                - strategy: 진입 전략 ("directional" or "contrarian")
                - size: 포지션 크기
                - avg_price: 평균 진입 가격
                - unrealized_pnl: 미실현 손익 (%)

        Returns:
            MarketSignal: 생성된 시그널 (없으면 None)
        """
        try:
            # 시장 데이터 파싱
            btc_price = market_data.get("btc_price", 0.0)
            strike_price = market_data.get("strike_price", 0.0)
            fair_up = market_data.get("fair_up", 0.0)
            fair_down = market_data.get("fair_down", 0.0)
            market_up = market_data.get("market_up", 0.0)
            market_down = market_data.get("market_down", 0.0)
            time_remaining = market_data.get("time_remaining_seconds", 0)

            # 필수 데이터 검증
            if btc_price <= 0 or strike_price <= 0:
                self.logger.warning("유효하지 않은 가격 데이터")
                return None

            if fair_up <= 0 or fair_down <= 0 or market_up <= 0 or market_down <= 0:
                self.logger.warning("유효하지 않은 확률 데이터")
                return None

            # Edge 계산
            edge_up = (fair_up - market_up) * 100
            edge_down = (fair_down - market_down) * 100

            # 포지션 보유 여부 확인
            has_position = position is not None and position.get("size", 0) > 0

            # 진입/청산 분기
            if has_position:
                return self._analyze_exit(
                    position, edge_up, edge_down, time_remaining
                )
            else:
                return self._analyze_entry(
                    btc_price,
                    strike_price,
                    edge_up,
                    edge_down,
                    fair_up,
                    fair_down,
                    market_up,
                    market_down,
                )

        except Exception as e:
            self.logger.error(f"시장 분석 오류: {e}")
            return None

    def _analyze_entry(
        self,
        btc_price: float,
        strike_price: float,
        edge_up: float,
        edge_down: float,
        fair_up: float,
        fair_down: float,
        market_up: float,
        market_down: float,
    ) -> Optional[MarketSignal]:
        """
        진입 기회 분석

        Args:
            btc_price: 현재 BTC 가격
            strike_price: 행사가
            edge_up: UP Edge (%)
            edge_down: DOWN Edge (%)
            fair_up: UP 공정 확률
            fair_down: DOWN 공정 확률
            market_up: UP 시장 가격
            market_down: DOWN 시장 가격

        Returns:
            MarketSignal: 진입 시그널 (없으면 None)
        """
        mode = self.trend_config.mode

        # Directional 분석
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

        # Contrarian 분석
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

        # 모드별 신호 선택
        if mode == TrendMode.DIRECTIONAL.value:
            return directional_signal
        elif mode == TrendMode.CONTRARIAN.value:
            return contrarian_signal
        else:  # AUTO
            if directional_signal and contrarian_signal:
                # Edge가 더 큰 쪽 선택
                if directional_signal.edge >= contrarian_signal.edge:
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
    ) -> Optional[MarketSignal]:
        """
        Directional 진입 분석

        BTC > 행사가이면 UP, BTC < 행사가이면 DOWN 진입을 고려합니다.

        Returns:
            MarketSignal: Directional 진입 시그널
        """
        threshold = self.trend_config.edge_threshold_pct

        if btc_price > strike_price:
            # BTC가 행사가 위: UP 진입 고려
            if edge_up >= threshold:
                kelly = 0.0
                if self.prob_model:
                    try:
                        kelly = self.prob_model.calculate_kelly_fraction(
                            fair_up, market_up
                        )
                    except Exception as e:
                        self.logger.warning(f"Kelly 계산 실패: {e}")

                direction = SignalDirection.LONG
                confidence = min(0.9, 0.5 + (edge_up / 100))

                signal = MarketSignal(
                    action=SignalAction.ENTER,
                    direction=direction,
                    confidence=confidence,
                    edge=edge_up,
                    reason=f"Directional UP (BTC > Strike, Edge: {edge_up:.1f}%)",
                    metadata={
                        "strategy": "directional",
                        "direction_str": "UP",
                        "btc_price": btc_price,
                        "strike_price": strike_price,
                        "fair_up": fair_up,
                        "market_up": market_up,
                        "kelly_fraction": kelly,
                    },
                )

                self.logger.debug(
                    f"Directional UP 신호: BTC={btc_price:.2f} > Strike={strike_price:.2f}, "
                    f"Edge={edge_up:.1f}%"
                )
                return signal

        elif btc_price < strike_price:
            # BTC가 행사가 아래: DOWN 진입 고려
            if edge_down >= threshold:
                kelly = 0.0
                if self.prob_model:
                    try:
                        kelly = self.prob_model.calculate_kelly_fraction(
                            fair_down, market_down
                        )
                    except Exception as e:
                        self.logger.warning(f"Kelly 계산 실패: {e}")

                direction = SignalDirection.SHORT
                confidence = min(0.9, 0.5 + (edge_down / 100))

                signal = MarketSignal(
                    action=SignalAction.ENTER,
                    direction=direction,
                    confidence=confidence,
                    edge=edge_down,
                    reason=f"Directional DOWN (BTC < Strike, Edge: {edge_down:.1f}%)",
                    metadata={
                        "strategy": "directional",
                        "direction_str": "DOWN",
                        "btc_price": btc_price,
                        "strike_price": strike_price,
                        "fair_down": fair_down,
                        "market_down": market_down,
                        "kelly_fraction": kelly,
                    },
                )

                self.logger.debug(
                    f"Directional DOWN 신호: BTC={btc_price:.2f} < Strike={strike_price:.2f}, "
                    f"Edge={edge_down:.1f}%"
                )
                return signal

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
    ) -> Optional[MarketSignal]:
        """
        Contrarian 진입 분석

        BTC > 행사가이면 DOWN, BTC < 행사가이면 UP 진입을 고려합니다.
        역추진 매매이므로 Edge 범위가 중요합니다.

        Returns:
            MarketSignal: Contrarian 진입 시그널
        """
        min_edge = self.trend_config.contrarian_entry_edge_min
        max_edge = self.trend_config.contrarian_entry_edge_max

        if btc_price > strike_price:
            # BTC가 행사가 위: DOWN 진입 고려 (역추세)
            if min_edge <= edge_down <= max_edge:
                direction = SignalDirection.SHORT
                confidence = min(0.8, 0.5 + (edge_down / 100))

                signal = MarketSignal(
                    action=SignalAction.ENTER,
                    direction=direction,
                    confidence=confidence,
                    edge=abs(edge_down),
                    reason=f"Contrarian DOWN (BTC > Strike, Edge: {edge_down:.1f}%)",
                    metadata={
                        "strategy": "contrarian",
                        "direction_str": "DOWN",
                        "btc_price": btc_price,
                        "strike_price": strike_price,
                        "fair_down": fair_down,
                        "market_down": market_down,
                        "kelly_fraction": 0.0,
                    },
                )

                self.logger.debug(
                    f"Contrarian DOWN 신호: BTC={btc_price:.2f} > Strike={strike_price:.2f}, "
                    f"Edge={edge_down:.1f}%"
                )
                return signal

        elif btc_price < strike_price:
            # BTC가 행사가 아래: UP 진입 고려 (역추세)
            if min_edge <= edge_up <= max_edge:
                direction = SignalDirection.LONG
                confidence = min(0.8, 0.5 + (edge_up / 100))

                signal = MarketSignal(
                    action=SignalAction.ENTER,
                    direction=direction,
                    confidence=confidence,
                    edge=abs(edge_up),
                    reason=f"Contrarian UP (BTC < Strike, Edge: {edge_up:.1f}%)",
                    metadata={
                        "strategy": "contrarian",
                        "direction_str": "UP",
                        "btc_price": btc_price,
                        "strike_price": strike_price,
                        "fair_up": fair_up,
                        "market_up": market_up,
                        "kelly_fraction": 0.0,
                    },
                )

                self.logger.debug(
                    f"Contrarian UP 신호: BTC={btc_price:.2f} < Strike={strike_price:.2f}, "
                    f"Edge={edge_up:.1f}%"
                )
                return signal

        return None

    def _analyze_exit(
        self,
        position: Dict[str, Any],
        edge_up: float,
        edge_down: float,
        time_remaining: int,
    ) -> Optional[MarketSignal]:
        """
        청산 조건 분석

        Args:
            position: 현재 포지션 정보
            edge_up: UP Edge (%)
            edge_down: DOWN Edge (%)
            time_remaining: 만료까지 남은 시간 (초)

        Returns:
            MarketSignal: 청산 시그널 (없으면 None)
        """
        direction_str = position.get("direction", "")
        strategy = position.get("strategy", "directional")
        unrealized_pnl_pct = position.get("unrealized_pnl", 0.0)

        # 현재 방향의 Edge 계산
        current_edge = edge_up if direction_str == "UP" else edge_down

        # 1. Edge 기반 청산 (Take Profit)
        if current_edge < self.trend_config.exit_edge_threshold and current_edge > -5.0:
            direction_enum = (
                SignalDirection.LONG if direction_str == "UP" else SignalDirection.SHORT
            )

            signal = MarketSignal(
                action=SignalAction.EXIT,
                direction=direction_enum,
                confidence=0.8,
                edge=abs(current_edge),
                reason=f"Take Profit (Edge {current_edge:.1f}% < {self.trend_config.exit_edge_threshold}%)",
                metadata={
                    "strategy": strategy,
                    "direction_str": direction_str,
                    "exit_type": "edge_threshold",
                },
            )

            self.logger.info(
                f"청산 신호: Edge 축소 ({current_edge:.1f}% < "
                f"{self.trend_config.exit_edge_threshold}%)"
            )
            return signal

        # 2. Stop Loss
        if current_edge <= self.trend_config.stoploss_edge_pct:
            direction_enum = (
                SignalDirection.LONG if direction_str == "UP" else SignalDirection.SHORT
            )

            signal = MarketSignal(
                action=SignalAction.EXIT,
                direction=direction_enum,
                confidence=0.9,
                edge=abs(current_edge),
                reason=f"Stop Loss (Edge {current_edge:.1f}% < {self.trend_config.stoploss_edge_pct}%)",
                metadata={
                    "strategy": strategy,
                    "direction_str": direction_str,
                    "exit_type": "stop_loss",
                },
            )

            self.logger.warning(
                f"손절 청산: Edge 악화 ({current_edge:.1f}% < "
                f"{self.trend_config.stoploss_edge_pct}%)"
            )
            return signal

        # 3. 시간 청산
        if time_remaining < self.trend_config.time_exit_seconds:
            direction_enum = (
                SignalDirection.LONG if direction_str == "UP" else SignalDirection.SHORT
            )

            signal = MarketSignal(
                action=SignalAction.EXIT,
                direction=direction_enum,
                confidence=0.7,
                edge=abs(current_edge),
                reason=f"Time Exit ({time_remaining}s < {self.trend_config.time_exit_seconds}s)",
                metadata={
                    "strategy": strategy,
                    "direction_str": direction_str,
                    "exit_type": "time_exit",
                },
            )

            self.logger.info(
                f"시간 청산: 잔여 시간 부족 ({time_remaining}s < "
                f"{self.trend_config.time_exit_seconds}s)"
            )
            return signal

        # 4. Contrarian 수익 실현
        if (
            strategy == "contrarian"
            and unrealized_pnl_pct >= self.trend_config.contrarian_take_profit_pct
        ):
            direction_enum = (
                SignalDirection.LONG if direction_str == "UP" else SignalDirection.SHORT
            )

            signal = MarketSignal(
                action=SignalAction.EXIT,
                direction=direction_enum,
                confidence=0.8,
                edge=abs(current_edge),
                reason=f"Contrarian Take Profit (PnL: {unrealized_pnl_pct:.1f}%)",
                metadata={
                    "strategy": strategy,
                    "direction_str": direction_str,
                    "exit_type": "contrarian_tp",
                    "pnl_pct": unrealized_pnl_pct,
                },
            )

            self.logger.info(
                f"Contrarian 수익 실현: PnL {unrealized_pnl_pct:.1f}% >= "
                f"{self.trend_config.contrarian_take_profit_pct}%"
            )
            return signal

        # 청산 조건 없음
        return None

    def get_position_size(
        self,
        balance: float,
        kelly_fraction: float = 0.0,
    ) -> float:
        """
        포지션 사이즈 계산

        Args:
            balance: 사용 가능한 잔액
            kelly_fraction: Kelly 공식 비율 (선택)

        Returns:
            float: 포지션 크기
        """
        if self.trend_config.use_kelly and kelly_fraction > 0:
            # Kelly 공식 사용
            position_size = kelly_fraction * self.trend_config.max_position_size
        else:
            # 고정 금액 사용
            position_size = self.trend_config.bet_amount_usdc

        # 최대 포지션 제한
        position_size = min(position_size, self.trend_config.max_position_size)

        # 잔액 초과 방지
        position_size = min(position_size, balance)

        return position_size

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"TrendStrategy(mode={self.trend_config.mode}, "
            f"enabled={self.trend_config.enabled})"
        )


# 전략 레지스트리에 등록
@register_strategy("trend", validate=True)
class _RegisteredTrendStrategy(TrendStrategy):
    """레지스트리 등록용 Trend 전략 래퍼"""

    pass
