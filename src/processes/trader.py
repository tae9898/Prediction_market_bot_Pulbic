import time
import logging
from src.api.polymarket import PolymarketAPI
from src.utils.config_loader import ConfigLoader
from src.strategies.simple_strategy import SimpleStrategy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Trader")

# Strategy Registry
STRATEGY_MAP = {
    "simple": SimpleStrategy
}

def main():
    try:
        loader = ConfigLoader()
        api = PolymarketAPI()
        markets = loader._config.get("markets", [])
        trading_config = loader.get_trading_config()
        
        # Initialize strategies
        active_strategies = []
        for m in markets:
            strat_name = m.get("strategy")
            strat_cls = STRATEGY_MAP.get(strat_name)
            if strat_cls:
                strategy_instance = strat_cls(m.get("strategy_config", {}))
                active_strategies.append({
                    "market": m,
                    "strategy": strategy_instance
                })
                logger.info(f"Loaded strategy '{strat_name}' for market {m.get('description')}")
            else:
                logger.warning(f"Strategy '{strat_name}' not found for market {m.get('description')}")

        logger.info("Trader Process Started. Monitoring markets...")
        
        while True:
            for item in active_strategies:
                market = item["market"]
                strategy = item["strategy"]
                token_id = market["token_id"]
                
                if token_id == "REPLACE_WITH_TOKEN_ID":
                    continue

                try:
                    # Fetch current price (Ask side for buying)
                    # Note: get_price usually returns a structure or value. 
                    # We convert to float safely.
                    price_resp = api.get_price(token_id, side="buy")
                    
                    current_price = None
                    if price_resp:
                        # Handle potential dict return or direct value
                        if isinstance(price_resp, dict):
                            current_price = float(price_resp.get('price', 0))
                        else:
                            current_price = float(price_resp)

                    market_data = {
                        "token_id": token_id,
                        "price": current_price
                    }

                    if current_price is not None:
                        if strategy.should_enter(market_data):
                            logger.info(f"Signal detected for {token_id} at price {current_price}")
                            
                            order_details = strategy.get_order_details(market_data)
                            
                            # Execute Order
                            api.place_order(
                                token_id=order_details['token_id'],
                                price=order_details['price'],
                                size=order_details['size'],
                                side=order_details['side']
                            )
                except Exception as e:
                    logger.error(f"Error processing {token_id}: {e}")
            
            time.sleep(trading_config.get("interval_seconds", 1))

    except Exception as e:
        logger.critical(f"Trader process crashed: {e}")
        raise

if __name__ == "__main__":
    main()
