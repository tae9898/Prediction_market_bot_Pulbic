"""
BTC Polymarket ARB Bot V3 - Sure-Bet Arbitrage Engine
Binary Market에서 YES + NO를 동시 매수하여 확정 수익 확보
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from enum import Enum


@dataclass
class OrderbookLevel:
    """오더북 호가 단계"""

    price: float
    size: float

    @property
    def value(self) -> float:
        """이 레벨의 총 가치 (price * size)"""
        return self.price * self.size


@dataclass
class ArbitrageOpportunity:
    """아비트라지 기회 분석 결과"""

    # VWAP 가격
    vwap_yes: float = 0.0
    vwap_no: float = 0.0

    # 수익성 지표
    total_cost: float = 0.0  # VWAP(YES) + VWAP(NO)
    spread: float = 0.0  # 1.0 - total_cost
    profit_rate: float = 0.0  # 수익률 (%)

    # 수량 정보
    max_size: float = 0.0  # 수익 구간 최대 수량
    max_profit: float = 0.0  # 최대 이익 ($)

    # 상태
    is_profitable: bool = False
    reason: str = ""

    # 오더북 깊이 정보
    yes_liquidity: float = 0.0  # YES 쪽 총 유동성
    no_liquidity: float = 0.0  # NO 쪽 총 유동성


class SurebetEngine:
    """
    Sure-Bet Arbitrage Engine
    Binary Market에서 YES + NO를 동시 매수하여 확정 수익 확보
    """

    def __init__(
        self,
        enabled: bool = True,
        min_profit_rate: float = 1.0,
        slippage_tolerance: float = 0.005,
        min_size: float = 5.0,
    ):
        self.enabled = enabled
        self.min_profit_rate = min_profit_rate
        self.slippage_tolerance = slippage_tolerance
        self.min_size = min_size

    def parse_orderbook(self, raw_levels: List[Dict]) -> List[OrderbookLevel]:
        """
        원시 오더북 데이터를 OrderbookLevel 리스트로 변환

        Args:
            raw_levels: [{"price": "0.45", "size": "100"}, ...] 또는 [[price, size], ...]
        """
        levels = []
        for item in raw_levels:
            if isinstance(item, dict):
                price = float(item.get("price", 0))
                size = float(item.get("size", 0))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                price = float(item[0])
                size = float(item[1])
            else:
                continue

            if price > 0 and size > 0:
                levels.append(OrderbookLevel(price=price, size=size))

        # 가격순 오름차순 정렬 (Ask는 낮은 가격이 먼저)
        levels.sort(key=lambda x: x.price)
        return levels

    def calculate_vwap(
        self, levels: List[OrderbookLevel], target_size: float
    ) -> Tuple[float, float]:
        """
        목표 수량에 대한 VWAP(Volume Weighted Average Price) 계산

        Args:
            levels: 오더북 레벨 리스트 (가격순 정렬됨)
            target_size: 목표 수량

        Returns:
            (vwap, actual_size): VWAP 가격과 실제 소화 가능 수량
        """
        if not levels or target_size <= 0:
            return 0.0, 0.0

        total_cost = 0.0
        total_size = 0.0

        for level in levels:
            remaining = target_size - total_size
            if remaining <= 0:
                break

            take_size = min(level.size, remaining)
            total_cost += level.price * take_size
            total_size += take_size

        if total_size == 0:
            return 0.0, 0.0

        vwap = total_cost / total_size
        return vwap, total_size

    def find_max_profitable_size(
        self,
        yes_asks: List[OrderbookLevel],
        no_asks: List[OrderbookLevel],
        max_search_size: float = 1000.0,
        step: float = 1.0,
    ) -> ArbitrageOpportunity:
        """
        수익 구간이 끝나는 지점까지의 최대 수량 계산

        이진 탐색 + 점진적 확인으로 최적 수량 찾기

        Args:
            yes_asks: YES 토큰 Ask 오더북
            no_asks: NO 토큰 Ask 오더북
            max_search_size: 탐색 최대 수량
            step: 탐색 단계
        """
        if not yes_asks or not no_asks:
            return ArbitrageOpportunity(
                is_profitable=False, reason="오더북 데이터 없음"
            )

        # 총 유동성 계산
        yes_liquidity = sum(level.size for level in yes_asks)
        no_liquidity = sum(level.size for level in no_asks)
        max_possible = min(yes_liquidity, no_liquidity, max_search_size)

        if max_possible < self.min_size:
            return ArbitrageOpportunity(
                is_profitable=False,
                reason=f"유동성 부족 (YES: {yes_liquidity:.2f}, NO: {no_liquidity:.2f})",
                yes_liquidity=yes_liquidity,
                no_liquidity=no_liquidity,
            )

        # 최소 수량에서 시작하여 점진적으로 증가
        best_opportunity = None
        best_profit = 0.0

        current_size = self.min_size
        while current_size <= max_possible:
            vwap_yes, actual_yes = self.calculate_vwap(yes_asks, current_size)
            vwap_no, actual_no = self.calculate_vwap(no_asks, current_size)

            # 어느 한쪽이 수량을 채우지 못하면 중단
            actual_size = min(actual_yes, actual_no)
            if actual_size < current_size * 0.99:  # 99% 미만이면 중단
                break

            total_cost = vwap_yes + vwap_no
            spread = 1.0 - total_cost
            profit_rate = (spread / total_cost) * 100 if total_cost > 0 else 0

            # 수익률이 최소 기준 미달이면 더 이상 탐색 불필요
            if profit_rate < self.min_profit_rate:
                break

            # 더 나은 기회 발견
            potential_profit = actual_size * spread
            if potential_profit > best_profit:
                best_profit = potential_profit
                best_opportunity = ArbitrageOpportunity(
                    vwap_yes=vwap_yes,
                    vwap_no=vwap_no,
                    total_cost=total_cost,
                    spread=spread,
                    profit_rate=profit_rate,
                    max_size=actual_size,
                    max_profit=potential_profit,
                    is_profitable=True,
                    reason=f"수익률 {profit_rate:.2f}% @ {actual_size:.2f}주",
                    yes_liquidity=yes_liquidity,
                    no_liquidity=no_liquidity,
                )

            current_size += step

        if best_opportunity:
            return best_opportunity

        # 기회 없음
        vwap_yes, _ = self.calculate_vwap(yes_asks, self.min_size)
        vwap_no, _ = self.calculate_vwap(no_asks, self.min_size)
        total_cost = vwap_yes + vwap_no
        spread = 1.0 - total_cost
        profit_rate = (spread / total_cost) * 100 if total_cost > 0 else 0

        return ArbitrageOpportunity(
            vwap_yes=vwap_yes,
            vwap_no=vwap_no,
            total_cost=total_cost,
            spread=spread,
            profit_rate=profit_rate,
            max_size=0,
            max_profit=0,
            is_profitable=False,
            reason=f"수익률 부족 ({profit_rate:.2f}% < {self.min_profit_rate}%)",
            yes_liquidity=yes_liquidity,
            no_liquidity=no_liquidity,
        )

    def analyze(self, yes_asks_raw: List, no_asks_raw: List) -> ArbitrageOpportunity:
        """
        아비트라지 기회 분석 - 메인 진입점

        Args:
            yes_asks_raw: YES 토큰 Ask 오더북 (원시 데이터)
            no_asks_raw: NO 토큰 Ask 오더북 (원시 데이터)

        Returns:
            ArbitrageOpportunity: 분석 결과
        """
        yes_asks = self.parse_orderbook(yes_asks_raw)
        no_asks = self.parse_orderbook(no_asks_raw)

        return self.find_max_profitable_size(yes_asks, no_asks)

    def quick_check(self, best_yes_ask: float, best_no_ask: float) -> bool:
        """
        빠른 기회 확인 (Best Ask 기준)

        오더북 전체를 분석하기 전에 빠르게 기회 여부 확인
        """
        if best_yes_ask <= 0 or best_no_ask <= 0:
            return False

        total = best_yes_ask + best_no_ask
        spread = 1.0 - total
        profit_rate = (spread / total) * 100

        # 슬리피지 고려하여 여유있게 판단
        return profit_rate >= (self.min_profit_rate + self.slippage_tolerance * 100)

    def calculate_order_params(
        self, opportunity: ArbitrageOpportunity, amount_usdc: float
    ) -> Dict:
        """
        주문 파라미터 계산

        Args:
            opportunity: 아비트라지 기회
            amount_usdc: 투자 금액 (USDC)

        Returns:
            {
                "yes_size": float,
                "yes_max_price": float,
                "no_size": float,
                "no_max_price": float,
                "expected_profit": float
            }
        """
        if not self.enabled:
            return {}

        if not opportunity.is_profitable:
            return {}

        # 최대 수량 기준으로 주문 크기 결정
        size = min(opportunity.max_size, amount_usdc / opportunity.total_cost)

        # 슬리피지 허용치 추가
        yes_max_price = opportunity.vwap_yes * (1 + self.slippage_tolerance)
        no_max_price = opportunity.vwap_no * (1 + self.slippage_tolerance)

        expected_profit = size * opportunity.spread

        return {
            "yes_size": size,
            "yes_max_price": yes_max_price,
            "no_size": size,
            "no_max_price": no_max_price,
            "expected_profit": expected_profit,
            "profit_rate": opportunity.profit_rate,
        }


# 테스트용
if __name__ == "__main__":
    engine = SurebetEngine(min_profit_rate=1.0)

    # 테스트 오더북
    yes_asks = [
        {"price": "0.45", "size": "100"},
        {"price": "0.46", "size": "200"},
        {"price": "0.47", "size": "300"},
    ]

    no_asks = [
        {"price": "0.52", "size": "100"},
        {"price": "0.53", "size": "200"},
        {"price": "0.54", "size": "300"},
    ]

    result = engine.analyze(yes_asks, no_asks)
    print(f"Profitable: {result.is_profitable}")
    print(f"VWAP YES: ${result.vwap_yes:.4f}")
    print(f"VWAP NO: ${result.vwap_no:.4f}")
    print(f"Total Cost: ${result.total_cost:.4f}")
    print(f"Spread: ${result.spread:.4f}")
    print(f"Profit Rate: {result.profit_rate:.2f}%")
    print(f"Max Size: {result.max_size:.2f}")
    print(f"Max Profit: ${result.max_profit:.2f}")
    print(f"Reason: {result.reason}")
