import logging
from src.api.binance import BinanceAPI

logger = logging.getLogger(__name__)

class OrderBookManager:
    def __init__(self, polymarket_api=None):
        # polymarket_api is kept in signature for compatibility but not used for OB
        self.binance_api = BinanceAPI()

    def get_combined_data(self, poly_token_id, binance_symbol):
        """
        Fetch order books from both exchanges and return a combined structure.
        Restored Polymarket fetching as per request.
        """
        poly_ob = None
        binance_ob = None
        
        try:
            # Fetch Polymarket Orderbook (Full Depth)
            if self.poly_api:
                poly_ob = self.poly_api.get_order_book(poly_token_id)
        except Exception as e:
            logger.error(f"Error fetching Polymarket OB: {e}")

        try:
             # Fetch Binance Orderbook
            binance_ob = self.binance_api.get_order_book(binance_symbol)
        except Exception as e:
            logger.error(f"Error fetching Binance OB: {e}")

        return {
            "polymarket": poly_ob,
            "binance": binance_ob
        }
