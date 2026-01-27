"""
Strategies Module - Trading Strategy Implementations

이 패키지는 모든 거래 전략을 포함합니다.
이 모듈을 임포트하면 모든 전략이 자동으로 registry에 등록됩니다.

사용 가능한 전략:
- trend: 방향성/역추세 통합 전략
- arbitrage: Sure-Bet 전략
- edge_hedge: Edge 헷징 전략
- expiry_sniper: 만료 스나이퍼 전략
"""

# 자동 등록을 위해 모든 전략 임포트
from strategies.trend.strategy import TrendStrategy
from strategies.arbitrage.strategy import SurebetEngine
from strategies.edge_hedge.strategy import EdgeHedgeStrategy
from strategies.expiry_sniper.strategy import ExpirySniperStrategy

# 타입 힌트를 위해 내보내기
__all__ = [
    "TrendStrategy",
    "SurebetEngine",
    "EdgeHedgeStrategy",
    "ExpirySniperStrategy",
]
