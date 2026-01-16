# Polymarket Trading Bot (Multi-Wallet Support)

**WARNING: THIS REPOSITORY CONTAINS PRIVATE TRADING STRATEGIES.**
Do not publish this repository publicly without removing sensitive strategy files located in `src/strategies/`.

## Architecture

- **Multi-Wallet**: Supports trading with multiple wallets simultaneously via `wallets.json`.
- **API Layer**: Modularized API wrappers for Polymarket CLOB.
- **Strategy Layer**: Private logic for order triggering.
- **Processes**:
  - `trader.py`: Monitors market and executes orders based on strategy.
  - `redeemer.py`: Automatically redeems positions (Requires Web3 implementation).

## Setup

1. **Environment Setup**:
   Copy `.env.example` to `.env`.
   ```bash
   cp .env.example .env
   ```

2. **Add Wallets**:
   Run the setup script to add one or more wallets. This will generate API keys and store them in `wallets.json` (gitignored).
   ```bash
   ./.venv/bin/python -m scripts.setup_api_keys
   ```
   *You can run this multiple times to add multiple wallets with unique labels (e.g., "main", "proxy1").*

3. **Configure Trading**:
   Edit `config.json` to define markets and strategies. **Assign a `wallet_label` to each market.**
   ```json
   {
       "markets": [
           {
               "token_id": "...",
               "wallet_label": "main",
               "strategy": "simple",
               ...
           }
       ]
   }
   ```

4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Start the bot using the helper script:
```bash
./start.sh
```

## License

Private / Proprietary.
