"""
BTC Polymarket ARB Bot V3 - Probability Model
Black-Scholes 바이너리 옵션 확률 모델
"""

import math
from dataclasses import dataclass
from typing import Tuple
from scipy.stats import norm


@dataclass
class ProbabilityResult:
    """확률 계산 결과"""
    fair_up: float = 0.5       # UP 공정 확률
    fair_down: float = 0.5     # DOWN 공정 확률
    d2: float = 0.0            # d2 값 (디버깅용)
    edge_up: float = 0.0       # UP 에지
    edge_down: float = 0.0     # DOWN 에지


class ProbabilityModel:
    """
    Black-Scholes 바이너리 옵션 확률 모델
    
    P(Up) = N(d2)
    d2 = [ln(S/K) + (r - σ²/2)T] / (σ√T)
    
    Variables:
        S: 현재 BTC 가격 (Binance)
        K: 행사가 (Strike Price, 1시간 캔들 시가)
        r: 무위험 이자율 (암호화폐 = 0)
        σ: 연간 변동성 (Annualized Volatility)
        T: 만기까지 남은 시간 (연 단위)
    """
    
    HOURS_PER_YEAR = 8760  # 365.25 × 24
    
    def __init__(self, subtract_spread: bool = True):
        """
        Args:
            subtract_spread: Edge 계산 시 스프레드 차감 여부
        """
        self.subtract_spread = subtract_spread
    
    def calculate_fair_probability(
        self,
        current_price: float,
        strike_price: float,
        time_remaining_seconds: int,
        volatility_annual: float,
        risk_free_rate: float = 0.0
    ) -> Tuple[float, float, float]:
        """
        Black-Scholes d2 기반 공정 확률 계산
        
        Args:
            current_price: 현재 BTC 가격 (S)
            strike_price: 행사가 (K)
            time_remaining_seconds: 만기까지 남은 시간 (초)
            volatility_annual: 연간 변동성 (예: 0.60 = 60%)
            risk_free_rate: 무위험 이자율 (기본값: 0)
        
        Returns:
            Tuple[fair_up, fair_down, d2]:
                - fair_up: UP 공정 확률 (0~1)
                - fair_down: DOWN 공정 확률 (0~1)
                - d2: d2 값
        """
        # 입력 검증
        if current_price <= 0 or strike_price <= 0:
            return 0.5, 0.5, 0.0
        
        if time_remaining_seconds <= 0:
            # 만료 시점: 현재 가격 기준
            if current_price >= strike_price:
                return 1.0, 0.0, float('inf')
            else:
                return 0.0, 1.0, float('-inf')
        
        if volatility_annual <= 0:
            volatility_annual = 0.60  # 기본값 60%
        
        # 시간을 연 단위로 변환
        T = time_remaining_seconds / (self.HOURS_PER_YEAR * 3600)
        
        # d2 계산
        # d2 = [ln(S/K) + (r - σ²/2)T] / (σ√T)
        S = current_price
        K = strike_price
        r = risk_free_rate
        sigma = volatility_annual
        
        sqrt_T = math.sqrt(T)
        
        numerator = math.log(S / K) + (r - (sigma ** 2) / 2) * T
        denominator = sigma * sqrt_T
        
        if denominator == 0:
            d2 = 0.0
        else:
            d2 = numerator / denominator
        
        # 정규 분포 CDF로 확률 계산
        fair_up = norm.cdf(d2)
        fair_down = 1.0 - fair_up
        
        # 범위 제한 (0.01 ~ 0.99)
        fair_up = max(0.01, min(0.99, fair_up))
        fair_down = max(0.01, min(0.99, fair_down))
        
        return fair_up, fair_down, d2
    
    def calculate_edge(
        self,
        fair_probability: float,
        market_price: float,
        spread: float = 0.0
    ) -> float:
        """
        에지 계산
        
        Edge = (Fair_Probability - Market_Price) × 100
        
        Args:
            fair_probability: 공정 확률 (0~1)
            market_price: 시장 가격 (0~1)
            spread: 스프레드 (선택적 차감)
        
        Returns:
            Edge (percentage): 양수 = 저평가(매수 기회), 음수 = 고평가
        """
        edge = (fair_probability - market_price) * 100
        
        if self.subtract_spread and spread > 0:
            edge -= spread * 100
        
        return edge
    
    def calculate_kelly_fraction(
        self,
        fair_probability: float,
        market_price: float
    ) -> float:
        """
        Kelly Criterion 최적 베팅 비율 계산
        
        f* = (p × b - q) / b
        
        p = 승리 확률 (Fair Probability)
        q = 1 - p (패배 확률)
        b = 배당률 = (1 - price) / price
        
        Args:
            fair_probability: 공정 확률 (0~1)
            market_price: 시장 가격 (0~1)
        
        Returns:
            Kelly fraction (0~1): 최적 베팅 비율
        """
        if market_price <= 0 or market_price >= 1:
            return 0.0
        
        p = fair_probability
        q = 1 - p
        b = (1 - market_price) / market_price  # 배당률
        
        if b <= 0:
            return 0.0
        
        kelly = (p * b - q) / b
        
        # 음수면 베팅하지 않음
        return max(0.0, min(1.0, kelly))
    
    def analyze(
        self,
        current_price: float,
        strike_price: float,
        time_remaining_seconds: int,
        volatility_annual: float,
        market_up: float,
        market_down: float,
        spread_up: float = 0.0,
        spread_down: float = 0.0
    ) -> ProbabilityResult:
        """
        전체 확률 분석 수행
        
        Args:
            current_price: 현재 BTC 가격
            strike_price: 행사가
            time_remaining_seconds: 만기까지 남은 시간 (초)
            volatility_annual: 연간 변동성
            market_up: UP 시장 가격 (ask)
            market_down: DOWN 시장 가격 (ask)
            spread_up: UP 스프레드
            spread_down: DOWN 스프레드
        
        Returns:
            ProbabilityResult: 분석 결과
        """
        fair_up, fair_down, d2 = self.calculate_fair_probability(
            current_price, strike_price, time_remaining_seconds, volatility_annual
        )
        
        edge_up = self.calculate_edge(fair_up, market_up, spread_up)
        edge_down = self.calculate_edge(fair_down, market_down, spread_down)
        
        return ProbabilityResult(
            fair_up=fair_up,
            fair_down=fair_down,
            d2=d2,
            edge_up=edge_up,
            edge_down=edge_down,
        )
    
    def get_signal(
        self,
        result: ProbabilityResult,
        current_price: float,
        strike_price: float,
        edge_threshold: float = 3.0
    ) -> Tuple[str, str]:
        """
        매매 시그널 생성
        
        Args:
            result: 확률 분석 결과
            current_price: 현재 BTC 가격
            strike_price: 행사가
            edge_threshold: 최소 에지 임계값
        
        Returns:
            Tuple[signal, direction]:
                - signal: "BUY", "SELL", "HOLD"
                - direction: "UP" or "DOWN"
        """
        # 방향성 전략: BTC 위치에 따라
        if current_price > strike_price:
            # BTC가 행사가 위
            if result.edge_up >= edge_threshold:
                return "BUY", "UP"
        else:
            # BTC가 행사가 아래
            if result.edge_down >= edge_threshold:
                return "BUY", "DOWN"
        
        return "HOLD", ""
