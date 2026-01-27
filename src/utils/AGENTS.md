<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# src/utils - Shared Utilities

## OVERVIEW
Utilities: config loading, logging with rotation, orderbook management, market resolution, CTF operations.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Load config | config_loader.py:ConfigLoader | Reads config.json, provides getters |
| Setup logging | logger.py:setup_logger | Rotating file handler (10MB, 5 backups) |
| Market resolution | market_resolver.py:MarketResolver | Keyword → token_id search |
| CTF operations | ctf_handler.py:CTFHandler | Merge/redeem, supports EOA + Gnosis Safe |
| Orderbook data | orderbook_manager.py:OrderBookManager | Combines poly + binance data |

## CONVENTIONS
- **ConfigLoader**: Load at module level via ConfigLoader()
- **Logging**: Use setup_logger(name, "logfile.log") - auto-creates logs/ dir
- **MarketResolver**: Search by keyword, returns best match token_id
- **CTFHandler**: Supports both EOA and Gnosis Safe proxy wallets
- **EIP-712**: CTFHandler signs Safe transactions via eth_account.sign_typed_data

## ANTI-PATTERNS
- **Don't** use basicConfig (use setup_logger for rotation)
- **Don't** hardcode paths (use ConfigLoader for config.json)
- **Don't** ignore proxy_address in CTFHandler (detects EOA vs Safe automatically)
