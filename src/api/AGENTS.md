<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# src/api - Exchange API Wrappers

## OVERVIEW
API wrappers for Polymarket CLOB (py_clob_client) and Binance (ccxt) used by trader process.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add Polymarket operation | polymarket.py | Follow existing methods pattern |
| Add Binance endpoint | binance.py | Use ccxt client methods |
| API initialization | trader.py | PolymarketAPI takes private_key, funder, creds |

## CONVENTIONS
- **PolymarketAPI**: Wraps py_clob_client.client.ClobClient
- **BinanceAPI**: Wraps ccxt.binance (public read-only)
- **Signature types**: 0=EOA, 1=Gnosis Safe, 2=Proxy (default)
- **Error handling**: All methods log errors and re-raise exceptions
- **Order args**: Use py_clob_client.clob_types.OrderArgs for orders

## ANTI-PATTERNS
- **Don't** create multiple BinanceAPI instances (use ccxt rate limiting)
- **Don't** use Binance for trading (read-only price reference only)
