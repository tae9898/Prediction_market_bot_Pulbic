"""
Polymarket API Key Generator (Batch)
.env 파일에 있는 모든 Private Key(기본 및 _1, _2...)를 찾아
API Key, Secret, Passphrase를 일괄 생성/조회합니다.
"""

import os
import sys
from dotenv import load_dotenv

try:
    from py_clob_client.client import ClobClient
except ImportError:
    print("❌ 'py-clob-client' 패키지가 필요합니다: pip install py-clob-client")
    sys.exit(1)

def get_creds(pk, label=""):
    try:
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=pk,
            chain_id=137
        )
        creds = client.create_or_derive_api_creds()
        return creds
    except Exception as e:
        print(f"❌ [{label}] 오류: {e}")
        return None

def main():
    load_dotenv()
    
    print("🔐 Polymarket API Key Batch Generator")
    print("-------------------------------------")
    
    keys_to_process = {}
    
    # 1. Base Key
    base_pk = os.getenv("PRIVATE_KEY")
    if base_pk:
        keys_to_process["(Base)"] = {"pk": base_pk, "suffix": ""}
        
    # 2. Suffixed Keys (Dynamic Scan)
    i = 1
    while True:
        suffix = f"_{i}"
        pk = os.getenv(f"PRIVATE_KEY{suffix}")
        if pk:
            keys_to_process[f"Wallet {i}"] = {"pk": pk, "suffix": suffix}
            i += 1
        else:
            # Stop if no consecutive key found
            # You can comment out 'break' if you have gaps (e.g. 1, 3) and want to scan more, 
            # but usually keys are sequential.
            break
            
    if not keys_to_process:
        print("ℹ️ .env 파일에서 PRIVATE_KEY를 찾을 수 없습니다.")
        manual_pk = input("👉 Private Key 직접 입력: ").strip()
        if manual_pk:
            keys_to_process["Manual"] = {"pk": manual_pk, "suffix": ""}
        else:
            return

    print(f"🔍 총 {len(keys_to_process)}개의 지갑을 발견했습니다.\n")

    for label, data in keys_to_process.items():
        pk = data["pk"]
        suffix = data["suffix"]
        
        print(f"Processing {label}...")
        creds = get_creds(pk, label)
        
        if creds:
            print(f"✅ Success! Copy below to .env:")
            print(f"POLYMARKET_API_KEY{suffix}={creds.api_key}")
            print(f"POLYMARKET_API_SECRET{suffix}={creds.api_secret}")
            print(f"POLYMARKET_PASSPHRASE{suffix}={creds.api_passphrase}")
            print("-" * 40)
        print("")

if __name__ == "__main__":
    main()