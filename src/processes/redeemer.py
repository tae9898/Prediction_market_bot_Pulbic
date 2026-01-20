import time
import logging
import os
import requests
from dotenv import load_dotenv
from src.utils.ctf_handler import CTFHandler
from src.utils.logger import setup_logger

# Setup Logging with rotation
logger = setup_logger("Redeemer", "redeemer.log")

DATA_API = "https://data-api.polymarket.com/positions"

def load_wallets_from_env():
    wallets = []
    load_dotenv(override=True)
    
    for key, val in os.environ.items():
        if key.startswith("WALLET_") and key.endswith("_PRIVATE_KEY"):
            parts = key.split("_")
            if len(parts) >= 4:
                prefix = "_".join(parts[:-2])
                funder = os.environ.get(f"{prefix}_FUNDER")
                if funder:
                    wallets.append({
                        "private_key": val,
                        "funder": funder,
                        "label": "_".join(parts[1:-2])
                    })
    return wallets

def main():
    logger.info("Redeemer Process Started.")
    
    while True:
        try:
            wallets = load_wallets_from_env()
            if not wallets:
                logger.warning("No wallets found. Sleeping...")
                time.sleep(300)
                continue

            for w in wallets:
                label = w["label"]
                funder = w["funder"]
                pk = w["private_key"]
                
                logger.info(f"Scanning wallet '{label}' ({funder})...")
                
                try:
                    # 1. Fetch Positions from Data API
                    resp = requests.get(DATA_API, params={"user": funder, "limit": 500})
                    if resp.status_code != 200:
                        logger.error(f"Failed to fetch positions for {label}: {resp.status_code}")
                        continue
                    
                    positions = resp.json()
                    if not positions:
                        continue
                        
                    # 2. Group positions by conditionId to find mergeable pairs
                    pos_by_cond = {}
                    ctf = CTFHandler(pk, proxy_address=funder)
                    
                    for pos in positions:
                        cond_id = pos.get("conditionId")
                        if not cond_id: continue
                        
                        if cond_id not in pos_by_cond:
                            pos_by_cond[cond_id] = []
                        pos_by_cond[cond_id].append(pos)
                        
                    # 3. Process each conditionId
                    for cond_id, p_list in pos_by_cond.items():
                        # A. Check for Merge (If we have multiple outcomes for the same market)
                        if len(p_list) > 1:
                            # Calculate min size across all outcomes to merge
                            sizes = [float(p.get("size", 0)) for p in p_list]
                            min_size = min(sizes)
                            
                            if min_size > 0.1: # Dust threshold
                                logger.info(f"Detected mergeable positions for {label} (Cond: {cond_id[:10]}..., Size: {min_size})")
                                if ctf.merge_positions(cond_id, min_size):
                                    logger.info(f"Merge successful for {label}")
                                    time.sleep(5)
                        
                        # B. Check for Redeem (If market is resolved)
                        # We only need to check one position per condition to see if it's redeemable
                        if ctf.is_redeemable(cond_id):
                            total_size = sum(float(p.get("size", 0)) for p in p_list)
                            if total_size > 0.1:
                                logger.info(f"Found redeemable position for {label} (Cond: {cond_id[:10]}...)")
                                if ctf.redeem_positions(cond_id):
                                    logger.info(f"Redeem successful for {label}")
                                    time.sleep(5)
                        
                        time.sleep(0.1) # Rate limit check
                        
                except Exception as e:
                    logger.error(f"Error processing wallet {label}: {e}")

            logger.info("Cycle complete. Sleeping for 5 minutes...")
            time.sleep(300) # 5 minutes

        except Exception as e:
            logger.critical(f"Redeemer crashed: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
