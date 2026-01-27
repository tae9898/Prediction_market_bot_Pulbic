<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# models

## Purpose
Mathematical models for probability calculations, portfolio management, and PnL tracking. These models provide the analytical foundation for trading decisions.

## Key Files

| File | Description |
|------|-------------|
| `probability.py` | Black-Scholes option pricing and probability calculations |
| `portfolio_manager.py` | Portfolio state tracking and position management |
| `pnl_database.py` | SQLite database for trade history and PnL persistence |
| `__init__.py` | Python package initializer |

## For AI Agents

### Working In This Directory
- Models should be pure functions (no side effects) where possible
- All probability calculations must be deterministic
- Database operations must be atomic (use transactions)
- Validate all inputs before calculations

### Probability Model

**Purpose**: Calculate fair values and implied probabilities for binary options

```python
from models.probability import (
    calculate_fair_probability,
    black_scholes_call,
    implied_probability_from_price,
    calculate_implied_volatility
)

# Calculate fair probability from market prices
fair_prob = calculate_fair_probability(
    bid_price=0.65,
    ask_price=0.67,
    time_to_expiry=86400  # seconds
)
# Returns: 0.66 (midpoint with adjustments)

# Black-Scholes option pricing
option_price = black_scholes_call(
    underlying_price=51234.50,
    strike_price=50000,
    time_to_expiry=86400,  # 1 day in seconds
    volatility=0.5,
    risk_free_rate=0.05
)
# Returns: 1456.78 (option premium in USDC)

# Implied probability from market price
market_price = 0.65  # YES token price
implied_prob = implied_probability_from_price(market_price)
# Returns: 0.65 (for linear binary options)

# Calculate implied volatility from market prices
iv = calculate_implied_volatility(
    market_price=0.65,
    underlying_price=51234.50,
    strike_price=50000,
    time_to_expiry=86400,
    risk_free_rate=0.05
)
# Returns: 0.48 (48% annualized volatility)
```

**Black-Scholes Formula**:
```python
def black_scholes_call(S, K, T, sigma, r):
    """
    S: Underlying price
    K: Strike price
    T: Time to expiry (years)
    sigma: Volatility
    r: Risk-free rate

    d1 = (ln(S/K) + (r + sigma^2/2)T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    Call = S * N(d1) - K * e^(-rT) * N(d2)
    """
    from scipy.stats import norm
    import numpy as np

    d1 = (np.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return call_price
```

### Portfolio Manager

**Purpose**: Track portfolio state, positions, and performance metrics

```python
from models.portfolio_manager import (
    PortfolioManager,
    Position,
    Trade
)

# Initialize portfolio manager
pm = PortfolioManager(wallet_id="wallet_0")

# Add a position
position = Position(
    token_id="12345",
    market_id="BTC > $50k",
    side="YES",
    entry_price=0.65,
    size=100,
    entry_time=datetime.now()
)
pm.add_position(position)

# Update position (partial fill)
pm.update_position(
    token_id="12345",
    filled_size=50,
    avg_fill_price=0.66
)

# Close position
pm.close_position(
    token_id="12345",
    exit_price=0.70,
    exit_time=datetime.now()
)

# Get portfolio state
state = pm.get_state()
# {
#     "total_value": 10500.00,
#     "unrealized_pnl": 500.00,
#     "realized_pnl": 1234.56,
#     "open_positions": 3,
#     "cash_balance": 8500.00
# }

# Get performance metrics
metrics = pm.get_performance_metrics(days=7)
# {
#     "total_trades": 25,
#     "win_rate": 0.68,
#     "avg_profit": 45.67,
#     "avg_loss": -23.45,
#     "sharpe_ratio": 1.45,
#     "max_drawdown": -234.56
# }
```

**Position Dataclass**:
```python
@dataclass
class Position:
    token_id: str
    market_id: str
    side: str  # "YES" or "NO"
    entry_price: float
    size: float
    entry_time: datetime
    filled_size: float = 0.0
    avg_fill_price: float = 0.0
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    status: str = "OPEN"  # OPEN, CLOSED

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL"""
        if self.side == "YES":
            return (current_price - self.avg_fill_price) * self.filled_size
        else:
            return (self.avg_fill_price - current_price) * self.filled_size

    def realized_pnl(self) -> float:
        """Calculate realized PnL"""
        if self.status != "CLOSED":
            return 0.0
        if self.side == "YES":
            return (self.exit_price - self.avg_fill_price) * self.filled_size
        else:
            return (self.avg_fill_price - self.exit_price) * self.filled_size
```

