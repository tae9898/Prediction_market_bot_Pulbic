# Polymarket Trading Bot (Private Strategy)

**WARNING: THIS REPOSITORY CONTAINS PRIVATE TRADING STRATEGIES.**
Do not publish this repository publicly without removing sensitive strategy files located in `src/strategies/`.

## Architecture

- **API Layer**: Modularized API wrappers (Polymarket currently).
- **Strategy Layer**: Private logic for order triggering.
- **Processes**:
  - `trader.py`: Monitors market and executes orders based on strategy.
  - `redeemer.py`: Automatically redeems positions at set intervals.

## Setup

1. Copy `.env.example` to `.env` and fill in secrets.
2. Adjust `config.json` for trading parameters.
3. Install dependencies: `pip install -r requirements.txt`

## License

Private / Proprietary.