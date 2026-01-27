"""
BTC Polymarket ARB Bot V3 - Binance WebSocket Feed
Binance WebSocket을 통한 실시간 BTC 가격 및 변동성 데이터 수신

Can be used with DataFeed interface from core.interfaces.data_feed_base
"""

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Deque, Tuple, Callable, Dict, Any
import numpy as np

# Import core interfaces (optional - for adapter pattern)
try:
    from core.interfaces.data_feed_base import DataFeed as BaseDataFeed
    HAS_CORE_INTERFACE = True
except (ImportError, ModuleNotFoundError):
    BaseDataFeed = object
    HAS_CORE_INTERFACE = False

try:
    import websockets
except ImportError:
    print("[ERROR] websockets 패키지가 필요합니다: pip install websockets")
    raise


@dataclass
class BinanceData:
    """Binance 데이터 상태"""
    price: float = 0.0
    price_change_24h: float = 0.0
    price_change_pct_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    volume_24h: float = 0.0
    last_update: float = 0.0
    
    # 가격 히스토리 (변동성 계산용)
    price_history: Deque[Tuple[float, float]] = field(
        default_factory=lambda: deque(maxlen=3600)  # 1시간 데이터 (1초당 1개)
    )


class BinanceFeed(BaseDataFeed if HAS_CORE_INTERFACE else object):
    """
    Binance WebSocket 실시간 피드 관리자

    When core.interfaces.data_feed_base.DataFeed is available, this class
    can be wrapped with BinanceFeedAdapter to provide the universal interface.

    For direct use with the new interface, use:
        from exchanges.adapters import BinanceFeedAdapter, create_binance_adapter
        adapter = create_binance_adapter(symbol="BTC")
        data = await adapter.get_market_data("BTC")
    """

    WS_URL = "wss://stream.binance.com:9443/ws"

    def __init__(self, symbol: str = "BTC", volatility_window_minutes: int = 60):
        # Initialize base class if available
        if HAS_CORE_INTERFACE:
            from core.interfaces.data_feed_base import DataFeedConfig
            config = DataFeedConfig(
                name=f"binance_{symbol.upper()}",
                enable_websocket=True,
                symbols=[symbol.upper()]
            )
            super().__init__(config=config, logger=None)

        self.symbol = symbol.upper()
        self._symbol_pair = f"{self.symbol.lower()}usdt"
        self.TRADE_STREAM = f"{self._symbol_pair}@trade"
        self.TICKER_STREAM = f"{self._symbol_pair}@ticker"

        self.data = BinanceData()
        self.volatility_window = volatility_window_minutes * 60  # 초 단위
        self._ws = None
        self._running = False
        self._reconnect_delay = 1.0
        self._on_price_update: Optional[Callable] = None
        self._update_count = 0
        
    def set_price_callback(self, callback: Callable) -> None:
        """가격 업데이트 콜백 설정"""
        self._on_price_update = callback
    
    async def start(self) -> None:
        """WebSocket 연결 시작"""
        self._running = True
        while self._running:
            try:
                await self._connect()
            except Exception as e:
                if self._running:
                    print(f"[Binance] 연결 오류: {e}, {self._reconnect_delay}초 후 재연결...")
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, 30)
    
    async def stop(self) -> None:
        """WebSocket 연결 중지"""
        self._running = False
        if self._ws:
            await self._ws.close()
    
    async def _connect(self) -> None:
        """WebSocket 연결 및 스트림 구독"""
        streams = f"{self.TRADE_STREAM}/{self.TICKER_STREAM}"
        url = f"{self.WS_URL}/{streams}"
        
        async with websockets.connect(url, ping_interval=20) as ws:
            self._ws = ws
            self._reconnect_delay = 1.0  # 연결 성공 시 리셋
            
            async for message in ws:
                if not self._running:
                    break
                await self._handle_message(message)
    
    async def _handle_message(self, message: str) -> None:
        """수신 메시지 처리"""
        try:
            data = json.loads(message)
            event_type = data.get("e")
            
            if event_type == "trade":
                await self._handle_trade(data)
            elif event_type == "24hrTicker":
                await self._handle_ticker(data)
                
        except json.JSONDecodeError:
            pass
    
    async def _handle_trade(self, data: dict) -> None:
        """실시간 거래 가격 처리"""
        price = float(data.get("p", 0))
        timestamp = time.time()
        
        self.data.price = price
        self.data.last_update = timestamp
        self.data.price_history.append((timestamp, price))
        self._update_count += 1
        
        if self._on_price_update:
            await self._on_price_update(price)
    
    async def _handle_ticker(self, data: dict) -> None:
        """24시간 티커 정보 처리"""
        self.data.price_change_24h = float(data.get("p", 0))
        self.data.price_change_pct_24h = float(data.get("P", 0))
        self.data.high_24h = float(data.get("h", 0))
        self.data.low_24h = float(data.get("l", 0))
        self.data.volume_24h = float(data.get("v", 0))
    
    def get_price(self) -> float:
        """현재 BTC 가격 반환"""
        return self.data.price
    
    def get_24h_stats(self) -> dict:
        """24시간 통계 반환"""
        return {
            "change": self.data.price_change_24h,
            "change_pct": self.data.price_change_pct_24h,
            "high": self.data.high_24h,
            "low": self.data.low_24h,
            "volume": self.data.volume_24h,
        }
    
    def calculate_volatility(self) -> float:
        """
        실시간 변동성 계산 (연간화)
        
        로그 수익률의 표준편차를 연간화하여 반환
        Returns: 연간 변동성 (0.0 ~ 2.0 범위)
        """
        if len(self.data.price_history) < 10:
            return 0.60  # 기본값 60%
        
        # 최근 window 데이터만 사용
        now = time.time()
        cutoff = now - self.volatility_window
        
        prices = []
        timestamps = []
        for ts, price in self.data.price_history:
            if ts >= cutoff:
                prices.append(price)
                timestamps.append(ts)
        
        if len(prices) < 10:
            return 0.60
        
        # 로그 수익률 계산
        prices_arr = np.array(prices)
        log_returns = np.diff(np.log(prices_arr))
        
        if len(log_returns) < 2:
            return 0.60
        
        # 평균 시간 간격 계산
        avg_interval = (timestamps[-1] - timestamps[0]) / len(timestamps)
        if avg_interval <= 0:
            avg_interval = 1.0
        
        # 수익률의 표준편차
        std_return = np.std(log_returns)
        
        # 연간화 (365.25일 × 24시간 × 3600초)
        intervals_per_year = (365.25 * 24 * 3600) / avg_interval
        annualized_vol = std_return * np.sqrt(intervals_per_year)
        
        # 합리적 범위로 제한 (10% ~ 200%)
        return max(0.10, min(2.0, annualized_vol))
    
    def get_momentum(self) -> str:
        """
        모멘텀 지표 계산
        
        최근 1분 가격 변화를 기반으로 방향성 판단
        Returns: 'BULLISH', 'BEARISH', 또는 'NEUTRAL'
        """
        if len(self.data.price_history) < 60:
            return "NEUTRAL"
        
        now = time.time()
        cutoff = now - 60  # 최근 1분
        
        recent_prices = [p for ts, p in self.data.price_history if ts >= cutoff]
        
        if len(recent_prices) < 2:
            return "NEUTRAL"
        
        change_pct = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
        
        if change_pct > 0.05:
            return "BULLISH"
        elif change_pct < -0.05:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def get_volatility_bar(self, width: int = 10) -> str:
        """변동성을 시각적 바로 표현"""
        vol = self.calculate_volatility()
        vol_pct = min(vol / 1.0, 1.0)  # 100%를 최대로
        filled = int(vol_pct * width)
        return "█" * filled + "░" * (width - filled)
    
    @property
    def update_count(self) -> int:
        """업데이트 카운트 반환"""
        return self._update_count
    
    @property
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._ws is not None and self._running

    # ========== Minimal DataFeed Interface Support ==========
    # These methods provide minimal implementation when used directly with the base class
    # For full interface support, use BinanceFeedAdapter from exchanges.adapters

    if HAS_CORE_INTERFACE:
        async def connect(self) -> bool:
            """Connect to Binance WebSocket"""
            if self._connected:
                return True
            try:
                asyncio.create_task(self.start())
                await asyncio.sleep(0.5)
                return self.is_connected
            except Exception:
                return False

        async def disconnect(self) -> None:
            """Disconnect from Binance"""
            await self.stop()
            self._connected = False

        async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
            """Get market data for symbol"""
            if symbol.upper() != self.symbol.upper():
                return None
            return {
                "symbol": self.symbol,
                "price": self.data.price,
                "volume_24h": self.data.volume_24h,
                "change_24h": self.data.price_change_24h,
                "change_pct_24h": self.data.price_change_pct_24h,
                "high_24h": self.data.high_24h,
                "low_24h": self.data.low_24h,
                "timestamp": self.data.last_update,
                "volatility": self.calculate_volatility(),
                "momentum": self.get_momentum()
            }

        async def get_orderbook(self, symbol: str, limit: int = 10) -> Optional[Dict[str, Any]]:
            """Get orderbook for symbol (placeholder)"""
            if symbol.upper() != self.symbol.upper():
                return None
            return {
                "symbol": symbol,
                "bids": [{"price": self.data.price * 0.999, "size": 10.0}],
                "asks": [{"price": self.data.price * 1.001, "size": 10.0}],
                "timestamp": time.time()
            }

    # Add connection state tracking
    _connected = False
