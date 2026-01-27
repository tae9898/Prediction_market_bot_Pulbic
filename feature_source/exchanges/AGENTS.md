<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# exchanges

## Purpose
Exchange integration modules providing real-time market data and trading execution capabilities for Binance and Polymarket.

## Key Files

| File | Description |
|------|-------------|
| `binance.py` | Binance WebSocket feed for real-time BTC price data |
| `polymarket.py` | Polymarket CLOB client for market queries and order execution |
| `__init__.py` | Python package initializer |

## For AI Agents

### Working In This Directory
- Always handle connection failures gracefully
- Implement reconnection logic for WebSocket streams
- Cache REST API responses to respect rate limits
- Log all trading operations for audit trail

### Binance Feed

**Purpose**: Provide real-time BTC/USDT price for hedging calculations

```python
from exchanges.binance import BinanceFeed

# Initialize feed
feed = BinanceFeed()

# Connect to WebSocket
await feed.connect()

# Get current price
price = feed.get_price()

# Subscribe to price updates
def on_price_update(price: float, timestamp: float):
    print(f"BTC Price: ${price}")

feed.subscribe(on_price_update)

# Disconnect when done
await feed.disconnect()
```

**Data Format**:
```python
{
    "symbol": "BTCUSDT",
    "price": 51234.50,
    "timestamp": 1706457600.0,
    "volume": 123.45
}
```

**Error Handling**:
```python
try:
    await feed.connect()
except ConnectionError as e:
    logger.error(f"Binance connection failed: {e}")
    # Implement reconnection logic
    await asyncio.sleep(5)
    await feed.connect()
```

### Polymarket CLOB Client

**Purpose**: Interact with Polymarket CLOB for trading prediction markets

```python
from exchanges.polymarket import PolymarketCLOB

# Initialize client
pm = PolymarketCLOB(
    wallet_address="0x...",
    private_key="your_private_key",
    api_key=os.getenv("POLYMARKET_API_KEY")
)

# Initialize connection
await pm.initialize()

# Query markets
markets = await pm.get_markets(condition_id="...")

# Get order book
order_book = await pm.get_order_book(token_id="12345")
# {
#     "bids": [[0.65, 100], [0.64, 200]],
#     "asks": [[0.67, 150], [0.68, 300]],
#     "last_updated": 1706457600.0
# }

# Place order
order = await pm.place_order(
    token_id="12345",
    side="BUY",  # or "SELL"
    price=0.66,
    size=10
)
# {
#     "order_id": "order_abc123",
#     "status": "OPEN",
#     "filled": 0,
#     "remaining": 10
# }

# Cancel order
await pm.cancel_order(order_id="order_abc123")

# Get positions
positions = await pm.get_positions()
```

**WebSocket Streams**:
```python
# Subscribe to order book updates
await pm.subscribe_orderbook(token_id="12345")

async def handle_orderbook_update(update):
    print(f"Bids: {update['bids']}, Asks: {update['asks']}")

pm.on_orderbook_update(handle_orderbook_update)

# Subscribe to trade updates
await pm.subscribe_trades(token_id="12345")

async def handle_trade(trade):
    print(f"Trade: {trade['side']} {trade['size']} @ {trade['price']}")

pm.on_trade(handle_trade)
```

## Common Patterns

### Reconnection Logic

```python
class ExchangeFeed:
    async def connect_with_retry(self, max_retries: int = 5):
        for attempt in range(max_retries):
            try:
                await self.connect()
                return True
            except Exception as e:
                logger.warning(f"Connection failed (attempt {attempt + 1}): {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return False
```

### Rate Limiting

```python
import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = []

    async def acquire(self):
        now = datetime.now()
        # Remove old requests
        self.requests = [r for r in self.requests if r > now - timedelta(minutes=1)]

        if len(self.requests) >= self.requests_per_minute:
            sleep_time = 60 / self.requests_per_minute
            await asyncio.sleep(sleep_time)

        self.requests.append(now)

# Usage
limiter = RateLimiter(requests_per_minute=60)
await limiter.acquire()
response = await pm.get_markets()
```

### Order Placement with Retry

```python
async def place_order_with_retry(
    pm: PolymarketCLOB,
    token_id: str,
    side: str,
    price: float,
    size: float,
    max_retries: int = 3
) -> Optional[str]:
    for attempt in range(max_retries):
        try:
            order = await pm.place_order(token_id, side, price, size)
            logger.info(f"Order placed: {order['order_id']}")
            return order['order_id']
        except InsufficientLiquidity as e:
            logger.warning(f"Insufficient liquidity: {e}")
            return None
        except NetworkError as e:
            logger.warning(f"Network error (attempt {attempt + 1}): {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    return None
```

## Dependencies

### Internal
- `feature_source/config.py` - API keys and endpoints
- `feature_source/logger.py` - Trading operation logging

### External
- `ccxt` - Binance exchange integration
- `web3` - Polygon blockchain interaction (for Polymarket)
- `websocket-client` - WebSocket connections
- `requests` - REST API calls
- `python-dotenv` - Environment variable management

## API Endpoints

### Binance
- REST: `https://api.binance.com/api/v3/`
- WebSocket: `wss://stream.binance.com:9443/ws/`

### Polymarket CLOB
- REST: `https://clob.polymarket.com/`
- WebSocket: `wss://clob.polymarket.com/ws`

## Error Types

| Error | Cause | Handling |
|-------|-------|----------|
| `ConnectionError` | Network/WS disconnect | Reconnect with backoff |
| `RateLimitError` | Too many requests | Implement rate limiting |
| `InsufficientLiquidity` | Not enough depth | Reduce order size or skip |
| `InvalidOrder` | Bad price/size | Validate before sending |
| `AuthError` | Invalid credentials | Check API keys |

## Performance Considerations

- **Latency**: WebSocket < 50ms, REST < 500ms
- **Rate Limits**: Binance 1200 req/min, Polymarket 300 req/min
- **Data Freshness**: WebSocket streams update in real-time
- **Connection Pooling**: Reuse connections for multiple requests

<!-- MANUAL: -->
