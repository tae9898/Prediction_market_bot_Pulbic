<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# src/strategies - Trading Logic

## OVERVIEW
Strategy implementations: BaseStrategy (abstract) and concrete strategies like SimpleStrategy.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add new strategy | Create new file in strategies/ | Inherit from BaseStrategy |
| Strategy registration | ../processes/trader.py:STRATEGY_MAP | Add mapping name → class |
| Abstract methods | base.py | should_enter(), get_order_details() |

## CONVENTIONS
- **BaseStrategy**: Abstract class defining strategy interface
- **Methods**: Implement `should_enter(market_data)` and `get_order_details(market_data)`
- **requires_binance**: Override property to True if strategy needs Binance data
- **Config**: Strategy config passed in constructor from config.json
- **Registration**: Add to STRATEGY_MAP in trader.py for discovery

## ANTI-PATTERNS
- **Don't** forget to implement both abstract methods
- **Don't** create blocking I/O in should_enter() (should be fast)
- **Don't** skip STRATEGY_MAP registration (strategy won't load)
