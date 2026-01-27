"""
BTC Polymarket ARB Bot V3 - Polymarket CLOB Client
Polymarket CLOB API를 통한 마켓 조회, 오더북, 주문 실행

Can be used with ExchangeClient interface from core.interfaces.exchange_base
"""

import asyncio
import aiohttp
import time
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Callable, Tuple
import re
from web3 import Web3
# Web3 v7 PoA Middleware (for Polygon)
from web3.middleware import ExtraDataToPOAMiddleware

# Import core interfaces (optional - for adapter pattern)
try:
    from core.interfaces.exchange_base import ExchangeClient as BaseExchangeClient
    HAS_CORE_INTERFACE = True
except (ImportError, ModuleNotFoundError):
    BaseExchangeClient = object
    HAS_CORE_INTERFACE = False

try:
    from config import get_config
except ImportError:
    get_config = None

try:
    from py_clob_client.client import ClobClient

    from py_clob_client.clob_types import MarketOrderArgs, OrderArgs, OrderType, ApiCreds, BalanceAllowanceParams, AssetType
    from py_clob_client.order_builder.constants import BUY, SELL
except ImportError:
    print("[ERROR] py-clob-client 패키지가 필요합니다: pip install py-clob-client")
    raise

try:
    from eth_account import Account
except ImportError:
    Account = None


# Minimal ABI for Conditional Tokens Framework (CTF)
CTF_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "conditionId", "type": "bytes32"},
            {"name": "index", "type": "uint256"}
        ],
        "name": "payoutNumerators",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "mergePositions",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"}
        ],
        "name": "redeemPositions",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Minimal ABI for Gnosis Safe (Proxy)
GNOSIS_SAFE_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "operation", "type": "uint8"},
            {"name": "safeTxGas", "type": "uint256"},
            {"name": "baseGas", "type": "uint256"},
            {"name": "gasPrice", "type": "uint256"},
            {"name": "gasToken", "type": "address"},
            {"name": "refundReceiver", "type": "address"},
            {"name": "signatures", "type": "bytes"}
        ],
        "name": "execTransaction",
        "outputs": [{"name": "success", "type": "bool"}],
        "payable": True,
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "nonce",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "domainSeparator",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function"
    }
]

@dataclass
class MarketData:
    """Polymarket 마켓 데이터"""
    condition_id: str = ""
    token_id_up: str = ""
    token_id_down: str = ""
    strike_price: float = 0.0
    end_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Best Ask/Bid (기존)
    up_ask: float = 0.0
    up_bid: float = 0.0
    down_ask: float = 0.0
    down_bid: float = 0.0
    
    # 스프레드
    spread_up: float = 0.0
    spread_down: float = 0.0
    
    # 오더북 깊이 (Sure-Bet용)
    yes_asks: list = field(default_factory=list)  # [{price, size}, ...]
    yes_bids: list = field(default_factory=list)
    no_asks: list = field(default_factory=list)
    no_bids: list = field(default_factory=list)
    
    last_update: float = 0.0


@dataclass
class Position:
    """포지션 정보"""
    direction: str = ""  # "UP" or "DOWN"
    size: float = 0.0
    avg_price: float = 0.0
    cost: float = 0.0
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    strategy: str = ""  # "directional" or "contrarian"


