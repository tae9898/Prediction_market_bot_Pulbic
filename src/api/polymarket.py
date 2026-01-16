from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from src.utils.config_loader import ConfigLoader
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PolymarketAPI:
    def __init__(self):
        self.host = ConfigLoader.get_env_var("POLYMARKET_HOST", "https://clob.polymarket.com")
        self.chain_id = int(ConfigLoader.get_env_var("CHAIN_ID", 137))
        self.private_key = ConfigLoader.get_env_var("PRIVATE_KEY")
        
        if not self.private_key:
            raise ValueError("PRIVATE_KEY not found in .env")

        try:
            # Initialize client with private key
            self.client = ClobClient(
                self.host,
                key=self.private_key,
                chain_id=self.chain_id
            )
            
            # Derive and set API credentials for L2 auth
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            logger.info("Polymarket API initialized successfully.")
            
        except Exception as e:
            logger.error(f"Failed to initialize Polymarket API: {e}")
            raise

    def get_market(self, condition_id):
        """Fetch market details by condition ID."""
        return self.client.get_market(condition_id)

    def get_price(self, token_id, side="buy"):
        """
        Get the current price for a token.
        side: 'buy' for ask price, 'sell' for bid price.
        """
        return self.client.get_price(token_id, side)

    def place_order(self, token_id, price, size, side):
        """
        Place a Limit Order.
        side: 'BUY' or 'SELL'
        """
        try:
            order_args = OrderArgs(
                price=float(price),
                size=float(size),
                side=side.upper(),
                token_id=token_id
            )
            # Defaulting to Limit Order (GTC)
            resp = self.client.create_and_post_order(order_args)
            logger.info(f"Order placed: {resp}")
            return resp
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    def cancel_all(self):
        """Cancel all open orders."""
        try:
            resp = self.client.cancel_all()
            logger.info("All orders cancelled.")
            return resp
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            raise

    def get_balance(self):
        """Get account balance/allowance info if available."""
        # Note: This usually checks allowance for the specific asset
        # Getting generic USDC balance might require a web3 call or a different endpoint
        # For now, let's return what the client offers
        return self.client.get_balance_allowance()
