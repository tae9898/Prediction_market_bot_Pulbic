import ccxt
import logging

logger = logging.getLogger(__name__)

class BinanceAPI:
    def __init__(self):
        self.client = ccxt.binance({
            'enableRateLimit': True,
        })
        logger.info("Binance API initialized (ccxt).")

    def get_order_book(self, symbol, limit=20):
        """
        Fetch order book for a given symbol.
        symbol: e.g., 'BTC/USDT'
        limit: depth of order book
        """
        try:
            return self.client.fetch_order_book(symbol, limit)
        except Exception as e:
            logger.error(f"Error fetching Binance orderbook for {symbol}: {e}")
            return None

    def get_price(self, symbol):
        """Fetch current ticker price."""
        try:
            ticker = self.client.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching Binance price for {symbol}: {e}")
            return None