class PolymarketClient(BaseExchangeClient if HAS_CORE_INTERFACE else object):
    """
    Polymarket CLOB API 클라이언트

    When core.interfaces.exchange_base.ExchangeClient is available, this class
    can be wrapped with PolymarketExchangeAdapter to provide the universal interface.

    For direct use with the new interface, use:
        from exchanges.adapters import PolymarketExchangeAdapter, create_polymarket_adapter
        adapter = create_polymarket_adapter(private_key=...)
        await adapter.buy("BTC-UP", size=10.0)
    """
    
    GAMMA_API = "https://gamma-api.polymarket.com"
    CLOB_API = "https://clob.polymarket.com"
    DATA_API = "https://data-api.polymarket.com"
    
    def __init__(
        self,
        private_key: str,
        proxy_address: str = "",
        order_proxy_url: str = "",
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        asset_type: str = "BTC",  # "BTC" or "ETH"
        log_callback: Optional[Callable[[str], None]] = None,
        pnl_callback: Optional[Callable[[str], None]] = None,
    ):
        self.log_callback = log_callback
        self.pnl_callback = pnl_callback
        self.private_key = private_key
        self.asset_type = asset_type.upper()
        
        # 주소 유도
        if Account:
            try:
                self.address = Account.from_key(private_key).address
            except:
                self.address = "Unknown"
        else:
            self.address = "Unknown"
            
        self.proxy_address = proxy_address
        self.order_proxy_url = order_proxy_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        
        self.market = MarketData()
        self.position = Position()
        self.transactions: List[Dict] = []
        self.expired_markets: List[MarketData] = []  # 정산 대기 중인 만료된 마켓들
        
        self._clob_client: Optional[ClobClient] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._initialized = False
        
        # P&L tracking
        self.total_pnl = 0.0
        self.realized_pnl = 0.0
        
        # Executor for non-blocking calls
        self._executor = ThreadPoolExecutor(max_workers=10)
    
    def _log(self, message: str) -> None:
        """로그 출력 (콜백 또는 표준 출력)"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def _log_pnl(self, message: str) -> None:
        """P&L 로그 출력"""
        if self.pnl_callback:
            self.pnl_callback(message)
        else:
            # Fallback to normal log if no P&L callback provided
            self._log(f"[PNL] {message}")

    async def fetch_positions(self) -> List[Dict]:
        """Fetch current positions from Data API"""
        target = self.proxy_address if self.proxy_address else self.address
        if not target or target == "Unknown":
            return []
            
        try:
            url = f"{self.DATA_API}/positions"
            params = {"user": target}
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
        except Exception as e:
            self._log(f"[API] Fetch positions failed: {e}")
            return []

    async def fetch_activity(self, limit: int = 500) -> List[Dict]:
        """Fetch all user activity (trades, deposits, redeems)"""
        target = self.proxy_address if self.proxy_address else self.address
        if not target or target == "Unknown":
            return []
            
        activities = []
        offset = 0
        
        try:
            while True:
                url = f"{self.DATA_API}/activity"
                params = {"user": target, "limit": limit, "offset": offset}
                
                async with self._session.get(url, params=params) as resp:
                    if resp.status != 200:
                        break
                    
                    data = await resp.json()
                    if not data:
                        break
                        
                    activities.extend(data)
                    
                    if len(data) < limit:
                        break
                        
                    offset += limit
                    await asyncio.sleep(0.2) # Rate limit protection
                    
            return activities
        except Exception as e:
            self._log(f"[API] Fetch activity failed: {e}")
            return activities

    async def initialize(self) -> bool:
        """클라이언트 초기화 (Auto-Auth: Proxy -> EOA 시도)"""
        try:
            # 주문/정산용 Proxy 설정 (py-clob-client 및 Web3는 requests를 사용하므로 환경변수 설정)
            if self.order_proxy_url:
                import os
                os.environ["HTTP_PROXY"] = self.order_proxy_url
                os.environ["HTTPS_PROXY"] = self.order_proxy_url
                self._log(f"[Polymarket] Write 작업을 위한 Proxy 환경변수 설정 완료")

            # 조회용 세션 (aiohttp)는 Proxy를 타지 않도록 trust_env=False 설정
            # 사용자가 "주문과 Redeem만 Proxy 사용"을 원했으므로 Read는 Direct로 연결
            self._session = aiohttp.ClientSession(trust_env=False)
            
            # 1. Proxy 모드 시도 (signature_type=2)
            self._log(f"[Polymarket] Proxy 모드 인증 시도... (Bot Address: {self.address})")
            if await self._init_clob_client(signature_type=2):
                self._log("[Polymarket] Proxy 모드 연결 성공")
                self.position.strategy = "Proxy Mode"  # 상태 표시용
                self._initialized = True
                return True
                
            # 2. EOA 모드 시도 (signature_type=1) --> Proxy 실패 시 Fallback
            self._log("[Polymarket] Proxy 인증 실패, EOA 모드 인증 시도...")
            if await self._init_clob_client(signature_type=1):
                self._log("[Polymarket] EOA 모드 연결 성공")
                self.position.strategy = "EOA Mode"  # 상태 표시용
                self._initialized = True
                return True
            
            self._log("[Polymarket] 모든 인증 방식 실패")
            return False
            
        except Exception as e:
            self._log(f"[Polymarket] 초기화 치명적 오류: {e}")
            return False

    async def _init_clob_client(self, signature_type: int) -> bool:
        """CLOB Client 초기화 및 연결 테스트"""
        try:
            # funder 설정: Proxy 모드(2)일 때만 proxy_address 사용, EOA(1)일 때는 None
            funder = self.proxy_address if (signature_type == 2 and self.proxy_address) else None
            
            self._clob_client = ClobClient(
                host=self.CLOB_API,
                key=self.private_key,
                chain_id=137,
                signature_type=signature_type,
                funder=funder,
            )
            
            
            if self.api_key and self.api_secret and self.passphrase:
                creds = ApiCreds(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    api_passphrase=self.passphrase,
                )
                self._clob_client.set_api_creds(creds)
                
            # 연결 테스트 (API 유효성 검증)
            # get_trades를 사용하여 인증 확인 (인자 없이 호출)
            try:
                loop = asyncio.get_running_loop()
                # 동기 함수인 get_trades()를 별도 스레드에서 실행하여 이벤트 루프 블로킹 방지
                await loop.run_in_executor(self._executor, self._clob_client.get_trades)
                return True
            except Exception as e:
                self._log(f"[Polymarket] 연결 테스트 실패 (SigType={signature_type}): {e}")
                return False
                
        except Exception as e:
            self._log(f"[Polymarket] 클라이언트 생성 오류: {e}")
            return False
    
    async def close(self) -> None:
        """세션 종료"""
        if self._session:
            await self._session.close()
        if self._executor:
            self._executor.shutdown(wait=False)
    
    def _generate_market_slug(self, hours_offset: int = 0) -> str:
        """현재 시간 기준 마켓 slug 생성"""
        # 동부 시간대로 변환 (UTC-5 or UTC-4 for DST)
        now_utc = datetime.now(timezone.utc)
        # 간단히 UTC-5 사용 (EST)
        et_offset = timedelta(hours=-5)
        now_et = now_utc + et_offset
        
        # 현재 정시 또는 offset 적용
        target_hour = now_et.replace(minute=0, second=0, microsecond=0) + timedelta(hours=hours_offset)
        
        month = target_hour.strftime("%B").lower()
        day = target_hour.day
        hour = target_hour.hour
        
        if hour == 0:
            hour_str = "12am"
        elif hour < 12:
            hour_str = f"{hour}am"
        elif hour == 12:
            hour_str = "12pm"
        else:
            hour_str = f"{hour - 12}pm"
        
        # Asset-specific slug generation
        asset_name = "bitcoin" if self.asset_type == "BTC" else "ethereum"
        slug = f"{asset_name}-up-or-down-{month}-{day}-{hour_str}-et"
        return slug
    
    async def find_hourly_market(self) -> bool:
        """자산 타입에 맞는 hourly 마켓 검색 - 여러 시간대 시도"""
        # 현재 시간, 다음 정시, 그 다음 정시 순서로 시도
        for offset in [0, 1, 2]:
            if await self._try_find_market(offset):
                return True
        
        self._log(f"[Polymarket] {self.asset_type} hourly 마켓을 찾을 수 없습니다")
        return False
    
    async def _try_find_market(self, hours_offset: int) -> bool:
        """특정 시간대의 마켓 검색 시도"""
        try:
            slug = self._generate_market_slug(hours_offset)
            url = f"{self.GAMMA_API}/events?slug={slug}"
            
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    return False
                
                events = await resp.json()
                
            if not events or not isinstance(events, list) or len(events) == 0:
                return False
            
            event = events[0]
            markets = event.get("markets", [])
            
            if not markets:
                return False
            
            # UP/DOWN 마켓 찾기
            for market in markets:
                outcome = market.get("outcome", "")
                if outcome:
                    outcome = outcome.upper()
                
                # clobTokenIds 파싱 (문자열 JSON 또는 배열)
                clob_ids = market.get("clobTokenIds")
                token_id = ""
                
                if clob_ids:
                    if isinstance(clob_ids, str):
                        # 문자열인 경우 JSON 파싱 시도
                        try:
                            import json as json_module
                            parsed = json_module.loads(clob_ids)
                            if isinstance(parsed, list) and len(parsed) > 0:
                                token_id = parsed[0]
                        except:
                            token_id = clob_ids
                    elif isinstance(clob_ids, list) and len(clob_ids) > 0:
                        token_id = clob_ids[0]
                
                # "Up or Down" 마켓: 첫 번째 토큰은 UP, 두 번째는 DOWN
                # outcome이 없는 경우 인덱스로 구분
                if outcome:
                    if "UP" in outcome or "YES" in outcome:
                        self.market.token_id_up = token_id
                    elif "DOWN" in outcome or "NO" in outcome:
                        self.market.token_id_down = token_id
                
                # condition_id 추출
                if not self.market.condition_id:
                    self.market.condition_id = market.get("conditionId", "")
            
            # "Up or Down" 마켓의 경우 마켓이 하나이고 token_ids가 2개
            if len(markets) == 1 and not self.market.token_id_up:
                clob_ids = markets[0].get("clobTokenIds")
                if clob_ids:
                    if isinstance(clob_ids, str):
                        try:
                            import json as json_module
                            clob_ids = json_module.loads(clob_ids)
                        except:
                            pass
                    
                    if isinstance(clob_ids, list) and len(clob_ids) >= 2:
                        # Revert: Found that Index 0 is UP (Yes) and Index 1 is DOWN (No) for these markets
                        # based on price analysis (Price < Strike -> Down winning -> Down expensive)
                        # Current observation: Index 1 is expensive (57c) => Index 1 is Down.
                        self.market.token_id_up = clob_ids[0]
                        self.market.token_id_down = clob_ids[1]
                        
                        self._log(f"[Polymarket] Token Fallback Used: UP={clob_ids[0][:10]}..., DOWN={clob_ids[1][:10]}...")
            
            # Strike price 추출
            title = event.get("title", "")
            description = event.get("description", "")
            
            # 여러 패턴 시도
            # 1. 제목에서 $XX,XXX 형식
            strike_match = re.search(r'\$([0-9,]+\.?\d*)', title)
            
            # 2. 설명에서 $XX,XXX 형식
            if not strike_match:
                strike_match = re.search(r'\$([0-9,]+\.?\d*)', description)
            
            # 3. "starting price of X" 패턴 (Up or Down 마켓)
            if not strike_match:
                strike_match = re.search(r'starting price of \$?([0-9,]+\.?\d*)', description, re.IGNORECASE)
            
            # 4. "price at X" 패턴
            if not strike_match:
                strike_match = re.search(r'price at \$?([0-9,]+\.?\d*)', description, re.IGNORECASE)
            
            # 5. 마켓별 startPrice 필드 확인
            if not strike_match:
                for market in markets:
                    if market.get("startPrice"):
                        try:
                            self.market.strike_price = float(market.get("startPrice"))
                            break
                        except:
                            pass
            
            if strike_match:
                self.market.strike_price = float(strike_match.group(1).replace(",", ""))
            
            # 종료 시간
            end_date_str = event.get("endDate", "")
            if end_date_str:
                try:
                    self.market.end_time = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                except:
                    pass
            
            # Strike 가격이 없으면 Binance에서 마켓 시작 시간의 candle open price 가져오기
            if self.market.strike_price == 0 and self.market.end_time:
                await self._fetch_strike_from_binance()
            
            # 오더북 업데이트
            await self._update_orderbook()
            
            self._log(f"[Polymarket] 마켓 발견: {slug}")
            self._log(f"  Strike: ${self.market.strike_price:,.2f}")
            self._log(f"  UP token: {self.market.token_id_up[:30]}..." if self.market.token_id_up else "  UP token: None")
            self._log(f"  DOWN token: {self.market.token_id_down[:30]}..." if self.market.token_id_down else "  DOWN token: None")
            self._log(f"  UP Ask: {self.market.up_ask:.4f}, Bid: {self.market.up_bid:.4f}")
            self._log(f"  DOWN Ask: {self.market.down_ask:.4f}, Bid: {self.market.down_bid:.4f}")
            return True
            
        except Exception as e:
            return False
    
    async def _fetch_strike_from_binance(self) -> None:
        """Binance에서 마켓 시작 시간의 1시간 캔들 open price 가져오기"""
        try:
            # 마켓 시작 시간 = 종료 시간 - 1시간
            start_time = self.market.end_time - timedelta(hours=1)
            start_ts = int(start_time.timestamp() * 1000)
            
            # 자산 타입에 맞는 심볼 사용
            symbol = "BTCUSDT" if self.asset_type == "BTC" else "ETHUSDT"
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&startTime={start_ts}&limit=1"
            
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        # Kline format: [open_time, open, high, low, close, ...]
                        self.market.strike_price = float(data[0][1])  # Open price
                        
        except Exception as e:
            self._log(f"[Polymarket] Binance strike 가져오기 오류: {e}")
    
    async def _update_orderbook(self) -> None:
        """오더북 업데이트 - 병렬 API 호출 (초고속)"""
        try:
            async def fetch_price(token_id: str, side: str) -> float:
                url = f"{self.CLOB_API}/price?token_id={token_id}&side={side}"
                async with self._session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return float(data.get("price", 0))
                return 0.0
            
            # 4개 API 호출을 병렬로 실행 (초고속)
            tasks = []
            if self.market.token_id_up:
                tasks.append(fetch_price(self.market.token_id_up, "buy"))   # up_bid
                tasks.append(fetch_price(self.market.token_id_up, "sell"))  # up_ask
            if self.market.token_id_down:
                tasks.append(fetch_price(self.market.token_id_down, "buy"))   # down_bid
                tasks.append(fetch_price(self.market.token_id_down, "sell"))  # down_ask
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            idx = 0
            if self.market.token_id_up:
                if not isinstance(results[idx], Exception):
                    self.market.up_bid = results[idx]
                idx += 1
                if not isinstance(results[idx], Exception):
                    self.market.up_ask = results[idx]
                idx += 1
                self.market.spread_up = self.market.up_ask - self.market.up_bid
            
            if self.market.token_id_down:
                if not isinstance(results[idx], Exception):
                    self.market.down_bid = results[idx]
                idx += 1
                if not isinstance(results[idx], Exception):
                    self.market.down_ask = results[idx]
                self.market.spread_down = self.market.down_ask - self.market.down_bid
            
            self.market.last_update = time.time()
            
        except Exception as e:
            self._log(f"[Polymarket] 가격 업데이트 오류: {e}")
    
    async def refresh_market(self) -> None:
        """마켓 데이터 새로고침"""
        await self._update_orderbook()
    
    async def get_orderbook_depth(self, token_id: str) -> Dict:
        """
        CLOB API에서 전체 오더북 가져오기 (HTTP 직접 호출)
        
        Returns:
            {"asks": [{"price": str, "size": str}, ...], "bids": [... ]}
        """
        if not token_id:
            return {"asks": [], "bids": []}
        
        try:
            # 직접 HTTP API 호출 (/book 엔드포인트)
            url = f"{self.CLOB_API}/book?token_id={token_id}"
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # 응답 형식: {"asks": [{"price": "0.45", "size": "100"}, ...], "bids": [... ]}
                    asks = data.get("asks", []) or []
                    bids = data.get("bids", []) or []
                    
                    # 정렬: asks는 오름차순 (낮은 가격이 best ask), bids는 내림차순 (높은 가격이 best bid)
                    asks = sorted(asks, key=lambda x: float(x.get("price", 999)))
                    bids = sorted(bids, key=lambda x: float(x.get("price", 0)), reverse=True)
                    
                    return {"asks": asks, "bids": bids}
                else:
                    self._log(f"[Polymarket] 오더북 API 오류: {resp.status}")
                    return {"asks": [], "bids": []}
            
        except Exception as e:
            self._log(f"[Polymarket] 오더북 깊이 가져오기 오류: {e}")
            return {"asks": [], "bids": []}
    
    async def update_full_orderbook(self) -> None:
        """
        YES/NO 토큰의 전체 오더북 깊이 업데이트 (Sure-Bet용) - 병렬 호출
        """
        try:
            # 두 오더북을 병렬로 가져오기 (초고속)
            tasks = []
            if self.market.token_id_up:
                tasks.append(self.get_orderbook_depth(self.market.token_id_up))
            if self.market.token_id_down:
                tasks.append(self.get_orderbook_depth(self.market.token_id_down))
            
            if not tasks:
                return
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            idx = 0
            # YES (Up) 토큰 오더북
            if self.market.token_id_up and not isinstance(results[idx], Exception):
                ob = results[idx]
                self.market.yes_asks = ob["asks"]
                self.market.yes_bids = ob["bids"]
                
                # Best Ask/Bid 업데이트
                if ob["asks"]:
                    self.market.up_ask = float(ob["asks"][0].get("price", 0))
                if ob["bids"]:
                    self.market.up_bid = float(ob["bids"][0].get("price", 0))
                idx += 1
            
            # NO (Down) 토큰 오더북
            if self.market.token_id_down and idx < len(results) and not isinstance(results[idx], Exception):
                ob = results[idx]
                self.market.no_asks = ob["asks"]
                self.market.no_bids = ob["bids"]
                
                # Best Ask/Bid 업데이트
                if ob["asks"]:
                    self.market.down_ask = float(ob["asks"][0].get("price", 0))
                if ob["bids"]:
                    self.market.down_bid = float(ob["bids"][0].get("price", 0))
            
            # 스프레드 업데이트
            self.market.spread_up = self.market.up_ask - self.market.up_bid
            self.market.spread_down = self.market.down_ask - self.market.down_bid
            self.market.last_update = time.time()
            
        except Exception as e:
            self._log(f"[Polymarket] 오더북 깊이 업데이트 오류: {e}")
    
    def get_time_remaining(self) -> int:
        """만료까지 남은 시간 (초)"""
        if not self.market.end_time:
            return 0
        
        now = datetime.now(timezone.utc)
        delta = self.market.end_time - now
        return max(0, int(delta.total_seconds()))
    
    def get_time_remaining_str(self) -> str:
        """만료까지 남은 시간 (MM:SS 형식)"""
        remaining = self.get_time_remaining()
        minutes = remaining // 60
        seconds = remaining % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def get_spread(self) -> float:
        """평균 스프레드 반환"""
        return (self.market.spread_up + self.market.spread_down) / 2
    
    async def buy(
        self,
        direction: str,
        amount_usdc: float = 0.0,
        size: float = 0.0,  # 직접 수량 지정 (헤지용)
        btc_price: float = 0.0,
        edge: float = 0.0,
        strategy: str = "directional"
    ) -> bool:
        """
        마켓 주문 (BUY)
        
        Args:
            direction: "UP" or "DOWN"
            amount_usdc: 주문 금액 (USDC) - size가 0이면 사용
            size: 주문 수량 (shares) - 직접 지정 시 사용 (헤지용)
            btc_price: 현재 BTC 가격 (로깅용)
            edge: 현재 에지 (로깅용)
            strategy: 전략 유형
        """
        if not self._clob_client:
            self._log("[Polymarket] CLOB 클라이언트가 초기화되지 않음")
            return False
        
        try:
            token_id = self.market.token_id_up if direction == "UP" else self.market.token_id_down
            price = self.market.up_ask if direction == "UP" else self.market.down_ask
            
            if not token_id or price <= 0:
                return False
            
            # 주문 수량 계산: size가 지정되면 사용, 아니면 amount_usdc에서 계산
            if size > 0:
                order_size = size
                actual_cost = size * price
            else:
                order_size = amount_usdc / price
                actual_cost = amount_usdc
            
            # Limit Order 실행
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=order_size,  # order_size 사용
                side=BUY,
            )
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(self._executor, self._clob_client.create_and_post_order, order_args)
            
            if response:
                # 포지션 업데이트 - 실제 비용 사용
                self.position.direction = direction
                self.position.size += order_size
                self.position.cost += actual_cost
                self.position.avg_price = self.position.cost / self.position.size if self.position.size > 0 else 0
                self.position.strategy = strategy
                
                # 거래 기록
                self.transactions.insert(0, {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "side": "BUY",
                    "direction": direction,
                    "price": price,
                    "size": order_size,
                    "btc_price": btc_price,
                    "info": f"Edge: {edge:+.1f}%",
                })
                
                # 최근 5개만 유지
                self.transactions = self.transactions[:5]
                
                self._log_pnl(f"[BUY] {direction} {order_size:.2f} @ {price:.4f} (Cost: ${actual_cost:.2f}, Strategy: {strategy})")
                
                return True
            
            return False
            
        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("trading.log", "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [BUY ERROR] {e}\n")
            return False
    
    async def sell(
        self,
        direction: str,
        size: float = 0,
        btc_price: float = 0.0,
        pnl: float = 0.0
    ) -> bool:
        """
        Limit 주문 (SELL at best bid)
        
        Args:
            direction: "UP" or "DOWN"
            size: 주문 수량 (0이면 전체)
            btc_price: 현재 BTC 가격 (로깅용)
            pnl: 실현 손익 (로깅용)
        """
        if not self._clob_client:
            return False
        
        try:
            token_id = self.market.token_id_up if direction == "UP" else self.market.token_id_down
            price = self.market.up_bid if direction == "UP" else self.market.down_bid
            
            if not token_id or price <= 0:
                return False
            
            sell_size = size if size > 0 else self.position.size
            
            # Limit Order 실행 (GTC)
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=sell_size,
                side=SELL,
                order_type=OrderType.GTC,
            )
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(self._executor, self._clob_client.create_and_post_order, order_args)
            
            if response:
                proceeds = sell_size * price
                realized = proceeds - (sell_size * self.position.avg_price)
                
                self.realized_pnl += realized
                self.total_pnl = self.realized_pnl
                
                # 포지션 업데이트
                self.position.size -= sell_size
                self.position.cost = self.position.size * self.position.avg_price
                
                if self.position.size <= 0:
                    self.position = Position()
                
                # 거래 기록
                self.transactions.insert(0, {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "side": "SELL",
                    "direction": direction,
                    "price": price,
                    "size": sell_size,
                    "btc_price": btc_price,
                    "info": f"P&L: {'+' if realized >= 0 else ''}{realized:.2f}",
                })
                
                self.transactions = self.transactions[:5]
                
                self._log_pnl(f"[SELL] {direction} {sell_size:.2f} @ {price:.4f} (Realized PnL: {'+' if realized >= 0 else ''}{realized:.4f})")
                
                return True
            
            return False
            
        except Exception as e:
            self._log(f"[Polymarket] SELL 오류: {e}")
            return False
    
    async def execute_surebet(
        self,
        yes_size: float,
        yes_max_price: float,
        no_size: float,
        no_max_price: float,
        profit_rate: float = 0.0
    ) -> Dict:
        """
        Sure-Bet 원자적 실행 - YES와 NO 동시 매수
        
        Args:
            yes_size: YES 토큰 수량
            yes_max_price: YES 최대 가격 (슬리피지 포함)
            no_size: NO 토큰 수량
            no_max_price: NO 최대 가격 (슬리피지 포함)
            profit_rate: 예상 수익률 (로깅용)
            
        Returns:
            {
                "success": bool,
                "yes_filled": bool,
                "no_filled": bool,
                "panic_mode": bool,
                "message": str
            }
        """
        if not self._clob_client:
            return {
                "success": False,
                "yes_filled": False,
                "no_filled": False,
                "panic_mode": False,
                "message": "CLOB 클라이언트 미초기화"
            }
        
        self._log(f"[Sure-Bet] 실행 시작 - YES: {yes_size:.2f}@{yes_max_price:.4f}, NO: {no_size:.2f}@{no_max_price:.4f}")
        
        try:
            # 두 주문을 동시에 생성
            yes_order = OrderArgs(
                token_id=self.market.token_id_up,
                price=yes_max_price,
                size=yes_size,
                side=BUY,
            )
            
            no_order = OrderArgs(
                token_id=self.market.token_id_down,
                price=no_max_price,
                size=no_size,
                side=BUY,
            )
            
            # Use run_in_executor to make blocking calls non-blocking and parallel
            loop = asyncio.get_running_loop()
            
            future_yes = loop.run_in_executor(self._executor, self._clob_client.create_and_post_order, yes_order)
            future_no = loop.run_in_executor(self._executor, self._clob_client.create_and_post_order, no_order)
            
            # Run both in parallel
            results = await asyncio.gather(future_yes, future_no, return_exceptions=True)
            
            yes_result = results[0]
            no_result = results[1]
            
            yes_response = None
            no_response = None
            
            # Check results
            if isinstance(yes_result, Exception):
                self._log(f"[Sure-Bet] YES 주문 실패: {yes_result}")
            else:
                yes_response = yes_result
                
            if isinstance(no_result, Exception):
                self._log(f"[Sure-Bet] NO 주문 실패: {no_result}")
            else:
                no_response = no_result
            
            yes_filled = yes_response is not None
            no_filled = no_response is not None
            
            # 둘 다 성공
            if yes_filled and no_filled:
                # 거래 기록
                self.transactions.insert(0, {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "side": "SUREBET",
                    "direction": "YES+NO",
                    "price": yes_max_price + no_max_price,
                    "size": yes_size,
                    "btc_price": 0,
                    "info": f"Profit: +{profit_rate:.2f}%",
                })
                self.transactions = self.transactions[:5]
                
                self._log_pnl(f"[Sure-Bet] ✅ 성공! YES+NO 매수 완료. 수익률: +{profit_rate:.2f}% (YES: {yes_size:.2f}@{yes_max_price:.4f}, NO: {no_size:.2f}@{no_max_price:.4f})")
                return {
                    "success": True,
                    "yes_filled": True,
                    "no_filled": True,
                    "panic_mode": False,
                    "message": f"Sure-Bet 성공 (+{profit_rate:.2f}%)"
                }
            
            # 한쪽만 성공 - Panic Mode
            if yes_filled != no_filled:
                filled_side = "YES" if yes_filled else "NO"
                filled_size = yes_size if yes_filled else no_size
                
                self._log(f"[Sure-Bet] ⚠️ Panic Mode! {filled_side}만 체결됨")
                
                # Panic Mode 처리
                await self.handle_leg_failure(filled_side, filled_size)
                
                return {
                    "success": False,
                    "yes_filled": yes_filled,
                    "no_filled": no_filled,
                    "panic_mode": True,
                    "message": f"Panic Mode - {filled_side}만 체결"
                }
            
            # 둘 다 실패
            return {
                "success": False,
                "yes_filled": False,
                "no_filled": False,
                "panic_mode": False,
                "message": "양쪽 주문 모두 실패"
            }
            
        except Exception as e:
            self._log(f"[Sure-Bet] 실행 오류: {e}")
            return {
                "success": False,
                "yes_filled": False,
                "no_filled": False,
                "panic_mode": False,
                "message": f"오류: {e}"
            }
    
    async def handle_leg_failure(self, filled_side: str, filled_size: float) -> bool:
        """
        Panic Mode: 한쪽만 체결된 경우 처리
        
        전략: 체결된 쪽을 즉시 시장가 매도하여 손실 최소화
        
        Args:
            filled_side: "YES" or "NO"
            filled_size: 체결된 수량
        """
        self._log(f"[Panic Mode] {filled_side} {filled_size:.2f}주 즉시 청산 시도")
        
        try:
            if filled_side == "YES":
                token_id = self.market.token_id_up
                price = self.market.up_bid * 0.99  # 1% 할인하여 빠른 체결
            else:
                token_id = self.market.token_id_down
                price = self.market.down_bid * 0.99
            
            if price <= 0:
                self._log("[Panic Mode] 유효한 bid 가격 없음")
                return False
            
            # 즉시 매도 주문
            sell_order = OrderArgs(
                token_id=token_id,
                price=price,
                size=filled_size,
                side=SELL,
            )
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(self._executor, self._clob_client.create_and_post_order, sell_order)
            
            if response:
                self._log_pnl(f"[Panic Mode] ✅ 청산 성공 - {filled_side} {filled_size:.2f}주 @ {price:.4f} (손실 확정)")
                
                # 거래 기록
                self.transactions.insert(0, {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "side": "PANIC",
                    "direction": filled_side,
                    "price": price,
                    "size": filled_size,
                    "btc_price": 0,
                    "info": "Leg Risk 청산",
                })
                self.transactions = self.transactions[:5]
                
                return True
            
            self._log("[Panic Mode] 청산 실패")
            return False
            
        except Exception as e:
            self._log(f"[Panic Mode] 오류: {e}")
            return False

    
    def _check_payout_status_sync(self, contract, condition_id: str) -> Tuple[int, int]:
        """Synchronous helper to check payout status"""
        try:
            p0 = contract.functions.payoutNumerators(condition_id, 0).call()
            p1 = contract.functions.payoutNumerators(condition_id, 1).call()
            return p0, p1
        except Exception:
            return 0, 0

    async def merge_positions(self, condition_id: str, amount: float) -> bool:
        """
        YES/NO 포지션을 병합하여 USDC로 전환 (Async Wrapper)
        Args:
            condition_id: 마켓 Condition ID
            amount: 병합할 수량 (Share 단위)
        """
        loop = asyncio.get_running_loop()
        
        # Proxy 모드인 경우
        if self.proxy_address and self.proxy_address != self.address:
            return await loop.run_in_executor(self._executor, self._merge_proxy_sync, condition_id, amount)
            
        # EOA 모드인 경우
        return await loop.run_in_executor(self._executor, self._merge_market_sync, condition_id, amount)

    def _merge_market_sync(self, condition_id: str, amount: float) -> bool:
        """
        mergePositions 동기 구현체 (EOA Direct)
        """
        try:
            config = get_config()
            w3 = Web3(Web3.HTTPProvider(config.web3_rpc_url, request_kwargs={'timeout': 10}))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            
            if not w3.is_connected():
                return False
                
            # 컨트랙트 주소
            ctf_address = self._clob_client.get_conditional_address() if self._clob_client else None
            collateral = self._clob_client.get_collateral_address() if self._clob_client else None
            
            if not ctf_address or not collateral:
                ctf_address = "0x4D97DCd97eC945f40cF65F87097ACE5EA0476045"
                collateral = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
                
            contract = w3.eth.contract(address=ctf_address, abi=CTF_ABI)
            account = w3.eth.account.from_key(self.private_key)
            
            # Amount to Wei (USDC 6 decimals)
            amount_wei = int(amount * 1_000_000)
            index_sets = [1, 2] # YES, NO
            parent_collection_id = "0x" + "0" * 64
            
            # 트랜잭션 구성
            func = contract.functions.mergePositions(
                collateral,
                parent_collection_id,
                condition_id,
                index_sets,
                amount_wei
            )
            
            # 가스 견적
            try:
                gas_estimate = func.estimate_gas({'from': account.address})
            except Exception:
                return False
                
            tx = func.build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address, 'pending'),
                'gas': int(gas_estimate * 1.2),
                'gasPrice': w3.eth.gas_price,
            })
            
            signed_tx = w3.eth.account.sign_transaction(tx, self.private_key)
            time.sleep(1)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            self._log(f"[Merge] 병합 트랜잭션 전송됨: {w3.to_hex(tx_hash)}")
            
            time.sleep(2) # Wait a bit
            return True
                
        except Exception as e:
            self._log(f"[Merge] 실행 오류: {e}")
            return False

    def _merge_proxy_sync(self, condition_id: str, amount: float) -> bool:
        """
        mergePositions 동기 구현체 (Proxy via Safe)
        """
        try:
            config = get_config()
            w3 = Web3(Web3.HTTPProvider(config.web3_rpc_url, request_kwargs={'timeout': 10}))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            
            if not w3.is_connected():
                return False
                
            ctf_address = self._clob_client.get_conditional_address() if self._clob_client else "0x4D97DCd97eC945f40cF65F87097ACE5EA0476045"
            collateral = self._clob_client.get_collateral_address() if self._clob_client else "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
            
            ctf_contract = w3.eth.contract(address=ctf_address, abi=CTF_ABI)
            
            # Inner Transaction
            amount_wei = int(amount * 1_000_000)
            index_sets = [1, 2]
            parent_collection_id = "0x" + "0" * 64
            
            inner_func = ctf_contract.functions.mergePositions(
                collateral,
                parent_collection_id,
                condition_id,
                index_sets,
                amount_wei
            )
            inner_data = inner_func.build_transaction({'gas': 0})['data']
            
            # Proxy Transaction
            safe_address = self.proxy_address
            safe_contract = w3.eth.contract(address=safe_address, abi=GNOSIS_SAFE_ABI)
            
            account = w3.eth.account.from_key(self.private_key)
            nonce = safe_contract.functions.nonce().call()
            time.sleep(1)
            
            to = ctf_address
            value = 0
            data_bytes = bytes.fromhex(inner_data[2:]) if inner_data.startswith('0x') else inner_data
            operation = 0
            safe_tx_gas = 0
            base_gas = 0
            gas_price = 0
            gas_token = "0x0000000000000000000000000000000000000000"
            refund_receiver = "0x0000000000000000000000000000000000000000"
            
            # Sign
            eip712_data = {
                "types": {
                    "EIP712Domain": [{"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}],
                    "SafeTx": [
                        {"name": "to", "type": "address"}, {"name": "value", "type": "uint256"},
                        {"name": "data", "type": "bytes"}, {"name": "operation", "type": "uint8"},
                        {"name": "safeTxGas", "type": "uint256"}, {"name": "baseGas", "type": "uint256"},
                        {"name": "gasPrice", "type": "uint256"}, {"name": "gasToken", "type": "address"},
                        {"name": "refundReceiver", "type": "address"}, {"name": "nonce", "type": "uint256"}
                    ]
                },
                "primaryType": "SafeTx",
                "domain": {"chainId": 137, "verifyingContract": safe_address},
                "message": {
                    "to": to, "value": value, "data": data_bytes, "operation": operation,
                    "safeTxGas": safe_tx_gas, "baseGas": base_gas, "gasPrice": gas_price,
                    "gasToken": gas_token, "refundReceiver": refund_receiver, "nonce": nonce
                }
            }
            
            signed = Account.sign_typed_data(self.private_key, full_message=eip712_data)
            signature = signed.signature
            
            # Execute
            exec_func = safe_contract.functions.execTransaction(
                to, value, data_bytes, operation, safe_tx_gas, base_gas,
                gas_price, gas_token, refund_receiver, signature
            )
            
            try:
                time.sleep(1)
                gas_estimate = exec_func.estimate_gas({'from': account.address})
            except Exception as e:
                self._log(f"[Proxy Merge] Gas estimation failed: {e}")
                return False
                
            tx = exec_func.build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address, 'pending'),
                'gas': int(gas_estimate * 1.2),
                'gasPrice': w3.eth.gas_price
            })
            
            signed_tx = w3.eth.account.sign_transaction(tx, self.private_key)
            time.sleep(1)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            self._log(f"[Proxy Merge] 병합 트랜잭션 전송됨: {w3.to_hex(tx_hash)}")
            time.sleep(2)
            return True
            
        except Exception as e:
            self._log(f"[Proxy Merge] 실행 오류: {e}")
            return False

    async def redeem_all_resolved_positions(self) -> int:
        """Data API를 통해 모든 포지션을 조회하고, 정산 가능한 것들을 찾아 Redeem 실행"""
        # Config 확인
        if not get_config().auto_redeem_enabled:
            return 0

        target = self.proxy_address if self.proxy_address else self.address
        if not target or target == "Unknown":
            return 0
            
        self._log(f"[Redeem] 전체 포지션 스캔 시작 (On-chain Check)... User: {target}")
        # print(f"[Redeem] Scanning positions for {target}...") # Optional: direct stdout if needed
        redeemed_count = 0
        
        try:
            # Web3 연결 (On-chain 확인용)
            config = get_config()
            w3 = Web3(Web3.HTTPProvider(config.web3_rpc_url, request_kwargs={'timeout': 10}))
            
            # CTF Contract
            ctf_address = self._clob_client.get_conditional_address() if self._clob_client else "0x4D97DCd97eC945f40cF65F87097ACE5EA0476045"
            ctf_contract = w3.eth.contract(address=ctf_address, abi=CTF_ABI)

            url = "https://data-api.polymarket.com/positions"
            # API 필터 제거: 모든 포지션을 가져와서 직접 확인
            params = {
                "user": target,
                "limit": "500"
            }
            
            async with self._session.get(url, params=params) as resp:
                if resp.status != 200:
                    self._log(f"[Redeem] API 오류: {resp.status}")
                    return 0
                positions = await resp.json()
            
            if not positions or not isinstance(positions, list):
                self._log("[Redeem] 포지션 없음")
                return 0
                
            self._log(f"[Redeem] {len(positions)}개의 포지션 확인 중...")
            
            loop = asyncio.get_running_loop()

            for pos in positions:
                size = float(pos.get("size", 0))
                if size < 0.000001: continue # Dust skip
                
                condition_id = pos.get("conditionId")
                if not condition_id: continue
                
                market_slug = pos.get("marketSlug", "Unknown Market")
                
                # On-chain 상태 확인 (Non-blocking)
                try:
                    p0, p1 = await loop.run_in_executor(
                        self._executor, 
                        self._check_payout_status_sync, 
                        ctf_contract, 
                        condition_id
                    )
                    
                    # 아직 결과 안 나옴 (Active Market) -> 스킵
                    if p0 == 0 and p1 == 0:
                        continue
                        
                except Exception as e:
                    self._log(f"[Redeem Check] On-chain check failed for condition_id {condition_id[:10]}... Error: {e}")
                    continue

                self._log(f"[Redeem] 정산 시도: {market_slug} (Split: {p0}/{p1}) - {size} shares")

                # 가상의 마켓 데이터 생성하여 redeem_market 호출
                temp_market = MarketData(condition_id=condition_id)
                
                if await self.redeem_market(temp_market):
                    redeemed_count += 1
                    self._log(f"[Redeem] 정산 성공: {market_slug}")
                    await asyncio.sleep(2) # Extra delay after a write transaction
                
                # General throttling for checks
                await asyncio.sleep(0.2)
                    
            return redeemed_count
        except Exception as e:
            self._log(f"[Redeem] 전체 정산 스캔 중 오류: {e}")
            return redeemed_count

    async def sync_position_from_api(self) -> None:
        """API(Data Check)에서 포지션 동기화"""
        if not self.address or self.address == "Unknown":
            self._log("[Polymarket] EOA 주소가 없어 포지션을 동기화할 수 없습니다.")
            return

        try:
            url = "https://data-api.polymarket.com/positions"
            
            # Proxy 주소 우선 사용, 없으면 EOA
            target_address = self.proxy_address if self.proxy_address else self.address
            params = {"user": target_address}
            
            self._log(f"[Polymarket] 포지션 동기화 중 (Data API)... User: {target_address}")
            
            async with self._session.get(url, params=params) as resp:
                if resp.status != 200:
                    self._log(f"[Polymarket] Data API 오류: {resp.status}")
                    return
                
                positions = await resp.json()
                
            if not positions or not isinstance(positions, list):
                self.position = Position()
                self._log("[Polymarket] 활성 포지션 없음 (0)")
                return

            # 현재 마켓의 토큰 ID
            token_up = self.market.token_id_up
            token_down = self.market.token_id_down
            
            found = False
            
            for pos in positions:
                asset = pos.get("asset")
                size = float(pos.get("size", 0))
                
                if size <= 0:
                    continue
                
                # 현재 마켓과 일치하는지 확인
                if asset == token_up:
                    self.position.direction = "UP"
                    self.position.size = size
                    self.position.avg_price = float(pos.get("avgPrice", 0))
                    self.position.cost = self.position.size * self.position.avg_price
                    found = True
                    break
                elif asset == token_down:
                    self.position.direction = "DOWN"
                    self.position.size = size
                    self.position.avg_price = float(pos.get("avgPrice", 0))
                    self.position.cost = self.position.size * self.position.avg_price
                    found = True
                    break
            
            if found:
                self._log(f"[Polymarket] 포지션 동기화 완료: {self.position.direction} {self.position.size}주")
            else:
                self.position = Position()
                self._log("[Polymarket] 이 마켓에 대한 활성 포지션 없음")
                
        except Exception as e:
            self._log(f"[Polymarket] 포지션 동기화 실패: {e}")
    
    def update_unrealized_pnl(self) -> None:
        """미실현 손익 업데이트"""
        if self.position.size <= 0:
            self.position.unrealized_pnl = 0.0
            return
        
        current_price = (
            self.market.up_bid if self.position.direction == "UP"
            else self.market.down_bid
        )
        
        self.position.current_value = self.position.size * current_price
        self.position.unrealized_pnl = self.position.current_value - self.position.cost
        self.total_pnl = self.realized_pnl + self.position.unrealized_pnl
    
    @property
    def has_position(self) -> bool:
        """포지션 보유 여부"""
        return self.position.size > 0
    
    @property
    def is_initialized(self) -> bool:
        """초기화 상태"""
        return self._initialized


    async def get_usdc_balance(self) -> float:
        """USDC 잔고 조회"""
        if not self._clob_client:
            return 0.0
            
        try:
            resp = self._clob_client.get_balance_allowance(
                params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            )
            # USDC has 6 decimals
            raw_balance = float(resp.get("balance", 0))
            return raw_balance / 1_000_000
        except Exception as e:
            self._log(f"[Polymarket] 잔고 조회 오류: {e}")
            return 0.0

    async def get_global_invested_value(self) -> float:
        """Data API를 통해 모든 포지션을 조회하고, 투자 원금(Cost Basis) 합계 조회"""
        target = self.proxy_address if self.proxy_address else self.address
        if not target or target == "Unknown":
            return 0.0
            
        try:
            url = "https://data-api.polymarket.com/positions"
            params = {"user": target}
            
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    positions = await resp.json()
                    total_invested = 0.0
                    if isinstance(positions, list):
                        for p in positions:
                            size = float(p.get("size", 0))
                            price = float(p.get("avgPrice", 0))
                            total_invested += size * price
                    return total_invested
            return 0.0
        except Exception:
            return 0.0

    async def archive_current_market(self) -> None:
        """현재 마켓을 만료 목록에 보관 (나중에 정산하기 위함)"""
        if self.market.condition_id:
            # 값 복사해서 저장
            import copy
            old_market = copy.deepcopy(self.market)
            self.expired_markets.append(old_market)
            self._log(f"[Polymarket] 마켓 보관됨 (Condition: {old_market.condition_id[:10]}...) - 총 {len(self.expired_markets)}개 대기 중")

    async def redeem_market(self, market_data: Optional[MarketData] = None) -> bool:
        """
        마켓에 대해 CTF 컨트랙트를 통해 정산(Redeem) 실행 (Async Wrapper)
        Args:
            market_data: 정산할 마켓 데이터. None이면 현재 self.market 사용
        """
        loop = asyncio.get_running_loop()
        
        target_market = market_data if market_data else self.market
        if not target_market.condition_id:
            return False

        # Proxy 모드인 경우
        if self.proxy_address and self.proxy_address != self.address:
            return await loop.run_in_executor(self._executor, self._redeem_proxy_sync, target_market)
            
        # EOA 모드인 경우
        return await loop.run_in_executor(self._executor, self._redeem_market_sync, target_market)

    def _redeem_market_sync(self, market_data: Optional[MarketData] = None) -> bool:
        """
        redeem_market의 동기 구현체 (Web3 블로킹 호출 포함)
        """
        target_market = market_data if market_data else self.market
        
        if not target_market.condition_id:
            return False

        # Proxy 모드라면 Proxy를 통해 실행
        if self.proxy_address and self.proxy_address != self.address:
            return self._redeem_proxy_sync(target_market)
            
        try:
            config = get_config()
            # 타임아웃 설정 추가 (연결 10초)
            w3 = Web3(Web3.HTTPProvider(config.web3_rpc_url, request_kwargs={'timeout': 10}))
            
            # PoA Middleware Injection (For Polygon)
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            
            if not w3.is_connected():
                self._log("[Redeem] Web3 연결 실패")
                return False
                
            # 컨트랙트 주소 조회
            ctf_address = self._clob_client.get_conditional_address() if self._clob_client else None
            collateral = self._clob_client.get_collateral_address() if self._clob_client else None
            
            if not ctf_address or not collateral:
                # Fallback addresses if client not ready
                ctf_address = Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACE5EA0476045") # Mainnet CTF
                collateral = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174") # USDC
                
            contract = w3.eth.contract(address=ctf_address, abi=CTF_ABI)
            
            # 정산 가능 여부 확인 (payoutNumerators 확인)
            try:
                # index 0 확인
                p0 = contract.functions.payoutNumerators(target_market.condition_id, 0).call()
                p1 = contract.functions.payoutNumerators(target_market.condition_id, 1).call()
                
                if p0 == 0 and p1 == 0:
                    return False
            except Exception:
                return False
            
            # Redeem 실행
            account = w3.eth.account.from_key(self.private_key)
            
            index_sets = [1, 2]
            parent_collection_id = "0x" + "0" * 64
            
            # 트랜잭션 구성
            func = contract.functions.redeemPositions(
                collateral,
                parent_collection_id,
                target_market.condition_id,
                index_sets
            )
            
            # 가스 견적
            try:
                gas_estimate = func.estimate_gas({'from': account.address})
            except Exception:
                return True # 이미 처리됨
                
            # 트랜잭션 빌드
            tx = func.build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address, 'pending'),
                'gas': int(gas_estimate * 1.2),
                'gasPrice': w3.eth.gas_price,
            })
            
            # 서명 및 전송
            signed_tx = w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            self._log(f"[Redeem] 정산 트랜잭션 전송됨: {w3.to_hex(tx_hash)}")
            
            # 대기 (타임아웃 60초)
            try:
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                if receipt['status'] == 1:
                    self._log_pnl(f"[Redeem] ✅ 정산 성공! ({target_market.condition_id[:8]}...) - Transaction Confirmed")
                    return True
                else:
                    self._log("[Redeem] ❌ 정산 트랜잭션 실패")
                    return False
            except Exception as e:
                self._log(f"[Redeem] 트랜잭션 확인 시간 초과 (성공 가능성 있음): {e}")
                return True # 타임아웃이어도 트랜잭션은 전송되었으므로 성공으로 간주 가능
                
        except Exception as e:
            self._log(f"[Redeem] 실행 오류: {e}")
            return False

    def _redeem_proxy_sync(self, market_data: MarketData) -> bool:
        """Gnosis Safe(Proxy)를 통한 정산 실행 (동기 구현)
        
        Note: 이 기능을 사용하려면 EOA 지갑에 소량의 Polygon(MATIC)이 있어야 합니다. (가스비 용도)
        """
        try:
            config = get_config()
            # 타임아웃 설정 추가 (연결 10초)
            w3 = Web3(Web3.HTTPProvider(config.web3_rpc_url, request_kwargs={'timeout': 10}))
            
            # PoA Middleware Injection (For Polygon)
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            
            if not w3.is_connected():
                return False
                
            # 1. CTF Contract Data 구성
            ctf_address = self._clob_client.get_conditional_address() if self._clob_client else Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACE5EA0476045")
            collateral = self._clob_client.get_collateral_address() if self._clob_client else Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
            
            ctf_contract = w3.eth.contract(address=ctf_address, abi=CTF_ABI)
            
            # 정산 가능 여부 확인
            try:
                p0 = ctf_contract.functions.payoutNumerators(market_data.condition_id, 0).call()
                p1 = ctf_contract.functions.payoutNumerators(market_data.condition_id, 1).call()
                if p0 == 0 and p1 == 0:
                    return False
            except:
                return False

            # Inner Transaction (Redeem)
            index_sets = [1, 2]
            parent_collection_id = "0x" + "0" * 64
            inner_func = ctf_contract.functions.redeemPositions(
                collateral,
                parent_collection_id,
                market_data.condition_id,
                index_sets
            )
            inner_data = inner_func.build_transaction({'gas': 0})['data']
            
            # 2. Proxy(Safe) Transaction 구성
            safe_address = self.proxy_address
            safe_contract = w3.eth.contract(address=safe_address, abi=GNOSIS_SAFE_ABI)
            
            account = w3.eth.account.from_key(self.private_key)
            nonce = safe_contract.functions.nonce().call()
            time.sleep(1) # Prevent RPC Rate Limit
            
            # SafeTx parameters
            to = ctf_address
            value = 0
            data_bytes = bytes.fromhex(inner_data[2:]) if inner_data.startswith('0x') else inner_data
            operation = 0  # Call
            safe_tx_gas = 0
            base_gas = 0
            gas_price = 0
            gas_token = "0x0000000000000000000000000000000000000000"
            refund_receiver = "0x0000000000000000000000000000000000000000"
            
            # 3. EIP-712 Signature using sign_typed_data (Standard Way)
            eip712_data = {
                "types": {
                    "EIP712Domain": [
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"}
                    ],
                    "SafeTx": [
                        {"name": "to", "type": "address"},
                        {"name": "value", "type": "uint256"},
                        {"name": "data", "type": "bytes"},
                        {"name": "operation", "type": "uint8"},
                        {"name": "safeTxGas", "type": "uint256"},
                        {"name": "baseGas", "type": "uint256"},
                        {"name": "gasPrice", "type": "uint256"},
                        {"name": "gasToken", "type": "address"},
                        {"name": "refundReceiver", "type": "address"},
                        {"name": "nonce", "type": "uint256"}
                    ]
                },
                "primaryType": "SafeTx",
                "domain": {
                    "chainId": 137,
                    "verifyingContract": safe_address
                },
                "message": {
                    "to": to,
                    "value": value,
                    "data": data_bytes,
                    "operation": operation,
                    "safeTxGas": safe_tx_gas,
                    "baseGas": base_gas,
                    "gasPrice": gas_price,
                    "gasToken": gas_token,
                    "refundReceiver": refund_receiver,
                    "nonce": nonce
                }
            }
            
            # Sign typed data
            signed = Account.sign_typed_data(self.private_key, full_message=eip712_data)
            signature = signed.signature
            
            # 5. Execute Transaction
            exec_func = safe_contract.functions.execTransaction(
                to,
                value,
                data_bytes,
                operation,
                safe_tx_gas,
                base_gas,
                gas_price,
                gas_token,
                refund_receiver,
                signature
            )
            
            # Estimate Gas
            try:
                time.sleep(1) # Prevent RPC Rate Limit
                gas_estimate = exec_func.estimate_gas({'from': account.address})
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                self._log(f"[Proxy Redeem] Gas estimation failed for {market_data.condition_id[:10]}...\nError: {e}\nDetails: {error_details}")
                # Often fails if already redeemed or insufficient gas in EOA
                return False
                
            tx = exec_func.build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address, 'pending'),
                'gas': int(gas_estimate * 1.2),
                'gasPrice': w3.eth.gas_price
            })
            
            signed_tx = w3.eth.account.sign_transaction(tx, self.private_key)
            time.sleep(1) # Prevent RPC Rate Limit
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            self._log(f"[Proxy Redeem] 트랜잭션 전송됨: {w3.to_hex(tx_hash)}")
            
            # 대기 (타임아웃 60초)
            try:
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                if receipt['status'] == 1:
                    self._log_pnl(f"[Proxy Redeem] ✅ 정산 성공! ({market_data.condition_id[:8]}...) - Transaction Confirmed")
                    return True
                else:
                    self._log("[Proxy Redeem] ❌ 정산 트랜잭션 실패")
                    return False
            except Exception as e:
                self._log(f"[Proxy Redeem] 트랜잭션 확인 시간 초과 (성공 가능성 있음): {e}")
                return True
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._log(f"[Proxy Redeem] 실행 오류: {e}")
            return False
    # ========== Minimal ExchangeClient Interface Support ==========
    # These methods provide minimal implementation when used directly with the base class
    # For full interface support, use PolymarketExchangeAdapter from exchanges.adapters

    if HAS_CORE_INTERFACE:
        # These are stub implementations to satisfy the abstract methods
        # They are not meant to be used directly - use the adapter instead
        async def connect(self) -> bool:
            """Connect to exchange (stub - use adapter for full functionality)"""
            if not self._initialized:
                return await self.initialize()
            return True

        async def disconnect(self) -> None:
            """Disconnect from exchange"""
            await self.close()

        async def buy(self, symbol: str, size: float, price: float = None, order_type=None):
            """
            Buy method - Note: This has different signature than the legacy buy().
            For backward compatibility, use the legacy buy(direction, ...) method.
            For new interface, use PolymarketExchangeAdapter from exchanges.adapters.
            """
            raise NotImplementedError(
                "Use PolymarketExchangeAdapter from exchanges.adapters for the new interface, "
                "or use the legacy buy(direction, amount_usdc, size, ...) method"
            )

        async def sell(self, symbol: str, size: float, price: float = None, order_type=None):
            """
            Sell method - Note: This has different signature than the legacy sell().
            For backward compatibility, use the legacy sell(direction, size, ...) method.
            For new interface, use PolymarketExchangeAdapter from exchanges.adapters.
            """
            raise NotImplementedError(
                "Use PolymarketExchangeAdapter from exchanges.adapters for the new interface, "
                "or use the legacy sell(direction, size, ...) method"
            )

        async def cancel_order(self, order_id: str) -> bool:
            """Cancel order (not supported by Polymarket)"""
            return False

        async def get_position(self, symbol: str):
            """Get position (stub - use adapter for full functionality)"""
            if not self.has_position:
                return None
            # Return a minimal position object
            from core.interfaces.exchange_base import Position as CorePosition
            return CorePosition(
                symbol=symbol,
                side="LONG",
                size=self.position.size,
                entry_price=self.position.avg_price,
                current_price=self.market.up_bid,
                unrealized_pnl=self.position.unrealized_pnl,
                realized_pnl=self.realized_pnl,
                timestamp=time.time()
            )

        async def get_balance(self):
            """Get balance"""
            usdc_balance = await self.get_usdc_balance()
            return {"USDC": usdc_balance}

        async def get_order_status(self, order_id: str):
            """Get order status (Polymarket orders fill immediately)"""
            from core.interfaces.exchange_base import Order, OrderSide, OrderStatus
            return Order(
                order_id=order_id,
                symbol="",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                price=0.0,
                size=0.0,
                status=OrderStatus.FILLED
            )
