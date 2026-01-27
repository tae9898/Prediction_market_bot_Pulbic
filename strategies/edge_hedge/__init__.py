"""
Edge Hedge Strategy Package

Edge-based entry with dynamic hedging strategy for binary options trading.
"""

from strategies.edge_hedge.config import EdgeHedgeConfig
from strategies.edge_hedge.strategy import EdgeHedgeStrategy

__all__ = [
    "EdgeHedgeConfig",
    "EdgeHedgeStrategy",
]
