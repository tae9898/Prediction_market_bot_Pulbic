<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# strategies

## Purpose
Trading strategy implementations for Polymarket arbitrage and directional trading. All strategies implement a common interface for seamless integration with the trading bot.

## Key Files

| File | Description |
|------|-------------|
| `arbitrage.py` | Sure-bet arbitrage strategy (risk-free profit) |
| `edge_hedge.py` | Edge hedge strategy with Binance hedging |
| `expiry_sniper.py` | Expiry sniper for near-exploitation trades |
| `trend.py` | Trend following strategy (directional + contrarian) |
| `__init__.py` | Python package initializer |

## For AI Agents

### Working In This Directory
- All strategies must inherit from `BaseStrategy` class
- Implement `analyze()` and `execute()` methods
- Use Korean language for docstrings and comments
- Log all trading decisions with reasoning
- Validate all parameters before trading

### Strategy Interface

```python
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, config: StrategyConfig, polymarket, binance=None):
        self.config = config
        self.polymarket = polymarket
        self.binance = binance
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    async def analyze(self, market_data: MarketData) -> Optional[TradeSignal]:
        """
        시장 분석 및 진입 기회 탐색

        Returns:
            None: 진입 기회 없음
            TradeSignal: {"direction": "UP"/"DOWN", "size": float, "reason": str}
        """
        pass

    @abstractmethod
    async def execute(self, signal: TradeSignal) -> bool:
        """
        거래 실행

        Returns:
            bool: 성공 여부
        """
        pass
```

### Available Strategies

#### 1. Arbitrage (Sure-bet)

**File**: `arbitrage.py`

**Class**: `SurebetEngine`

**Purpose**: Risk-free profit when YES + NO prices < 1.0

**Logic**:
```python
 Opportunity: YES_Price + NO_Price < 1.0
 Profit: 1.0 - (YES_Price + NO_Price) - Transaction_Costs

 Action:
 - Buy both YES and NO at current prices
 - Hold until expiry or price convergence
 - Guaranteed profit regardless of outcome
```

**Parameters**:
```python
@dataclass
class SurebetConfig:
    enabled: bool = True
    min_profit_pct: float = 2.0  # Minimum 2% profit
    max_position_size: float = 100  # Maximum USDC per trade
    transaction_cost_pct: float = 0.5  # 0.5% transaction costs
    max_slippage_pct: float = 0.5  # Maximum acceptable slippage
```

**Example**:
```python
from strategies.arbitrage import SurebetEngine

config = SurebetConfig(min_profit_pct=2.0)
strategy = SurebetEngine(config, polymarket)

# Analyze market
signal = await strategy.analyze(market_data)
# Returns:
# {
#     "action": "BUY_BOTH",
#     "yes_size": 100,
#     "no_size": 100,
#     "yes_price": 0.48,
#     "no_price": 0.50,
#     "expected_profit_pct": 2.0,
#     "reason": "YES(0.48) + NO(0.50) = 0.98 < 1.0, 수익 2%"
# }
```

#### 2. Edge Hedge

**File**: `edge_hedge.py`

**Class**: `EdgeHedgeStrategy`

**Purpose**: Trade on mispricings between Polymarket and Binance implied prices

**Logic**:
```python
1. Get Polymarket price (e.g., BTC > $50k)
2. Get Binance BTC price
3. Calculate Binance implied probability
4. Trade if spread > threshold
5. Hedge with Binance futures

 Hedge Ratio:
 - Long Polymarket YES → Short Binance futures (BTC exposure)
 - Long Polymarket NO → Long Binance futures (inverse exposure)
```

**Parameters**:
```python
@dataclass
class EdgeHedgeConfig:
    enabled: bool = True
    min_edge_pct: float = 5.0  # Minimum 5% edge
    hedge_ratio: float = 1.0  # 1:1 hedge ratio
    profit_hedge_threshold_pct: float = 7.0  # Close hedge at 7% profit
    stop_loss_pct: float = 10.0  # Stop loss at 10%
    max_position_usdc: float = 500
```

**Example**:
```python
from strategies.edge_hedge import EdgeHedgeStrategy

config = EdgeHedgeConfig(min_edge_pct=5.0)
strategy = EdgeHedgeStrategy(config, polymarket, binance)

signal = await strategy.analyze(market_data)
# Returns:
# {
#     "action": "BUY_YES",
#     "size": 50,
#     "entry_price": 0.60,
#     "polymarket_implied": 0.60,
#     "binance_implied": 0.65,
#     "edge_pct": 5.0,
#     "hedge_action": "SHORT_BINANCE",
#     "hedge_size": 0.001,  # BTC size
#     "reason": "Polymarket 0.60 < Binance implied 0.65, 엣지 5%"
# }
```

#### 3. Expiry Sniper

**File**: `expiry_sniper.py`

**Class**: `ExpirySniperStrategy`

**Purpose**: Capture value near market expiration when prices are inefficient

**Logic**:
```python
Condition: Time to expiry < threshold (default 5 minutes)
Opportunity: Mispriced options near expiry

Why it works:
- Liquidity drops near expiry
- Market makers reduce exposure
- Prices deviate from fair value

Action:
- Buy underpriced options
- Hedge with Binance if directional exposure
- Hold until expiry for maximum profit
```

**Parameters**:
```python
@dataclass
class ExpirySniperConfig:
    enabled: bool = True
    expiry_threshold_seconds: int = 300  # 5 minutes
    min_edge_pct: float = 3.0
    max_spread_pct: float = 2.0  # Maximum bid-ask spread
    use_hedge: bool = True
    max_position_usdc: float = 200
```

