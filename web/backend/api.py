"""
FastAPI Backend for Trading Bot
Provides REST API and WebSocket for real-time monitoring and control
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from web.backend.models import (
    WalletInfo,
    PositionInfo,
    MarketData,
    PnLRecord,
    PnLSnapshot,
    PerformanceStats,
    StrategyPerformance,
    SignalEvent,
    BotStatus,
    PortfolioSnapshot,
    WebSocketMessage,
    ErrorResponse,
)

# Global engine reference (will be set by main app)
_trading_engine = None


def set_trading_engine(engine):
    """Set the global trading engine reference"""
    global _trading_engine
    _trading_engine = engine


def get_engine():
    """Get the trading engine instance"""
    if _trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    return _trading_engine


# Create FastAPI app
app = FastAPI(
    title="Trading Bot API",
    description="Real-time monitoring and control API for automated trading bot",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections.remove(conn)

    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception:
            pass


manager = ConnectionManager()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Trading Bot API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "wallets": "/api/wallets",
            "positions": "/api/positions",
            "performance": "/api/performance",
            "signals": "/api/signals",
            "markets": "/api/markets",
            "status": "/api/status",
            "portfolio": "/api/portfolio",
            "websocket": "/ws",
        },
    }


@app.get("/api/status")
async def get_status() -> BotStatus:
    """Get overall bot status"""
    engine = get_engine()

    # Get first bot's state for overall status
    first_bot = next(iter(engine.bots.values()), None)
    if not first_bot:
        return BotStatus(
            is_running=False,
            wallet_count=0,
            total_portfolio_value=0.0,
            total_usdc=0.0,
            total_invested=0.0,
            total_pnl=0.0,
            update_count=0,
            last_update=datetime.now().strftime("%H:%M:%S"),
            logs=[],
        )

    state = first_bot.state

    # Aggregate across all wallets
    total_value = 0.0
    total_usdc = 0.0
    total_pnl = 0.0

    for bot in engine.bots.values():
        total_value += bot.state.portfolio_value
        total_usdc += bot.state.usdc_balance
        total_pnl += sum(
            asset_state.total_pnl for asset_state in bot.state.assets.values()
        )

    return BotStatus(
        is_running=engine._running,
        wallet_count=len(engine.bots),
        total_portfolio_value=total_value,
        total_usdc=total_usdc,
        total_invested=total_value - total_usdc,
        total_pnl=total_pnl,
        update_count=state.update_count,
        last_update=state.last_update,
        logs=state.logs[-20:],  # Last 20 log entries
    )


@app.get("/api/wallets")
async def get_wallets() -> List[WalletInfo]:
    """Get all wallets with status"""
    engine = get_engine()
    wallets = []

    for bot_id, bot in engine.bots.items():
        state = bot.state
        wallets.append(
            WalletInfo(
                id=bot_id,
                address=state.wallet_address,
                usdc_balance=state.usdc_balance,
                reserved_balance=state.reserved_balance,
                portfolio_value=state.portfolio_value,
                is_connected=state.is_connected,
                auto_trade=state.auto_trade,
            )
        )

    return wallets


@app.get("/api/wallets/{wallet_id}")
async def get_wallet(wallet_id: str) -> WalletInfo:
    """Get specific wallet details"""
    engine = get_engine()

    if wallet_id not in engine.bots:
        raise HTTPException(status_code=404, detail=f"Wallet {wallet_id} not found")

    bot = engine.bots[wallet_id]
    state = bot.state

    return WalletInfo(
        id=wallet_id,
        address=state.wallet_address,
        usdc_balance=state.usdc_balance,
        reserved_balance=state.reserved_balance,
        portfolio_value=state.portfolio_value,
        is_connected=state.is_connected,
        auto_trade=state.auto_trade,
    )


@app.get("/api/positions")
async def get_positions(wallet_id: Optional[str] = None) -> List[PositionInfo]:
    """Get all positions across wallets"""
    engine = get_engine()
    positions = []

    bots_to_check = {wallet_id: engine.bots[wallet_id]} if wallet_id else engine.bots

    for bot_id, bot in bots_to_check.items():
        for asset_name, asset_state in bot.state.assets.items():
            if asset_state.has_position:
                pm = bot.polymarkets.get(asset_name)
                if not pm:
                    continue

                positions.append(
                    PositionInfo(
                        wallet_id=bot_id,
                        asset=asset_name,
                        market=f"{asset_name} Hourly",
                        side=asset_state.position_direction,
                        size=asset_state.position_size,
                        avg_price=asset_state.position_avg_price,
                        cur_price=pm.market.up_bid
                        if asset_state.position_direction == "UP"
                        else pm.market.down_bid,
                        cost=asset_state.position_cost,
                        current_value=asset_state.position_cost + asset_state.position_pnl,
                        pnl=asset_state.position_pnl,
                        pnl_pct=(
                            (asset_state.position_pnl / asset_state.position_cost * 100)
                            if asset_state.position_cost > 0
                            else 0
                        ),
                        strategy=asset_state.position_strategy,
                        entry_prob=asset_state.position_entry_prob,
                    )
                )

    return positions


@app.get("/api/markets")
async def get_markets(wallet_id: Optional[str] = None) -> List[MarketData]:
    """Get market data for all assets"""
    engine = get_engine()
    markets = []

    bots_to_check = {wallet_id: engine.bots[wallet_id]} if wallet_id else engine.bots

    for bot_id, bot in bots_to_check.items():
        for asset_name, asset_state in bot.state.assets.items():
            markets.append(
                MarketData(
                    asset=asset_name,
                    price=asset_state.price,
                    change_24h=asset_state.change_24h,
                    change_pct=asset_state.change_pct,
                    volatility=asset_state.volatility,
                    momentum=asset_state.momentum,
                    strike_price=asset_state.strike_price,
                    time_remaining=asset_state.time_remaining,
                    time_remaining_sec=asset_state.time_remaining_sec,
                    up_ask=asset_state.up_ask,
                    up_bid=asset_state.up_bid,
                    down_ask=asset_state.down_ask,
                    down_bid=asset_state.down_bid,
                    spread=asset_state.spread,
                    fair_up=asset_state.fair_up,
                    fair_down=asset_state.fair_down,
                    edge_up=asset_state.edge_up,
                    edge_down=asset_state.edge_down,
                    d2=asset_state.d2,
                    surebet_profitable=asset_state.surebet_profitable,
                    surebet_profit_rate=asset_state.surebet_profit_rate,
                    signal=asset_state.signal,
                )
            )

    return markets


@app.get("/api/performance")
async def get_performance(
    wallet_id: Optional[str] = None,
    hours: int = Query(24, description="Hours of history to fetch"),
) -> Dict[str, Any]:
    """Get PnL history and performance stats"""
    engine = get_engine()

    # Get PnL database
    pnl_db = next(iter(engine.bots.values())).pnl_db if engine.bots else None
    if not pnl_db:
        return {"snapshots": [], "stats": {}, "strategy_performance": {}}

    # Get PnL history
    snapshots = pnl_db.get_pnl_history(wallet_id=wallet_id or "", hours=hours)
    snapshot_models = [
        PnLSnapshot(
            id=s.id,
            timestamp=s.timestamp,
            wallet_id=s.wallet_id,
            asset=s.asset,
            total_pnl=s.total_pnl,
            realized_pnl=s.realized_pnl,
            unrealized_pnl=s.unrealized_pnl,
            position_size=s.position_size,
            portfolio_value=s.portfolio_value,
        )
        for s in snapshots
    ]

    # Get stats
    stats = pnl_db.get_stats(wallet_id=wallet_id or "")

    # Get strategy performance
    strategy_perf = pnl_db.get_strategy_performance(wallet_id=wallet_id or "")
    strategy_models = [
        StrategyPerformance(
            strategy=strategy,
            trade_count=data["trade_count"],
            win_count=data["win_count"],
            loss_count=data["loss_count"],
            win_rate=data["win_rate"],
            total_pnl=data["total_pnl"],
            avg_pnl=data["avg_pnl"],
        )
        for strategy, data in strategy_perf.items()
    ]

    return {
        "snapshots": snapshot_models,
        "stats": stats,
        "strategy_performance": strategy_models,
    }


@app.get("/api/signals")
async def get_signals(
    limit: int = Query(50, description="Number of recent signals"),
) -> List[Dict[str, Any]]:
    """Get recent trading signals from logs"""
    engine = get_engine()
    signals = []

    for bot in engine.bots.values():
        for log in bot.state.logs:
            # Parse signal from logs
            if any(keyword in log for keyword in ["Signal", "SUREBET", "SNIPER", "Entry", "Hedge"]):
                signals.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "wallet_id": bot.bot_id,
                        "message": log,
                    }
                )

    # Sort by most recent and limit
    signals = sorted(signals, key=lambda x: x["timestamp"], reverse=True)[:limit]
    return signals


@app.get("/api/portfolio")
async def get_portfolio_history(
    wallet_id: Optional[str] = None,
    period: str = Query("7d", description="Time period: 1d, 7d, all"),
) -> List[PortfolioSnapshot]:
    """Get portfolio value history"""
    engine = get_engine()

    bot = next(iter(engine.bots.values()), None)
    if not bot or not bot.portfolio_manager:
        return []

    history = await bot.portfolio_manager.fetch_portfolio_history(period=period)

    return [
        PortfolioSnapshot(
            timestamp=h["timestamp"],
            date_str=h["date_str"],
            usdc_balance=h["usdc_balance"],
            invested_value=h["invested_value"],
            total_value=h["total_value"],
        )
        for h in history
    ]


@app.post("/api/wallets/{wallet_id}/toggle-auto-trade")
async def toggle_auto_trade(wallet_id: str) -> Dict[str, Any]:
    """Toggle auto-trading for a wallet"""
    engine = get_engine()

    if wallet_id not in engine.bots:
        raise HTTPException(status_code=404, detail=f"Wallet {wallet_id} not found")

    bot = engine.bots[wallet_id]
    bot.state.auto_trade = not bot.state.auto_trade

    return {
        "wallet_id": wallet_id,
        "auto_trade": bot.state.auto_trade,
        "message": f"Auto-trade {'enabled' if bot.state.auto_trade else 'disabled'}",
    }


@app.get("/api/trades")
async def get_trades(
    wallet_id: Optional[str] = None,
    asset: Optional[str] = None,
    limit: int = Query(100, description="Maximum number of trades"),
) -> List[PnLRecord]:
    """Get trade history"""
    engine = get_engine()

    pnl_db = next(iter(engine.bots.values())).pnl_db if engine.bots else None
    if not pnl_db:
        return []

    trades = pnl_db.get_trades(wallet_id=wallet_id or "", asset=asset or "", limit=limit)

    return [
        PnLRecord(
            id=t.id,
            timestamp=t.timestamp,
            wallet_id=t.wallet_id,
            asset=t.asset,
            asset_name=t.asset_name,
            direction=t.direction,
            size=t.size,
            price=t.price,
            cost=t.cost,
            strategy=t.strategy,
            is_exit=t.is_exit,
            realized_pnl=t.realized_pnl,
            condition_id=t.condition_id,
        )
        for t in trades
    ]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)

    try:
        # Send initial state
        engine = get_engine()
        if engine.bots:
            first_bot = next(iter(engine.bots.values()))
            await websocket.send_json(
                {
                    "type": "connected",
                    "data": {
                        "message": "Connected to trading bot",
                        "wallet_count": len(engine.bots),
                    },
                    "timestamp": datetime.now().timestamp(),
                }
            )

        # Keep connection alive and broadcast updates
        while True:
            try:
                # Receive any messages from client (ping/pong, commands)
                data = await websocket.receive_text()

                # Handle client commands
                try:
                    message = json.loads(data)
                    await handle_websocket_command(websocket, message)
                except json.JSONDecodeError:
                    # Ignore invalid JSON
                    pass

            except WebSocketDisconnect:
                break

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


async def handle_websocket_command(websocket: WebSocket, message: dict):
    """Handle commands received via WebSocket"""
    command = message.get("command")

    if command == "ping":
        await websocket.send_json(
            {
                "type": "pong",
                "timestamp": datetime.now().timestamp(),
            }
        )

    elif command == "get_state":
        engine = get_engine()
        if engine.bots:
            first_bot = next(iter(engine.bots.values()))
            state = first_bot.state

            await websocket.send_json(
                {
                    "type": "state",
                    "data": {
                        "auto_trade": state.auto_trade,
                        "usdc_balance": state.usdc_balance,
                        "portfolio_value": state.portfolio_value,
                        "assets": {
                            name: {
                                "price": asset.price,
                                "signal": asset.signal,
                                "has_position": asset.has_position,
                                "position_pnl": asset.position_pnl,
                            }
                            for name, asset in state.assets.items()
                        },
                    },
                    "timestamp": datetime.now().timestamp(),
                }
            )

    elif command == "toggle_auto_trade":
        wallet_id = message.get("wallet_id")
        engine = get_engine()

        if wallet_id and wallet_id in engine.bots:
            bot = engine.bots[wallet_id]
            bot.state.auto_trade = not bot.state.auto_trade

            await websocket.send_json(
                {
                    "type": "auto_trade_toggled",
                    "data": {
                        "wallet_id": wallet_id,
                        "auto_trade": bot.state.auto_trade,
                    },
                    "timestamp": datetime.now().timestamp(),
                }
            )


# Background task to broadcast state updates
async def broadcast_state_updates():
    """Broadcast state updates to all connected WebSocket clients"""
    while True:
        try:
            if manager.active_connections and _trading_engine:
                # Get current state
                first_bot = next(iter(_trading_engine.bots.values()), None)
                if first_bot:
                    state = first_bot.state

                    # Broadcast compact state update
                    await manager.broadcast(
                        {
                            "type": "state_update",
                            "data": {
                                "usdc_balance": state.usdc_balance,
                                "portfolio_value": state.portfolio_value,
                                "assets": {
                                    name: {
                                        "price": asset.price,
                                        "signal": asset.signal,
                                        "has_position": asset.has_position,
                                        "position_pnl": asset.position_pnl,
                                    }
                                    for name, asset in state.assets.items()
                                },
                            },
                            "timestamp": datetime.now().timestamp(),
                        }
                    )

        except Exception as e:
            print(f"Broadcast error: {e}")

        await asyncio.sleep(1)  # Update every second


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "engine_initialized": _trading_engine is not None,
    }
