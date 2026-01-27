"""
Pydantic models for API responses
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


class WalletInfo(BaseModel):
    """Wallet information"""
    id: str = Field(..., description="Wallet ID")
    address: str = Field(..., description="Wallet address")
    usdc_balance: float = Field(..., description="Available USDC balance")
    reserved_balance: float = Field(default=0.0, description="Reserved/committed balance")
    portfolio_value: float = Field(..., description="Total portfolio value (cash + positions)")
    is_connected: bool = Field(default=False, description="Connection status")
    auto_trade: bool = Field(default=False, description="Auto-trading enabled")


class PositionInfo(BaseModel):
    """Position information"""
    wallet_id: str = Field(..., description="Wallet ID")
    asset: str = Field(..., description="Asset symbol (BTC, ETH)")
    market: str = Field(..., description="Market title")
    side: str = Field(..., description="Position side (UP/DOWN)")
    size: float = Field(..., description="Position size")
    avg_price: float = Field(..., description="Average entry price")
    cur_price: float = Field(..., description="Current market price")
    cost: float = Field(..., description="Total cost basis")
    current_value: float = Field(..., description="Current value")
    pnl: float = Field(..., description="Unrealized PnL")
    pnl_pct: float = Field(..., description="PnL percentage")
    strategy: str = Field(default="", description="Strategy that created position")
    entry_prob: float = Field(default=0.0, description="Entry probability")


class MarketData(BaseModel):
    """Market data for an asset"""
    asset: str = Field(..., description="Asset symbol")
    price: float = Field(..., description="Current price")
    change_24h: float = Field(..., description="24h price change")
    change_pct: float = Field(..., description="24h price change %")
    volatility: float = Field(..., description="Volatility")
    momentum: str = Field(..., description="Momentum indicator")

    # Polymarket data
    strike_price: float = Field(..., description="Option strike price")
    time_remaining: str = Field(..., description="Time remaining formatted")
    time_remaining_sec: int = Field(..., description="Time remaining in seconds")

    # Market prices
    up_ask: float = Field(..., description="UP token ask price")
    up_bid: float = Field(..., description="UP token bid price")
    down_ask: float = Field(..., description="DOWN token ask price")
    down_bid: float = Field(..., description="DOWN token bid price")
    spread: float = Field(..., description="Bid-ask spread")

    # Probability analysis
    fair_up: float = Field(..., description="Fair value UP probability")
    fair_down: float = Field(..., description="Fair value DOWN probability")
    edge_up: float = Field(..., description="Edge on UP side")
    edge_down: float = Field(..., description="Edge on DOWN side")
    d2: float = Field(..., description="D2 indicator")

    # Surebet opportunity
    surebet_profitable: bool = Field(default=False, description="Surebet available")
    surebet_profit_rate: float = Field(default=0.0, description="Surebet profit rate %")

    # Signal
    signal: str = Field(default="WAITING", description="Current signal")


class PnLRecord(BaseModel):
    """PnL record from database"""
    id: int
    timestamp: float
    wallet_id: str
    asset: str
    asset_name: str
    direction: str
    size: float
    price: float
    cost: float
    strategy: str
    is_exit: bool
    realized_pnl: float
    condition_id: str


class PnLSnapshot(BaseModel):
    """PnL snapshot for history"""
    id: int
    timestamp: float
    wallet_id: str
    asset: str
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    position_size: float
    portfolio_value: float


class PerformanceStats(BaseModel):
    """Performance statistics"""
    wallet_id: str
    total_trades: int
    total_realized_pnl: float
    win_count: int
    loss_count: int
    win_rate: float
    avg_pnl: float


class StrategyPerformance(BaseModel):
    """Strategy-specific performance"""
    strategy: str
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    total_pnl: float
    avg_pnl: float


class SignalEvent(BaseModel):
    """Trading signal event"""
    timestamp: float
    asset: str
    signal: str
    direction: Optional[str] = None
    edge: Optional[float] = None
    probability: Optional[float] = None
    reason: Optional[str] = None


class BotStatus(BaseModel):
    """Overall bot status"""
    is_running: bool
    wallet_count: int
    total_portfolio_value: float
    total_usdc: float
    total_invested: float
    total_pnl: float
    update_count: int
    last_update: str
    logs: List[str]


class PortfolioSnapshot(BaseModel):
    """Portfolio value snapshot"""
    timestamp: float
    date_str: str
    usdc_balance: float
    invested_value: float
    total_value: float


class WebSocketMessage(BaseModel):
    """WebSocket message wrapper"""
    type: str = Field(..., description="Message type: state, trade, signal, error")
    data: Dict[str, Any] = Field(default_factory=dict, description="Message payload")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())


class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error info")