**Example**:
```python
from strategies.expiry_sniper import ExpirySniperStrategy

config = ExpirySniperConfig(expiry_threshold_seconds=300)
strategy = ExpirySniperStrategy(config, polymarket, binance)

signal = await strategy.analyze(market_data)
# Returns:
# {
#     "action": "BUY_YES",
#     "size": 75,
#     "entry_price": 0.45,
#     "fair_value": 0.52,
#     "edge_pct": 7.0,
#     "time_to_expiry": 120,  # seconds
#     "reason": "만기 2분 전, 시장가 0.45 < 공정가 0.52, 엣지 7%"
# }
```

#### 4. Trend Following

**File**: `trend.py`

**Class**: `TrendStrategy`

**Purpose**: Directional trading based on price trends and momentum

**Logic**:
```python
1. Calculate trend indicators (SMA, RSI, MACD)
2. Identify trend direction and strength
3. Enter trade in trend direction
4. Use optional hedge to reduce risk

Indicators:
- SMA (Simple Moving Average): Trend direction
- RSI (Relative Strength Index): Overbought/oversold
- Momentum: Price velocity
```

**Parameters**:
```python
@dataclass
class TrendConfig:
    enabled: bool = False
    trend_period_seconds: int = 3600  # 1 hour
    min_trend_strength: float = 0.6  # Minimum trend strength
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    use_hedge: bool = True
    hedge_ratio: float = 0.5  # Partial hedge
    max_position_usdc: float = 300
```

**Example**:
```python
from strategies.trend import TrendStrategy

config = TrendConfig(trend_period_seconds=3600)
strategy = TrendStrategy(config, polymarket, binance)

signal = await strategy.analyze(market_data)
# Returns:
# {
#     "action": "BUY_YES",
#     "size": 50,
#     "entry_price": 0.55,
#     "trend_direction": "UP",
#     "trend_strength": 0.75,
#     "rsi": 55,
#     "momentum": 0.05,
#     "reason": "상승 추세 강함 (강도 0.75), RSI 55, 모멘텀 양호"
# }
```

## Common Patterns

### Strategy Initialization

```python
from feature_source.config import get_config
from exchanges.polymarket import PolymarketCLOB
from exchanges.binance import BinanceFeed
from strategies.arbitrage import SurebetEngine

# Load configuration
config = get_config(suffix="")

# Initialize exchanges
polymarket = PolymarketCLOB(config.wallet_address, config.private_key)
await polymarket.initialize()

binance = BinanceFeed()
await binance.connect()

# Initialize strategy
strategy_config = config.strategies["arbitrage"]
strategy = SurebetEngine(strategy_config, polymarket)
```

### Signal Analysis

```python
async def analyze_and_trade(strategy, market_data):
    # Analyze market
    signal = await strategy.analyze(market_data)

    if not signal:
        logger.debug("No trading opportunity found")
        return

    # Log signal
    logger.info(f"Signal found: {signal['reason']}")

    # Execute trade
    success = await strategy.execute(signal)

    if success:
        logger.info(f"Trade executed: {signal['action']} {signal['size']} @ {signal.get('entry_price')}")
    else:
        logger.error("Trade execution failed")
```

### Error Handling

```python
async def execute_with_retry(self, signal: TradeSignal, max_retries: int = 3) -> bool:
    """거래 실행 with 재시도"""
    for attempt in range(max_retries):
        try:
            return await self.execute(signal)
        except InsufficientLiquidity as e:
            self.logger.warning(f"유동성 부족: {e}")
            return False
        except NetworkError as e:
            self.logger.warning(f"네트워크 오류 (시도 {attempt + 1}): {e}")
            await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"예상치 못한 오류: {e}")
            return False

    return False
```

## Strategy Selection Guide

| Market Condition | Best Strategy | Risk Level |
|------------------|---------------|------------|
| YES + NO < 1.0 | Arbitrage | None (risk-free) |
| Polymarket ≠ Binance implied | Edge Hedge | Low (hedged) |
| Near expiry, mispriced | Expiry Sniper | Medium |
| Strong trend detected | Trend Following | High |

## Performance Metrics

Each strategy tracks:
- **Total Trades**: 총 거래 횟수
- **Win Rate**: 승률
- **Average Profit**: 평균 수익
- **Total PnL**: 총 손익
- **Sharpe Ratio**: 샤프 비율 (risk-adjusted return)

```python
# Get strategy performance
performance = strategy.get_performance()
print(f"Total Trades: {performance['total_trades']}")
print(f"Win Rate: {performance['win_rate']:.2%}")
print(f"Total PnL: ${performance['total_pnl']:.2f}")
print(f"Sharpe Ratio: {performance['sharpe_ratio']:.2f}")
```

## Dependencies

### Internal
- `feature_source/config.py` - Strategy configuration
- `feature_source/models/probability.py` - Fair value calculations
- `feature_source/exchanges/` - Market data and execution
- `feature_source/logger.py` - Trade logging

### External
- `pandas` - Data analysis for trend calculations
- `numpy` - Numerical computations
- `asyncio` - Async strategy execution

## Configuration Example

```json
{
  "strategies": {
    "arbitrage": {
      "enabled": true,
      "min_profit_pct": 2.0,
      "max_position_size": 100,
      "transaction_cost_pct": 0.5
    },
    "edge_hedge": {
      "enabled": true,
      "min_edge_pct": 5.0,
      "hedge_ratio": 1.0,
      "profit_hedge_threshold_pct": 7.0,
      "stop_loss_pct": 10.0
    },
    "expiry_sniper": {
      "enabled": true,
      "expiry_threshold_seconds": 300,
      "min_edge_pct": 3.0,
      "use_hedge": true
    },
    "trend": {
      "enabled": false,
      "trend_period_seconds": 3600,
      "use_hedge": true
    }
  }
}
```

<!-- MANUAL: -->
