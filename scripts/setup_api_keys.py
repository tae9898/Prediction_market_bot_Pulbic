import os
import sys
from py_clob_client.client import ClobClient
from dotenv import load_dotenv, set_key

ENV_FILE = ".env"

def setup_keys():
    load_dotenv(ENV_FILE)
    
    print("--- Add New Wallet to .env ---")
    label = input("Enter a label for this wallet (e.g., 'MAIN', 'PROXY1'): ").strip().upper()
    if not label:
        print("Label cannot be empty.")
        return

    # Check for existing
    prefix = f"WALLET_{label}_"
    if os.getenv(f"{prefix}PRIVATE_KEY"):
        print(f"Warning: Wallet '{label}' already exists in .env.")
        confirm = input("Overwrite? (y/n): ").lower()
        if confirm != 'y':
            return

    private_key = input("Enter Private Key: ").strip()
    funder = input("Enter Funder Address (Proxy Address): ").strip()
    
    if not private_key or not funder:
        print("Error: Key and Funder Address are required.")
        return

    host = os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com")
    chain_id = int(os.getenv("CHAIN_ID", 137))
    signature_type = int(os.getenv("SIGNATURE_TYPE", 2)) 

    print(f"Initializing client for {funder}...")
    
    try:
        # Client for API Key derivation
        client = ClobClient(
            host=host,
            key=private_key,
            chain_id=chain_id,
            signature_type=signature_type,
            funder=funder
        )

        print("Creating or Deriving API Key...")
        creds = client.create_or_derive_api_creds()
        
        print("\nAPI Key retrieved successfully!")
        
        # Save to .env using set_key (appends or updates)
        # Ensure .env exists
        if not os.path.exists(ENV_FILE):
            with open(ENV_FILE, 'w') as f: f.write("")

        set_key(ENV_FILE, f"{prefix}PRIVATE_KEY", private_key)
        set_key(ENV_FILE, f"{prefix}FUNDER", funder)
        set_key(ENV_FILE, f"{prefix}API_KEY", creds.api_key)
        set_key(ENV_FILE, f"{prefix}API_SECRET", creds.api_secret)
        set_key(ENV_FILE, f"{prefix}API_PASSPHRASE", creds.api_passphrase)
        set_key(ENV_FILE, f"{prefix}SIGNATURE_TYPE", str(signature_type))
        
        print(f"\nSUCCESS: Wallet '{label}' saved to .env with prefix {prefix}")

    except Exception as e:
        print(f"Error creating API Key: {e}")

if __name__ == "__main__":
    setup_keys()
