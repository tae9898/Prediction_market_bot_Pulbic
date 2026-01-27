<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# strategies

## Purpose
Trading strategy implementations for Polymarket arbitrage and directional trading. This directory is a stub; active implementations are in `feature_source/strategies/`.

## Key Files

**Note**: This directory is currently empty. The actual strategy implementations are in:
- `feature_source/strategies/arbitrage.py` - Sure-bet arbitrage strategy
- `feature_source/strategies/edge_hedge.py` - Edge hedge with dynamic hedging
- `feature_source/strategies/expiry_sniper.py` - Expiry sniper strategy
- `feature_source/strategies/trend.py` - Trend following strategy

## For AI Agents

### Working In This Directory
⚠️ **WARNING**: This directory is a stub only.
- All active strategy development happens in `feature_source/strategies/`
- Do not create new files here
- Import strategies from `feature_source.strategies` instead

### Strategy Implementations (in feature_source/strategies/)

All strategies follow a common interface:

```python
class BaseStrategy:
    def __init__(self, config: StrategyConfig):
        self.config = config

    async def analyze(self, market_data: MarketData) -> Optional[TradeSignal]:
        """
        Analyze market and return trade signal if opportunity exists

        Returns:
            None: No trade opportunity
            TradeSignal: Dict with direction, size, price, etc.
        """
        pass

    async def execute(self, signal: TradeSignal) -> bool:
        """Execute the trade with proper error handling"""
        pass
```

### Available Strategies

#### 1. Arbitrage (Sure-bet)
**File**: `feature_source/strategies/arbitrage.py`

**Purpose**: Risk-free profit when YES + NO prices < 1.0

**Logic**:
```
Opportunity: YES_Price + NO_Price < 1.0
Profit: 1.0 - (YES_Price + NO_Price) - Transaction_Costs

Action:
- Buy both YES and NO
- Hold until expiry or price convergence
- Guaranteed profit regardless of outcome
```

**Parameters**:
- `min_profit_pct` - Minimum profit threshold (default: 2%)
- `max_position_size` - Maximum position per trade
- `transaction_cost_pct` - Estimated transaction costs

**Example**:
```python
YES_Price = 0.48
NO_Price = 0.50
Sum = 0.98
Profit = 1.0 - 0.98 = 0.02 (2%)

Action: Buy YES and NO, lock in 2% profit
```

#### 2. Edge Hedge
**File**: `feature_source/strategies/edge_hedge.py`

**Purpose**: Trade on mispricings between Polymarket and Binance implied prices

**Logic**:
```
1. Get Polymarket price (e.g., BTC > $50k)
2. Get Binance BTC price
3. Calculate Binance implied probability
4. Trade if spread > threshold

Hedge:
- Long Polymarket YES → Short Binance futures
- Long Polymarket NO → Long Binance futures
```

**Parameters**:
- `min_edge_pct` - Minimum edge to trade (default: 5%)
- `hedge_ratio` - Hedge ratio for Binance position
- `profit_hedge_threshold_pct` - Profit threshold to close hedge

**Example**:
```python
Polymarket YES_Price = 0.60
Binance Price = $52,000 (Implied YES = 0.65)
Edge = 0.65 - 0.60 = 5%

Action: Buy Polymarket YES, Short Binance futures
```

#### 3. Expiry Sniper
**File**: `feature_source/strategies/expiry_sniper.py`

**Purpose**: Capture value near market expiration when prices converge

**Logic**:
```
Condition: Time to expiry < 5 minutes
Opportunity: Mispriced options near expiry

Action:
- Buy underpriced options
- Hedge with Binance if directional exposure
- Hold until expiry for maximum profit
```

**Parameters**:
- `expiry_threshold_seconds` - Time before expiry to start (default: 300)
- `min_edge_pct` - Minimum edge to trade
- `max_spread_pct` - Maximum bid-ask spread to accept

**Example**:
```python
Market: BTC > $50k
Time to expiry: 2 minutes
YES_Price: 0.45
Fair Value: 0.52 (based on Binance $51,500)

Action: Buy YES at 0.45, hedge with short Binance futures
Expected Profit: 7%
```

#### 4. Trend Following
**File**: `feature_source/strategies/trend.py`

**Purpose**: Directional trading based on price trends and momentum

**Logic**:
```
1. Calculate trend indicators (MA, RSI, MACD)
2. Identify trend direction and strength
3. Enter trade in trend direction
4. Optional hedge to reduce risk
```

**Parameters**:
- `trend_period` - Period for trend calculation (default: 1 hour)
- `min_trend_strength` - Minimum trend strength to trade
- `use_hedge` - Whether to hedge with Binance

**Indicators**:
- Moving Average (SMA/EMA)
- Relative Strength Index (RSI)
- Momentum

**Example**:
```python
BTC Price: $50,000 → $51,000 → $52,000
Trend: Strong UP
RSI: 65 (Bullish but not overbought)

Action: Buy Polymarket YES for BTC > $50k
Optional Hedge: Short Binance futures to reduce risk
```

## Strategy Selection

### Market Conditions

| Condition | Best Strategy |
|-----------|---------------|
| YES + NO < 1.0 | Arbitrage (risk-free) |
| Polymarket ≠ Binance implied | Edge Hedge |
| Near expiry, mispriced | Expiry Sniper |
| Strong trend detected | Trend Following |

### Risk Profile

| Strategy | Risk Level | Hedge Required |
|----------|------------|----------------|
| Arbitrage | None (risk-free) | No |
| Edge Hedge | Low | Yes (Binance) |
| Expiry Sniper | Medium | Optional |
| Trend Following | High | Recommended |

## Dependencies

### Internal
- `feature_source/strategies/` - Active implementations
- `feature_source/models/probability.py` - Fair value calculations
- `feature_source/exchanges/` - Market data and execution

### External
- `pandas` - Data analysis for trend calculations
- `numpy` - Numerical computations
- `asyncio` - Async strategy execution

## Configuration

Strategies are configured in `config.json`:

```json
{
  "strategies": {
    "arbitrage": {
      "enabled": true,
      "min_profit_pct": 2.0,
      "max_position_size": 100
    },
    "edge_hedge": {
      "enabled": true,
      "min_edge_pct": 5.0,
      "hedge_ratio": 1.0
    },
    "expiry_sniper": {
      "enabled": true,
      "expiry_threshold_seconds": 300
    },
    "trend": {
      "enabled": false,
      "trend_period": 3600
    }
  }
}
```

## Performance Metrics

Each strategy tracks:
- **Total Trades**: Number of trades executed
- **Win Rate**: Percentage of profitable trades
- **Average Profit**: Mean profit per trade
- **Total PnL**: Cumulative profit/loss
- **Sharpe Ratio**: Risk-adjusted returns

<!-- MANUAL: -->
