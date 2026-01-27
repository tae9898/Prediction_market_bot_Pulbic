"""
Edge Hedge Strategy - 엣지 기반 진입 + 동적 헤지 전략

전략 개요:
1. 진입: FAIR 확률 > 마켓 확률 (edge >= 7%)인 방향에 매수
2. 수익 실현: 포지션이 상승하면 반대 포지션을 저가에 매수하여 확정 수익
3. 스탑로스: 포지션이 -15% 하락하면 반대 포지션 매수로 손실 제한
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Callable


@dataclass
class EdgeHedgePosition:
    """현재 포지션 상태"""

    asset_type: str = ""  # "BTC" or "ETH"
    direction: str = ""  # "UP" or "DOWN"
    entry_price: float = 0.0  # 진입 시 마켓 확률
    entry_fair: float = 0.0  # 진입 시 FAIR 확률
    entry_edge: float = 0.0  # 진입 시 edge
    size: float = 0.0
    cost: float = 0.0
    entry_time: float = 0.0

    # 헤지 상태
    is_hedged: bool = False
    hedge_direction: str = ""  # 헤지한 방향 (반대 방향)
    hedge_price: float = 0.0
    hedge_size: float = 0.0
    hedge_cost: float = 0.0
    hedge_type: str = ""  # "PROFIT" or "STOPLOSS"

    # 예상 손익
    expected_profit: float = 0.0


@dataclass
class StrategyConfig:
    """전략 설정"""

    enabled: bool = True  # 전략 활성화 여부

    # 진입 조건
    min_edge_pct: float = 10.0

    # 수익 실현 헤지 조건
    profit_hedge_threshold_pct: float = 7.0

    # 스탑로스 헤지 조건
    stoploss_trigger_pct: float = 15.0

    # 포지션 설정
    position_size_usdc: float = 10.0

    # 쿨다운
    entry_cooldown_sec: float = 30.0


class EdgeHedgeStrategy:
    """Edge 기반 진입 + 동적 헤지 전략"""

    def __init__(
        self,
        config: StrategyConfig = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.config = config or StrategyConfig()
        self._log_callback = log_callback

        # 자산별 포지션
        self.positions: Dict[str, EdgeHedgePosition] = {}

        # 자산별 마지막 진입 시간
        self._last_entry_time: Dict[str, float] = {}

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)
        else:
            print(message)

    def analyze_entry(
        self,
        asset_type: str,
        fair_up: float,
        fair_down: float,
        market_up: float,
        market_down: float,
    ) -> Optional[Dict]:
        """
        진입 기회 분석

        Returns:
            None: 진입 기회 없음
            Dict: {
                "direction": "UP" or "DOWN",
                "edge": edge 값,
                "fair": fair 확률,
                "market": market 확률
            }
        """
        if not self.config.enabled:
            return None

        # 쿨다운 체크
        last_entry = self._last_entry_time.get(asset_type, 0)
        if time.time() - last_entry < self.config.entry_cooldown_sec:
            return None

        # 이미 포지션이 있으면 진입 안함
        if asset_type in self.positions and self.positions[asset_type].size > 0:
            return None

        # Edge 계산: (FAIR - Market) * 100
        edge_up = (fair_up - market_up) * 100
        edge_down = (fair_down - market_down) * 100

        # 더 우세한 방향 선택 (FAIR가 높은 쪽)
        if fair_up > fair_down:
            # UP이 더 가능성 높음
            if edge_up >= self.config.min_edge_pct:
                return {
                    "direction": "UP",
                    "edge": edge_up,
                    "fair": fair_up,
                    "market": market_up,
                    "opposite_market": market_down,
                }
            else:
                self._log(
                    f"[EdgeHedge] Skip UP: Edge {edge_up:.2f}% < {self.config.min_edge_pct}%"
                )
        else:
            # DOWN이 더 가능성 높음
            if edge_down >= self.config.min_edge_pct:
                return {
                    "direction": "DOWN",
                    "edge": edge_down,
                    "fair": fair_down,
                    "market": market_down,
                    "opposite_market": market_up,
                }
            else:
                self._log(
                    f"[EdgeHedge] Skip DOWN: Edge {edge_down:.2f}% < {self.config.min_edge_pct}%"
                )

        return None

    def analyze_profit_hedge(
        self,
        asset_type: str,
        market_up_bid: float,
        market_down_bid: float,
        market_up_ask: float,
        market_down_ask: float,
    ) -> Optional[Dict]:
        """
        수익 실현 헤지 분석

        포지션 가치(Bid)가 상승하여 반대 포지션 매수(Ask) 비용을 감당하고도 확정 수익이 날 때
        """
        pos = self.positions.get(asset_type)
        if not pos or pos.size <= 0 or pos.is_hedged:
            return None

        # 내 포지션의 현재 가치 (Bid 사용)
        if pos.direction == "UP":
            current_val_price = market_up_bid
            # 헷지하려면 반대쪽(DOWN)을 사야 함 (Ask 사용)
            hedge_cost_price = market_down_ask
            hedge_direction = "DOWN"
        else:
            current_val_price = market_down_bid
            # 헷지하려면 반대쪽(UP)을 사야 함 (Ask 사용)
            hedge_cost_price = market_up_ask
            hedge_direction = "UP"

        # 포지션 상승률 계산 (진입가 대비 현재 Bid 가치)
        price_change_pct = (
            (current_val_price - pos.entry_price) / pos.entry_price
        ) * 100

        # 수익 실현 조건: 포지션 가격이 threshold 만큼 상승
        if price_change_pct >= self.config.profit_hedge_threshold_pct:
            # 총 비용 = 진입 비용 + 헷지 비용
            # 여기서 진입 비용은 이미 지불함.
            # 확정 수익 계산: (1.0 - (진입가 + 헷지가))
            # 바이너리 옵션 만기 시 둘 중 하나는 $1이 됨. 따라서 총 투입 비용이 $1보다 작으면 무조건 이득.
            total_cost = pos.entry_price + hedge_cost_price

            expected_profit_pct = (1.0 - total_cost) * 100

            # ⚠️ 핵심 검증: 총 비용이 100% 미만이어야 수익 가능
            if total_cost >= 1.0:
                # self._log(f"[{asset_type}] ❌ 헤지 불가: 총 비용 {total_cost*100:.1f}% >= 100% (확정 손실)")
                return None

            if expected_profit_pct > 0:
                return {
                    "type": "PROFIT",
                    "direction": hedge_direction,
                    "opposite_price": hedge_cost_price,
                    "expected_profit_pct": expected_profit_pct,
                    "position_gain_pct": price_change_pct,
                    "total_cost": total_cost,
                }

        return None

    def analyze_stoploss_hedge(
        self,
        asset_type: str,
        market_up_bid: float,
        market_down_bid: float,
        market_up_ask: float,
        market_down_ask: float,
    ) -> Optional[Dict]:
        """
        스탑로스 헤지 분석

        포지션 가치(Bid)가 하락하면 반대 포지션 매수(Ask)로 손실 제한
        """
        pos = self.positions.get(asset_type)
        if not pos or pos.size <= 0 or pos.is_hedged:
            return None

        # 내 포지션의 현재 가치 (Bid 사용)
        if pos.direction == "UP":
            current_val_price = market_up_bid
            # 헷지하려면 반대쪽(DOWN)을 사야 함 (Ask 사용)
            hedge_cost_price = market_down_ask
            hedge_direction = "DOWN"
        else:
            current_val_price = market_down_bid
            # 헷지하려면 반대쪽(UP)을 사야 함 (Ask 사용)
            hedge_cost_price = market_up_ask
            hedge_direction = "UP"

        # 포지션 하락률 계산 (진입가 대비 현재 Bid 가치)
        price_change_pct = (
            (current_val_price - pos.entry_price) / pos.entry_price
        ) * 100

        # 디버그 로그 추가
        # self._log(f"~EdgeHedge SL Check~ [{asset_type}] Dir:{pos.direction}, Entry:{pos.entry_price:.4f}, Bid:{current_val_price:.4f}, Change:{price_change_pct:.1f}%, Trigger:{-self.config.stoploss_trigger_pct:.1f}%")

        # Console Debug for User
        if price_change_pct <= -5.0:  # -5% 이상 손실이면 로그 출력
            print(
                f"[DEBUG] {asset_type} Loss: {price_change_pct:.1f}% (Entry: {pos.entry_price:.3f}, Current: {current_val_price:.3f})"
            )

        # 스탑로스 조건: 포지션 가격이 threshold 만큼 하락
        if price_change_pct <= -self.config.stoploss_trigger_pct:
            # 총 비용 = 진입 비용 + 헷지 비용
            total_cost = pos.entry_price + hedge_cost_price

            # 예상 손익 계산 (1.0 - 총비용)
            expected_pnl_pct = (1.0 - total_cost) * 100

            return {
                "type": "STOPLOSS",
                "direction": hedge_direction,
                "opposite_price": hedge_cost_price,
                "expected_pnl_pct": expected_pnl_pct,
                "position_loss_pct": price_change_pct,
                "total_cost": total_cost,
            }

        return None

    def record_entry(
        self,
        asset_type: str,
        direction: str,
        entry_price: float,
        fair_price: float,
        edge: float,
        size: float,
        cost: float,
    ) -> None:
        """진입 기록"""
        self.positions[asset_type] = EdgeHedgePosition(
            asset_type=asset_type,
            direction=direction,
            entry_price=entry_price,
            entry_fair=fair_price,
            entry_edge=edge,
            size=size,
            cost=cost,
            entry_time=time.time(),
        )
        self._last_entry_time[asset_type] = time.time()
        self._log(
            f"[{asset_type}] 진입: {direction} @{entry_price * 100:.1f}% (Edge: +{edge:.1f}%)"
        )

    def record_hedge(
        self,
        asset_type: str,
        hedge_type: str,
        hedge_direction: str,
        hedge_price: float,
        hedge_size: float,
        hedge_cost: float,
        expected_profit: float,
    ) -> None:
        """헤지 기록"""
        pos = self.positions.get(asset_type)
        if pos:
            pos.is_hedged = True
            pos.hedge_type = hedge_type
            pos.hedge_direction = hedge_direction
            pos.hedge_price = hedge_price
            pos.hedge_size = hedge_size
            pos.hedge_cost = hedge_cost
            pos.expected_profit = expected_profit

            self._log(
                f"[{asset_type}] {hedge_type} 헤지: {hedge_direction} @{hedge_price * 100:.1f}% (예상: {'+' if expected_profit >= 0 else ''}{expected_profit:.2f}%)"
            )

    def clear_position(self, asset_type: str) -> None:
        """포지션 정리 (마켓 만료 시)"""
        if asset_type in self.positions:
            del self.positions[asset_type]
            self._log(f"[{asset_type}] 포지션 정리 (마켓 만료)")

    def get_position_status(self, asset_type: str) -> Optional[Dict]:
        """현재 포지션 상태 조회"""
        pos = self.positions.get(asset_type)
        if not pos or pos.size <= 0:
            return None

        return {
            "direction": pos.direction,
            "entry_price": pos.entry_price,
            "size": pos.size,
            "is_hedged": pos.is_hedged,
            "hedge_type": pos.hedge_type,
            "expected_profit": pos.expected_profit,
        }
