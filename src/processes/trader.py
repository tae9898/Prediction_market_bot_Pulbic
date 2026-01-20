import time
import logging
import json
import os
from src.api.polymarket import PolymarketAPI
from src.utils.config_loader import ConfigLoader
from src.strategies.simple_strategy import SimpleStrategy
from src.utils.orderbook_manager import OrderBookManager
from src.utils.market_resolver import MarketResolver

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

def load_wallets_from_env():
    wallets = {}
    
    # 1. Reload env to ensure fresh keys are loaded
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    # 2. Scan environ for WALLET_{LABEL}_PRIVATE_KEY
    for key, val in os.environ.items():
        if key.startswith("WALLET_") and key.endswith("_PRIVATE_KEY"):
            # Extract Label: WALLET_MAIN_PRIVATE_KEY -> MAIN
            parts = key.split("_")
            # parts[0] = WALLET, parts[-1] = KEY, parts[-2] = PRIVATE
            # Label is everything in between
            if len(parts) >= 4:
                label = "_".join(parts[1:-2]).lower() # internal label use lower case
                prefix = "_".join(parts[:-2]) # WALLET_MAIN
                
                wallets[label] = {
                    "private_key": val,
                    "funder": os.environ.get(f"{prefix}_FUNDER"),
                    "api_key": os.environ.get(f"{prefix}_API_KEY"),
                    "api_secret": os.environ.get(f"{prefix}_API_SECRET"),
                    "api_passphrase": os.environ.get(f"{prefix}_API_PASSPHRASE"),
                    "signature_type": int(os.environ.get(f"{prefix}_SIGNATURE_TYPE", 2))
                }
    return wallets

def main():
    try:
        loader = ConfigLoader()
        markets = loader._config.get("markets", [])
        trading_config = loader.get_trading_config()
        
        # Load all wallets from ENV
        wallets_data = load_wallets_from_env()
        
        if not wallets_data:
            logger.warning("No wallets found in environment variables. Please run scripts/setup_api_keys.py.")
            # Don't return, keep running just in case hot-reload works or user fixes it
        
        # Initialize Resolver
        resolver = MarketResolver()

        # Initialize API instances
        api_instances = {} 
        ob_managers = {} 

        for label, w in wallets_data.items():
            try:
                # Skip incomplete wallets
                if not w["private_key"] or not w["funder"]:
                    continue
                    
                api = PolymarketAPI(
                    private_key=w.get("private_key"),
                    funder=w.get("funder"),
                    api_key=w.get("api_key"),
                    api_secret=w.get("api_secret"),
                    api_passphrase=w.get("api_passphrase"),
                    signature_type=w.get("signature_type", 2)
                )
                api_instances[label] = api
                ob_managers[label] = OrderBookManager(api)
            except Exception as e:
                logger.error(f"Failed to initialize wallet '{label}': {e}")

        # Initialize strategies
        active_strategies = []
        for m in markets:
            # Resolve Token ID if missing
            if not m.get("token_id") and m.get("keyword"):
                resolved_id = resolver.resolve_token_id(m.get("keyword"))
                if resolved_id:
                    m["token_id"] = resolved_id
                else:
                    logger.error(f"Could not resolve market for keyword: {m.get('keyword')}")
                    continue

            if not m.get("token_id"):
                 logger.error(f"Market config missing 'token_id' or valid 'keyword': {m}")
                 continue

            strat_name = m.get("strategy")
            wallet_label = m.get("wallet_label", "main")
            
            if wallet_label not in api_instances:
                logger.error(f"Wallet '{wallet_label}' not found for market {m.get('description')}. Skipping.")
                continue
                
            api = api_instances[wallet_label]
            ob_manager = ob_managers[wallet_label]
            strat_cls = STRATEGY_MAP.get(strat_name)
            
            if strat_cls:
                strategy_instance = strat_cls(m.get("strategy_config", {}))
                active_strategies.append({
                    "market": m,
                    "strategy": strategy_instance,
                    "api": api,
                    "ob_manager": ob_manager,
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
                ob_manager = item["ob_manager"]
                
                token_id = market["token_id"]
                binance_symbol = market.get("binance_symbol") # e.g. "BTC/USDT"
                
                if token_id == "REPLACE_WITH_TOKEN_ID":
                    continue

                try:
                    # 1. Fetch Combined Data (Orderbooks from both)
                    market_data = ob_manager.get_combined_data(token_id, binance_symbol)
                    market_data["token_id"] = token_id
                    
                    # 2. Extract Polymarket Price from Orderbook (Best Ask)
                    current_price = 0.0
                    poly_ob = market_data.get("polymarket")
                    
                    # Polymarket OB structure checking
                    # It typically has 'asks' and 'bids'. Asks are sorted ascending (lowest price first).
                    if poly_ob:
                        # Access 'asks' safely whether it's an object or dict
                        asks = getattr(poly_ob, 'asks', []) or poly_ob.get('asks', [])
                        
                        if asks and len(asks) > 0:
                            best_ask = asks[0]
                            # Handle different formats: object with .price or list/tuple [price, size]
                            try:
                                if hasattr(best_ask, 'price'):
                                    current_price = float(best_ask.price)
                                elif isinstance(best_ask, (list, tuple)):
                                    current_price = float(best_ask[0])
                                elif isinstance(best_ask, dict):
                                    current_price = float(best_ask.get('price', 0))
                                else:
                                    current_price = float(best_ask) # Direct string/float
                            except ValueError:
                                current_price = 0.0

                    market_data["price"] = current_price

                    # 3. Strategy Execution
                    if strategy.should_enter(market_data):
                        logger.info(f"Signal detected for {token_id} at {current_price} (Wallet: {item['wallet_label']})")
                        
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
