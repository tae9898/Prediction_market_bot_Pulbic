from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from src.utils.config_loader import ConfigLoader
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PolymarketAPI:
    def __init__(self, private_key, funder, api_key=None, api_secret=None, api_passphrase=None, chain_id=137, host="https://clob.polymarket.com", signature_type=2):
        self.host = host
        self.chain_id = int(chain_id)
        self.private_key = private_key
        self.funder = funder
        self.signature_type = int(signature_type)
        
        if not self.private_key or not self.funder:
            raise ValueError("private_key and funder are required")

        try:
            from py_clob_client.clob_types import ApiCreds
            
            # Initialize client with full credentials if available
            creds = None
            if api_key and api_secret and api_passphrase:
                creds = ApiCreds(
                    api_key=api_key,
                    api_secret=api_secret,
                    api_passphrase=api_passphrase
                )

            self.client = ClobClient(
                self.host,
                key=self.private_key,
                chain_id=self.chain_id,
                signature_type=self.signature_type,
                funder=self.funder,
                api_creds=creds
            )
            
            # Mask private key for logging
            masked_key = self.private_key[:6] + "..." if self.private_key else "None"
            logger.info(f"Polymarket API initialized for {self.funder} (Key: {masked_key})")
            
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

    def get_order_book(self, token_id):
        """Get order book for a specific token."""
        try:
            return self.client.get_order_book(token_id)
        except Exception as e:
            logger.error(f"Error fetching Polymarket orderbook for {token_id}: {e}")
            raise

    def get_balance(self):
        """Get account balance/allowance info if available."""
        # Note: This usually checks allowance for the specific asset
        # Getting generic USDC balance might require a web3 call or a different endpoint
        # For now, let's return what the client offers
        return self.client.get_balance_allowance()
