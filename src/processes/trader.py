import time
import logging
import json
import os
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

def load_wallets():
    if os.path.exists("wallets.json"):
        with open("wallets.json", 'r') as f:
            return json.load(f)
    return {}

def main():
    try:
        loader = ConfigLoader()
        markets = loader._config.get("markets", [])
        trading_config = loader.get_trading_config()
        
        # Load all wallets
        wallets_data = load_wallets()
        if not wallets_data:
            logger.warning("No wallets found in wallets.json. Please run scripts/setup_api_keys.py first.")
            return

        # Initialize API instances for each wallet
        # Cache them to avoid creating multiple clients for the same wallet
        api_instances = {} 
        
        for label, w in wallets_data.items():
            try:
                api_instances[label] = PolymarketAPI(
                    private_key=w.get("private_key"),
                    funder=w.get("funder"),
                    api_key=w.get("api_key"),
                    api_secret=w.get("api_secret"),
                    api_passphrase=w.get("api_passphrase"),
                    signature_type=w.get("signature_type", 2)
                )
            except Exception as e:
                logger.error(f"Failed to initialize wallet '{label}': {e}")

        # Initialize strategies
        active_strategies = []
        for m in markets:
            strat_name = m.get("strategy")
            wallet_label = m.get("wallet_label", "main")
            
            # Check if wallet exists
            if wallet_label not in api_instances:
                logger.error(f"Wallet '{wallet_label}' not found for market {m.get('description')}. Skipping.")
                continue
                
            api = api_instances[wallet_label]
            strat_cls = STRATEGY_MAP.get(strat_name)
            
            if strat_cls:
                strategy_instance = strat_cls(m.get("strategy_config", {}))
                active_strategies.append({
                    "market": m,
                    "strategy": strategy_instance,
                    "api": api,  # Assign the specific API instance for this market
                    "wallet_label": wallet_label
                })
                logger.info(f"Loaded strategy '{strat_name}' for market {m.get('description')} using wallet '{wallet_label}'")
            else:
                logger.warning(f"Strategy '{strat_name}' not found for market {m.get('description')}")

        logger.info("Trader Process Started. Monitoring markets...")
        
        while True:
            for item in active_strategies:
                market = item["market"]
                strategy = item["strategy"]
                api = item["api"]
                token_id = market["token_id"]
                
                if token_id == "REPLACE_WITH_TOKEN_ID":
                    continue

                try:
                    # Fetch current price
                    price_resp = api.get_price(token_id, side="buy")
                    
                    current_price = None
                    if price_resp:
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
                            logger.info(f"Signal detected for {token_id} at price {current_price} (Wallet: {item['wallet_label']})")
                            
                            order_details = strategy.get_order_details(market_data)
                            
                            # Execute Order
                            api.place_order(
                                token_id=order_details['token_id'],
                                price=order_details['price'],
                                size=order_details['size'],
                                side=order_details['side']
                            )
                except Exception as e:
                    logger.error(f"Error processing {token_id} (Wallet: {item['wallet_label']}): {e}")
            
            time.sleep(trading_config.get("interval_seconds", 1))

    except Exception as e:
        logger.critical(f"Trader process crashed: {e}")
        raise

if __name__ == "__main__":
    main()
