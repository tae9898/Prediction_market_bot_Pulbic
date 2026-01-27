<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# models

## Purpose
Mathematical models and analytical tools supporting trading decisions. This directory currently serves as a reference; active implementations are in `feature_source/models/`.

## Key Files

**Note**: This directory is currently empty or minimal. The actual model implementations are in:
- `feature_source/models/probability.py` - Probability calculations using Black-Scholes
- `feature_source/models/portfolio_manager.py` - Portfolio tracking and state management
- `feature_source/models/pnl_database.py` - PnL database with SQLite backend

## For AI Agents

### Working In This Directory
⚠️ **WARNING**: This directory is a stub/reference only.
- All active model development happens in `feature_source/models/`
- Do not create new files here unless restructuring the project
- Import models from `feature_source.models` instead

### Model Implementations (in feature_source/models/)

#### Probability Model
**File**: `feature_source/models/probability.py`

**Purpose**: Calculate fair probabilities and option pricing using Black-Scholes model

**Key Functions**:
- `calculate_fair_probability()` - Convert market price to implied probability
- `black_scholes()` - Option pricing with volatility and time decay
- `implied_volatility()` - Calculate volatility from market prices

**Usage**:
```python
from models.probability import calculate_fair_probability

# Calculate fair value
fair_prob = calculate_fair_probability(
    bid=0.65,
    ask=0.67,
    time_to_expiry=3600  # seconds
)
```

#### Portfolio Manager
**File**: `feature_source/models/portfolio_manager.py`

**Purpose**: Track portfolio state, positions, and PnL across multiple wallets

**Key Classes**:
- `PortfolioState` - Dataclass for portfolio snapshot
- `Position` - Individual position tracking
- `Trade` - Trade history record

**Usage**:
```python
from models.portfolio_manager import PortfolioManager

pm = PortfolioManager(wallet_id="wallet_0")
pm.add_position(token_id, side, size, entry_price)
current_pnl = pm.calculate_pnl()
```

#### PnL Database
**File**: `feature_source/models/pnl_database.py`

**Purpose**: Persistent storage for trade history and PnL calculations

**Key Functions**:
- `log_trade()` - Record trade to database
- `get_pnl_history()` - Retrieve historical PnL
- `get_strategy_performance()` - Per-strategy statistics

**Usage**:
```python
from models.pnl_database import log_trade, get_pnl_history

# Log a trade
log_trade(
    wallet_id="wallet_0",
    strategy="arbitrage",
    token_id="12345",
    side="BUY",
    size=10,
    price=0.65
)

# Get history
history = get_pnl_history(wallet_id="wallet_0", days=7)
```

## Mathematical Concepts

### Black-Scholes Model
Used for pricing binary options on Polymarket:

```
C = S * N(d1) - K * e^(-rT) * N(d2)

Where:
- C = Call option price
- S = Current price of underlying
- K = Strike price
- r = Risk-free rate
- T = Time to expiry
- N() = Cumulative normal distribution
```

### Implied Probability
For binary options (YES/NO):
```
Implied_Prob = YES_Price / (YES_Price + NO_Price)

Fair_Value = Implied_Prob - Transaction_Costs
```

### Expected Value
```
EV = (Prob_Win * Profit) - (Prob_Loss * Loss)

Trade if EV > Threshold
```

## Dependencies

### Internal
- `feature_source/models/` - Active implementations
- `feature_source/config.py` - Configuration parameters

### External
- `scipy` - Statistical functions (norm, cdf)
- `numpy` - Numerical computations
- `sqlite3` - Database operations
- `pandas` - Data analysis

## Data Flow

```
┌──────────────────┐
│ Market Data      │
│ (prices, orderbook)│
└────────┬─────────┘
         │
    ┌────▼────────────┐
    │ Probability     │
    │ Model           │
    └────┬────────────┘
         │
    ┌────▼────────────┐
    │ Trading         │
    │ Decision        │
    └────┬────────────┘
         │
    ┌────▼────────────┐
    │ Portfolio       │
    │ Manager         │
    └────┬────────────┘
         │
    ┌────▼────────────┐
    │ PnL Database    │
    └─────────────────┘
```

## Common Patterns

### Fair Value Calculation
```python
from models.probability import ProbabilityModel

model = ProbabilityModel(volatility=0.3, risk_free_rate=0.05)

# Calculate fair value for option
fair_price = model.calculate_fair_value(
    current_price=50000,
    strike_price=55000,
    time_to_expiry=86400  # 1 day in seconds
)
```

### Portfolio Snapshot
```python
from models.portfolio_manager import PortfolioManager

pm = PortfolioManager(wallet_id="wallet_0")

# Get current state
snapshot = {
    "total_value": pm.get_total_value(),
    "unrealized_pnl": pm.get_unrealized_pnl(),
    "realized_pnl": pm.get_realized_pnl(),
    "positions": pm.get_all_positions(),
    "timestamp": datetime.now()
}
```

<!-- MANUAL: -->
