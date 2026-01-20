from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def should_enter(self, market_data):
        """
        Analyze market data and decide whether to enter a trade.
        market_data: dict containing prices, orderbooks, etc.
        Returns: boolean
        """
        pass

    @abstractmethod
    def get_order_details(self, market_data):
        """
        Calculate order parameters.
        Returns: dict with {'price': float, 'size': float, 'side': 'BUY'|'SELL', 'token_id': str}
        """
        pass