### PnL Database

**Purpose**: Persistent storage for trade history and PnL calculations

```python
from models.pnl_database import (
    log_trade,
    get_pnl_history,
    get_strategy_performance,
    get_daily_summary
)

# Log a trade
log_trade(
    wallet_id="wallet_0",
    strategy="arbitrage",
    token_id="12345",
    side="BUY",
    size=100,
    price=0.65,
    trade_id="trade_abc123",
    timestamp=datetime.now()
)

# Get PnL history
history = get_pnl_history(
    wallet_id="wallet_0",
    days=7,
    granularity="hour"  # hour, day
)
# Returns DataFrame with columns: timestamp, realized_pnl, unrealized_pnl, total_value

# Get strategy performance
performance = get_strategy_performance(
    wallet_id="wallet_0",
    strategy="arbitrage"
)
# {
#     "total_trades": 45,
#     "winning_trades": 32,
#     "losing_trades": 13,
#     "win_rate": 0.71,
#     "total_pnl": 1234.56,
#     "avg_profit_per_trade": 27.43,
#     "max_profit": 156.78,
#     "max_loss": -45.67
# }

# Get daily summary
summary = get_daily_summary(wallet_id="wallet_0", days=30)
# Returns DataFrame with daily PnL, trades, and performance metrics
```

**Database Schema**:
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    token_id TEXT NOT NULL,
    side TEXT NOT NULL,
    size REAL NOT NULL,
    price REAL NOT NULL,
    trade_id TEXT UNIQUE,
    timestamp DATETIME NOT NULL,
    INDEX idx_wallet_timestamp (wallet_id, timestamp),
    INDEX idx_strategy (strategy)
);

CREATE TABLE portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    total_value REAL,
    unrealized_pnl REAL,
    realized_pnl REAL,
    cash_balance REAL,
    open_positions INTEGER,
    INDEX idx_wallet_timestamp (wallet_id, timestamp)
);
```

## Common Patterns

### Fair Value Calculation

```python
from models.probability import ProbabilityModel

model = ProbabilityModel(
    volatility=0.5,  # 50% annual volatility
    risk_free_rate=0.05
)

# Calculate fair value for YES token
btc_price = 51234.50
strike_price = 50000
time_to_expiry = 86400  # 1 day

fair_value = model.fair_value_call(
    underlying=btc_price,
    strike=strike_price,
    time_to_expiry=time_to_expiry
)

# Adjust for transaction costs
transaction_cost = 0.02  # 2%
adjusted_fair_value = fair_value * (1 - transaction_cost)
```

### Portfolio Rebalancing

```python
def check_rebalance_needed(pm: PortfolioManager) -> bool:
    """Check if portfolio needs rebalancing"""
    state = pm.get_state()

    # Check position concentration
    for position in pm.get_open_positions():
        position_value = position.size * position.avg_fill_price
        portfolio_share = position_value / state["total_value"]

        if portfolio_share > 0.2:  # 20% threshold
            logger.warning(f"Position {position.token_id} exceeds 20% of portfolio")
            return True

    return False
```

### Performance Analytics

```python
import pandas as pd

def calculate_sharpe_ratio(pnl_series: pd.Series, risk_free_rate: float = 0.05) -> float:
    """Calculate Sharpe ratio for PnL series"""
    returns = pnl_series.pct_change().dropna()

    excess_returns = returns - risk_free_rate / 252  # Daily
    sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)

    return sharpe

def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Calculate maximum drawdown"""
    rolling_max = equity_curve.expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return drawdown.min()
```

## Dependencies

### Internal
- `feature_source/config.py` - Model parameters
- `feature_source/logger.py` - Calculation logging

### External
- `scipy` - Statistical functions (norm, cdf)
- `numpy` - Numerical computations
- `pandas` - Data analysis and time series
- `sqlite3` - Database operations

## Mathematical Concepts

### Black-Scholes for Binary Options

For a binary option that pays $1 if condition is met:

```
Price = e^(-rT) * N(d2)

Where:
- r = Risk-free rate
- T = Time to expiry
- N() = Cumulative normal distribution
- d2 = (ln(S/K) + (r - σ²/2)T) / (σ√T)
```

### Implied Probability

For linear binary options (0-100):

```
Implied_Prob = Price / 100

For options priced 0-1:
Implied_Prob = Price
```

### Expected Value

```
EV = (Prob_Win × Profit) - (Prob_Loss × Loss)

Trade if EV > Transaction_Costs
```

<!-- MANUAL: -->
