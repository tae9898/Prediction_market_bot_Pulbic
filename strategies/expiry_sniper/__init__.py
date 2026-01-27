"""
Expiry Sniper Strategy - 마감 직전 고확률 배팅 전략

전략 개요:
1. 마감 A분 전 (예: 15분)
2. 확률 B% 이상 (예: 98%) - 한쪽 방향이 확실할 때
3. C 달러만큼 매수
4. 최대 D번 진입
5. E초 간격으로 분할 매수
"""

from strategies.expiry_sniper.strategy import ExpirySniperStrategy
from strategies.expiry_sniper.config import ExpirySniperConfig, SniperState

__all__ = [
    "ExpirySniperStrategy",
    "ExpirySniperConfig",
    "SniperState",
]
