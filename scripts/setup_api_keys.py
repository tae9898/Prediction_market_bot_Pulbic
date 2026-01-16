import os
import json
from py_clob_client.client import ClobClient
from dotenv import load_dotenv

WALLETS_FILE = "wallets.json"

def load_wallets():
    if os.path.exists(WALLETS_FILE):
        with open(WALLETS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_wallets(wallets):
    with open(WALLETS_FILE, 'w') as f:
        json.dump(wallets, f, indent=4)
    print(f"Updated {WALLETS_FILE}")

def setup_keys():
    load_dotenv()
    
    print("--- Add New Wallet ---")
    label = input("Enter a label for this wallet (e.g., 'main', 'proxy1'): ").strip()
    if not label:
        print("Label cannot be empty.")
        return

    wallets = load_wallets()
    if label in wallets:
        overwrite = input(f"Wallet '{label}' already exists. Overwrite? (y/n): ").lower()
        if overwrite != 'y':
            return

    private_key = input("Enter Private Key: ").strip()
    funder = input("Enter Funder Address (Proxy Address): ").strip()
    
    if not private_key or not funder:
        print("Error: Key and Funder Address are required.")
        return

    host = os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com")
    chain_id = int(os.getenv("CHAIN_ID", 137))
    signature_type = int(os.getenv("SIGNATURE_TYPE", 2)) # Default to Proxy

    print(f"Initializing client for {funder}...")
    
    try:
        # Temporary client to create keys
        client = ClobClient(
            host=host,
            key=private_key,
            chain_id=chain_id,
            signature_type=signature_type,
            funder=funder
        )

        print("Creating or Deriving API Key on Polymarket...")
        # create_or_derive_api_creds handles both creation and existing keys
        creds = client.create_or_derive_api_creds()
        
        print("\nAPI Key retrieved successfully!")
        
        wallet_data = {
            "private_key": private_key,
            "funder": funder,
            "api_key": creds.api_key,
            "api_secret": creds.api_secret,
            "api_passphrase": creds.api_passphrase,
            "signature_type": signature_type
        }
        
        wallets[label] = wallet_data
        save_wallets(wallets)
        
        print(f"\nSUCCESS: Wallet '{label}' added to {WALLETS_FILE}.")

    except Exception as e:
        print(f"Error creating API Key: {e}")

if __name__ == "__main__":
    setup_keys()