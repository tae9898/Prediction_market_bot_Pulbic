# 🤖 AGENTS.md - Agentic Coding Guide

## Build / Test Commands

```bash
# Install dependencies (uv creates virtualenv automatically)
uv pip install -r requirements.txt

# Run bot (CLI + Web Dashboard)
uv run main.py

# Run bot - Web Dashboard only
uv run main.py --web-only

# Run bot on custom port
uv run main.py --port 3001

# Build Web Dashboard (React)
cd web && npm install && npm run build

# Note: No unit tests currently exist. Tests should be added with pytest framework.
# Run single test (when tests exist):
# uv run pytest tests/test_module.py -k test_specific_function -v
```

---

## Code Style Guidelines

### Imports

**Order**: Standard library → Third-party → Local modules

```python
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable

from dotenv import load_dotenv
from scipy.stats import norm

from config import Config
from exchanges.binance import BinanceFeed
```

**Type hints**: Required for all function signatures. Use `typing` module:
- `Optional[Type]`, `List[Type]`, `Dict[KeyType, ValueType]`
- `Tuple[Type1, Type2, ...]`
- `Callable[[ArgTypes], ReturnType]`

### File & Class Naming

- **Files**: `snake_case.py` (e.g., `trading_engine.py`, `edge_hedge.py`)
- **Classes**: `PascalCase` (e.g., `TradingEngine`, `EdgeHedgeStrategy`, `Config`)
- **Functions**: `snake_case` (e.g., `analyze_entry`, `calculate_fair_probability`)

**Strategy naming convention**:
- `trend.py` → `TrendStrategy` (Directional + Contrarian unified)
- `edge_hedge.py` → `EdgeHedgeStrategy`
- `arbitrage.py` → `SurebetEngine`
- `expiry_sniper.py` → `ExpirySniperStrategy`

### Dataclasses

Use `@dataclass` for configuration and state management:

```python
@dataclass
class StrategyConfig:
    enabled: bool = True
    min_edge_pct: float = 10.0
    profit_hedge_threshold_pct: float = 7.0

@dataclass
class BotState:
    assets: Dict[str, AssetState] = field(default_factory=dict)
    auto_trade: bool = False
    logs: List[str] = field(default_factory=list)
```

### Docstrings

**Language**: Korean (this codebase uses Korean documentation)

```python
def analyze_entry(self, asset_type: str, fair_up: float) -> Optional[Dict]:
    """
    진입 기회 분석

    Returns:
        None: 진입 기회 없음
        Dict: {"direction": "UP" or "DOWN", "edge": edge 값}
    """
```

### Error Handling

**Pattern**: Try/except in async loops with logging:

```python
async def trading_loop(self) -> None:
    while self._running:
        try:
            # Trading logic here
            pass
        except Exception as e:
            self.add_log(f"Trading loop error: {e}")
            await asyncio.sleep(5)  # Delay before retry
```

**Never**: Use empty catch blocks (`except: pass`) or suppress exceptions.

### Logging

Use custom logger with callbacks (defined in `logger.py`):

```python
self.logger = get_logger(self.bot_id)

# Log types: "debug" (default), "error", "pnl"
self.add_log("Trading signal detected", log_type="debug")
self.add_log("Critical error occurred", log_type="error")
self.add_log("Position closed with profit", log_type="pnl")
```

### Async/Await

All I/O operations should be async. Use `asyncio` properly:

```python
async def initialize(self) -> bool:
    for asset in self.enabled_assets:
        pm = self.polymarkets[asset]
        if not await pm.initialize():
            self.add_log(f"❌ {asset} Init Failed")
            return False
    return True
```

### Type Safety

**Never**: Use type suppression (`as any`, `@type: ignore`, etc.)

**Always**: Properly type function returns and arguments:
- `def calculate(self, price: float) -> Optional[Dict]:`
- `async def buy(self, direction: str, size: float) -> bool:`

### Configuration Pattern

Use `Config` class with `.env` and `config.json`:

```python
from config import get_config

config = get_config(suffix="")  # Base config
config_1 = get_config(suffix="1")  # Wallet 1 specific

# Inheritance: Identity fields (private_key, proxy_address) NEVER inherit
# Trading parameters (bet_amount_usdc, edge_threshold_pct) DO inherit
```

### Testing (When Added)

Tests should use `pytest`:
```bash
pytest tests/ -v                    # Run all tests
pytest tests/test_edge_hedge.py     # Run single file
pytest tests/test_edge_hedge.py -k test_analyze_entry -v  # Run specific test
```

---

## Project Structure

```
Polymarket_bot/
├── main.py                    # Entry point (CLI + Web)
├── bot_core.py                # Core trading engine
├── config.py                  # Config management
├── logger.py                  # Logging system
├── strategies/                # Trading strategies
│   ├── trend.py             # Trend (Directional + Contrarian)
│   ├── edge_hedge.py         # Edge Hedge
│   ├── arbitrage.py           # Sure-Bet
│   └── expiry_sniper.py      # Expiry Sniper
├── models/                    # Data models
│   ├── probability.py         # Black-Scholes model
│   └── portfolio_manager.py  # Portfolio tracking
├── exchanges/                 # Exchange adapters
│   ├── binance.py            # Binance price feed
│   └── polymarket.py         # Polymarket CLOB
└── web/                       # React dashboard
```

---

## Key Constraints

- **Python 3.10+** required (uses `|` union operator in type hints)
- **No type suppression** (`as any`, `@type: ignore`, etc.)
- **No empty catch blocks** - log all exceptions
- **Korean documentation** for docstrings and comments
- **Async/await** for all I/O operations
- **Type hints required** on all public functions
