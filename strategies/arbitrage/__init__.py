"""
Arbitrage Strategy Package

Sure-bet arbitrage strategy for binary prediction markets.
Simultaneously buys YES and NO tokens when price discrepancy guarantees profit.
"""

from .strategy import SurebetEngine
from .config import ArbitrageConfig

__all__ = [
    "SurebetEngine",
    "ArbitrageConfig",
]
