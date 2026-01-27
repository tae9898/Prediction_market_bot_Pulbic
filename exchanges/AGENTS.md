<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# exchanges

## Purpose
**거래소 연결 모듈** - 오더북 데이터, 가격 정보, 거래 실행을 위한 general-purpose exchange integration module입니다.

Binance (암호화폐 가격 데이터)와 Polymarket (예측 시장 CLOB)에 연결하여 실시간 데이터를 제공하고 거래를 실행합니다.

## Key Files

| File | Description |
|------|-------------|
| `binance.py` | Binance WebSocket 실시간 가격 피드 (다양한 심볼 지원) |
| `polymarket.py` | Polymarket CLOB 클라이언트 (마켓 조회, 오더북, 주문, 정산) |
| `__init__.py` | Python 패키지 초기화 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `__pycache__/` | 컴파일된 Python 캐시 파일 (자동 생성) |

## For AI Agents

### Working In This Directory
이 모듈은 **거래소 데이터 인터페이스**를 담당합니다:
- 실제 거래 로직은 상위 레벨(`feature_source/`, `strategies/`)에 있습니다
- 여기서는 데이터 가져오기와 주문 실행만 담당
- config.py或其他 모듈에 대한 의존성을 최소화하여 general하게 사용 가능

### Exchange Implementations

#### Binance Feed (`binance.py`)
**Purpose**: 다양한 암호화폐 심볼의 실시간 가격 데이터를 WebSocket으로 제공

**Features**:
- 실시간 가격 업데이트 (1초 단위)
- 24시간 통계 (변동률, 고가, 저가, 거래량)
- 변동성 계산 (연간화)
- 모멘텀 지표 (Bullish/Bearish/Neutral)
- 여러 심볼 지원 (BTC, ETH 등)

```python
from exchanges.binance import BinanceFeed

# BTC/USDT 피드 생성
feed = BinanceFeed(symbol="BTC", quote_currency="USDT")
await feed.start()

# ETH/USDT 피드 생성
eth_feed = BinanceFeed(symbol="ETH")

# 현재 가격 조회
price = feed.get_price()

# 변동성 계산
volatility = feed.calculate_volatility()

# 모멘텀 확인
momentum = feed.get_momentum()  # "BULLISH", "BEARISH", "NEUTRAL"

# 콜백 설정
async def on_price_update(price):
    print(f"New price: ${price}")

feed.set_price_callback(on_price_update)
```

#### Polymarket CLOB (`polymarket.py`)
**Purpose**: Polymarket prediction market 거래를 위한 general-purpose 클라이언트

**Features**:
- 마켓 조회 및 검색
- 오더북 데이터 (best bid/ask + full depth)
- 주문 실행 (market/limit orders)
- 포지션 관리
- 자동 정산 (merge/redeem)
- Gnosis Safe proxy 지원

**General한 사용법**:
```python
from exchanges.polymarket import PolymarketClient

# 클라이언트 초기화 (필수 파라미터만)
pm = PolymarketClient(
    private_key="your_private_key",
    web3_rpc_url="https://polygon-rpc.com"  # 또는 커스텀 RPC
)

# 또는 모든 파라미터 지정
pm = PolymarketClient(
    private_key="your_private_key",
    proxy_address="0x...",  # Gnosis Safe (선택)
    api_key="...",           # Polymarket API (선택)
    asset_type="BTC",        # BTC 또는 ETH
    web3_rpc_url="https://polygon-rpc.com",
    ctf_address="0x4D97DCd97eC945f40cF65F87097ACE5EA0476045",
    collateral_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    log_callback=lambda msg: print(msg),
    pnl_callback=lambda msg: print(f"[PNL] {msg}")
)

# 초기화
await pm.initialize()

# 마켓 찾기
await pm.find_hourly_market()

# 오더북 업데이트
await pm.refresh_market()

# 주문 실행
await pm.buy(
    direction="UP",
    amount_usdc=100,
    strategy="arbitrage"
)

# 전체 오더북 가져오기
await pm.update_full_orderbook()
yes_depth = pm.market.yes_asks  # [{price, size}, ...]

# 정산
await pm.redeem_all_resolved_positions()
```

