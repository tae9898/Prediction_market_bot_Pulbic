"""
BTC Polymarket ARB Bot - Web Interface (FastAPI)
"""

import asyncio
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from dataclasses import asdict
import os

from bot_core import TradingBot
from logger import get_logger

app = FastAPI(title="Polymarket Bot Dashboard")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Bot Instances
bot_instances: list[TradingBot] = []


def set_bot_instances(bots: list[TradingBot]):
    global bot_instances
    bot_instances = bots


def get_main_bot() -> TradingBot:
    if bot_instances:
        return bot_instances[0]
    return None


@app.get("/api/state")
async def get_state():
    """Get current bot state (Main bot + Global totals)"""
    main_bot = get_main_bot()
    if not main_bot:
        return {"error": "Bot not initialized"}

    # Convert dataclass to dict
    state_dict = asdict(main_bot.state)

    # Calculate Global Totals
    global_balance = sum(b.state.usdc_balance for b in bot_instances)
    global_equity = sum(b.state.portfolio_value for b in bot_instances)

    # Calculate Global PnL (Sum of pnl across all assets in all bots)
    global_pnl = 0.0
    for b in bot_instances:
        for asset in b.state.assets.values():
            global_pnl += asset.total_pnl

    state_dict["global_usdc_balance"] = global_balance
    state_dict["global_portfolio_value"] = global_equity
    state_dict["global_total_pnl"] = global_pnl

    # Add config info that might be useful for UI
    config_info = {
        "expiry_sniper_minutes_before": main_bot.config.expiry_sniper_minutes_before,
        "expiry_sniper_prob_threshold": main_bot.config.expiry_sniper_prob_threshold,
    }

    return JSONResponse(content={"state": state_dict, "config": config_info})


@app.get("/api/wallets")
async def get_wallets():
    """Get summary of all connected wallets"""
    if not bot_instances:
        return []

    wallets = []
    for bot in bot_instances:
        wallet_pnl = sum(asset.total_pnl for asset in bot.state.assets.values())
        wallets.append(
            {
                "id": bot.bot_id if bot.bot_id else "Main",
                "address": bot.state.wallet_address,
                "balance": bot.state.usdc_balance,
                "equity": bot.state.portfolio_value,
                "pnl": wallet_pnl,
                "active": bot._running,
            }
        )
    return JSONResponse(content=wallets)


@app.get("/api/history")
async def get_history(period: str = "all"):
    """Get portfolio history data (Main bot for now)"""
    bot = get_main_bot()
    if not bot or not bot.portfolio_manager:
        return {"error": "Bot/Portfolio not initialized"}

    data = await bot.portfolio_manager.fetch_portfolio_history(period)
    return JSONResponse(content=data)


@app.get("/api/portfolio/positions")
async def get_portfolio_positions():
    """Get current positions from Data API (Main bot for now)"""
    bot = get_main_bot()
    if not bot or not bot.portfolio_manager:
        return {"error": "Bot/Portfolio not initialized"}

    positions = await bot.portfolio_manager.get_current_positions()
    return JSONResponse(content=positions)


@app.get("/api/pnl/trades")
async def get_pnl_trades(wallet_id: str = "", asset: str = "", limit: int = 100):
    """Get recent trades from PnL database"""
    from models.pnl_database import get_pnl_db

    db = get_pnl_db()
    trades = db.get_trades(wallet_id=wallet_id, limit=limit, asset=asset)

    return JSONResponse(content=[asdict(t) for t in trades])


@app.get("/api/pnl/history")
async def get_pnl_history(wallet_id: str = "", hours: int = 24):
    """Get PnL history from database"""
    from models.pnl_database import get_pnl_db

    db = get_pnl_db()
    history = db.get_pnl_history(wallet_id=wallet_id, hours=hours)

    return JSONResponse(content=[asdict(h) for h in history])


@app.get("/api/pnl/strategies")
async def get_strategy_performance(wallet_id: str = ""):
    """Get performance metrics per strategy"""
    from models.pnl_database import get_pnl_db

    db = get_pnl_db()
    performance = db.get_strategy_performance(wallet_id=wallet_id)

    return JSONResponse(content=performance)


@app.get("/api/pnl/stats")
async def get_pnl_stats(wallet_id: str = ""):
    """Get overall PnL statistics"""
    from models.pnl_database import get_pnl_db

    db = get_pnl_db()
    stats = db.get_stats(wallet_id=wallet_id)

    return JSONResponse(content=stats)


@app.get("/api/logs/recent")
async def get_recent_logs(wallet_id: str = "", lines: int = 100):
    """Get recent trading log lines"""
    bot = get_main_bot()
    if not bot:
        return {"error": "Bot not initialized"}

    logger = get_logger(wallet_id)
    logs = logger.get_recent_trading_logs(lines=lines)

    return JSONResponse(content=logs)


# @app.post("/api/toggle_auto")
# async def toggle_auto_trade():
#     """Toggle auto trading"""
#     if not bot_instance:
#         return {"error": "Bot not initialized"}
#
#     bot_instance.state.auto_trade = not bot_instance.state.auto_trade
#     return {"auto_trade": bot_instance.state.auto_trade}

# @app.post("/api/stop")
# async def stop_bot():
#     """Stop the bot"""
#     if bot_instance:
#         bot_instance._running = False
#     return {"status": "stopping"}

# Serve React App (if built)
# We will create a 'web/dist' folder later
if os.path.exists("web/dist"):
    app.mount("/", StaticFiles(directory="web/dist", html=True), name="static")
else:

    @app.get("/")
    def read_root():
        return {
            "message": "Web Dashboard is under construction. Please build the frontend."
        }


async def run_web(bot: TradingBot, host="0.0.0.0", port=8000):
    """Run Web Server"""
    set_bot_instance(bot)

    # Start bot tasks if not already started
    # Note: If running with CLI, tasks are started there.
    # If running Web only, we need to start them here.
    if not bot._running:
        await bot.start()

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    # Run server
    try:
        await server.serve()
    finally:
        bot._running = False
