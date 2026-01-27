<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# src/processes - Main Entry Points

## OVERVIEW
Core processes: trader.py (active trading loop) and redeemer.py (position redemption), launched by start.sh.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Main trading loop | trader.py | Strategy execution, order placement |
| Market monitoring | trader.py | Fetches orderbooks, executes strategies |
| Position redemption | redeemer.py | CTF operations for resolved markets |
| Strategy registration | trader.py:STRATEGY_MAP | Add new strategies here |
| Wallet loading | trader.py:load_wallets_from_env() | Scans WALLET_{LABEL}_* env vars |
| Market resolution | trader.py uses MarketResolver | Convert keywords to token_ids |

## CONVENTIONS
- **Entry points**: All run via `python -m src.processes.X` from start.sh
- **STRATEGY_MAP**: Dict mapping name → class, auto-registers strategies
- **Wallets**: Loaded from env vars with pattern `WALLET_{LABEL}_*`
- **Market resolution**: Missing token_id → resolve via keyword using MarketResolver
- **Dual process**: trader (foreground) + redeemer (background) run concurrently

## ANTI-PATTERNS
- **Don't** hardcode wallet credentials (always use env vars)
- **Don't** skip wallet validation (check private_key + funder exist)
- **Don't** forget to register new strategies in STRATEGY_MAP