### Design Principles

1. **Minimal Dependencies**: `config.py`或其他 모듈에 의존하지 않음
2. **Configuration via Parameters**: 모든 설정을 생성자 파라미터로 전달
3. **Flexible Callbacks**: 로그 및 P&L 콜백을 사용자 정의 가능
4. **Multi-Asset Support**: BTC, ETH 등 다양한 자산 지원
5. **Proxy Support**: Gnosis Safe 등 프록시 지갑 지원

### Common Patterns

#### 콜백 설정
```python
def log_handler(msg: str):
    # 원하는 로그 시스템으로 전송
    send_to_logging_service(msg)

def pnl_handler(msg: str):
    # P&L을 별도로 기록
    send_to_pnl_tracker(msg)

pm = PolymarketClient(
    private_key=key,
    log_callback=log_handler,
    pnl_callback=pnl_handler
)
```

#### 여러 자산 동시 사용
```python
# BTC 마켓
btc_pm = PolymarketClient(
    private_key=key,
    asset_type="BTC"
)
await btc_pm.initialize()
await btc_pm.find_hourly_market()

# ETH 마켓
eth_pm = PolymarketClient(
    private_key=key,
    asset_type="ETH"
)
await eth_pm.initialize()
await eth_pm.find_hourly_market()
```

## Dependencies

### Internal
- 없음 (독립적 모듈)

### External
- `websockets` - Binance WebSocket 연결
- `aiohttp` - 비동기 HTTP 요청
- `web3` - Ethereum/Polygon 블록체인 상호작용
- `py_clob_client` - Polymarket CLOB API
- `eth_account` - 트랜잭션 서명
- `numpy` - 수치 계산 (변동성 등)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Trading Bot                         │
│            (feature_source/bot_core.py)                 │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                              │
┌───────▼──────────┐        ┌──────────▼──────────┐
│  BinanceFeed     │        │ PolymarketClient    │
│  - symbol        │        │ - asset_type        │
│  - quote_currency│        │ - proxy_address     │
│  - web3_rpc_url  │        │ - web3_rpc_url      │
└──────────────────┘        └─────────────────────┘
        │                              │
        ▼                              ▼
   Crypto Prices              Prediction Markets
   (BTC/ETH/etc)               (YES/NO tokens)
```

## API Reference

### BinanceFeed

```python
class BinanceFeed:
    def __init__(
        self,
        symbol: str = "BTC",              # 기본 심볼
        quote_currency: str = "USDT",     # 견적 통화
        volatility_window_minutes: int = 60  # 변동성 윈도우
    )

    async def start() -> None
    async def stop() -> None
    def get_price() -> float
    def get_24h_stats() -> dict
    def calculate_volatility() -> float
    def get_momentum() -> str
    def set_price_callback(callback: Callable) -> None
```

### PolymarketClient

```python
class PolymarketClient:
    def __init__(
        self,
        private_key: str,                 # 필수
        proxy_address: str = "",           # Gnosis Safe (선택)
        order_proxy_url: str = "",         # 주문용 프록시 (선택)
        api_key: str = "",                 # Polymarket API (선택)
        asset_type: str = "BTC",           # BTC 또는 ETH
        web3_rpc_url: str = DEFAULT_RPC,   # Web3 RPC URL
        ctf_address: str = DEFAULT_CTF,    # CTF 컨트랙트
        collateral_address: str = DEFAULT_USDC,  # USDC 주소
        log_callback: Callable = None,
        pnl_callback: Callable = None,
        auto_redeem_enabled: bool = True
    )

    async def initialize() -> bool
    async def find_hourly_market() -> bool
    async def refresh_market() -> None
    async def update_full_orderbook() -> None
    async def buy(direction, amount_usdc, size, ...) -> bool
    async def sell(direction, size, ...) -> bool
    async def execute_surebet(yes_size, yes_price, no_size, no_price) -> Dict
    async def redeem_all_resolved_positions() -> int
    async def get_usdc_balance() -> float
```

<!-- MANUAL: -->
