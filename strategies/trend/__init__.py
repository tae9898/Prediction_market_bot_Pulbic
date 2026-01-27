"""
Trend Strategy - 방향성/역추세 통합 매매 전략

전략 모드:
- directional: BTC가 행사가 위면 UP, 아래면 DOWN (edge_threshold 이상)
- contrarian: BTC가 행사가 위지만 DOWN edge 범위, 아래지만 UP edge 범위
- auto: 상황에 따라 둘 중 더 유리한 쪽 선택
"""

from .strategy import TrendStrategy
from .config import TrendConfig, TrendMode

__all__ = [
    "TrendStrategy",
    "TrendConfig",
    "TrendMode",
]
