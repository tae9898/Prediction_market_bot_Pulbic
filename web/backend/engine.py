"""
Trading Engine Manager
Manages multiple bot instances and provides interface for API
"""

import asyncio
import os
from typing import Dict, Optional
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from feature_source.bot_core import TradingBot
from feature_source.config import get_config


class TradingEngine:
    """
    Manages multiple trading bot instances
    Provides unified interface for API access
    """

    def __init__(self):
        self.bots: Dict[str, TradingBot] = {}
        self._running = False
        self._tasks = []

    async def initialize(self):
        """Initialize trading engine with configured wallets"""
        # Check for multiple wallet configurations
        config_dir = Path("config")
        wallet_configs = []

        # Load base config
        base_config = get_config(suffix="")
        if base_config.is_valid():
            wallet_configs.append(("0", base_config))

        # Look for additional wallet configs (config_1.json, config_2.json, etc.)
        for i in range(1, 10):  # Support up to 10 wallets
            config_path = config_dir / f"config_{i}.json"
            if config_path.exists():
                config = get_config(suffix=f"_{i}")
                if config.is_valid():
                    wallet_configs.append((str(i), config))

        # Also check environment variables for multiple wallets
        # PRIVATE_KEY_1, PRIVATE_KEY_2, etc.
        for i in range(1, 10):
            private_key = os.getenv(f"PRIVATE_KEY_{i}")
            if private_key:
                config = get_config(suffix=f"_{i}")
                if config.is_valid():
                    wallet_configs.append((str(i), config))

        # Initialize bot for each wallet
        for wallet_id, config in wallet_configs:
            try:
                bot = TradingBot(config=config, bot_id=wallet_id)
                if await bot.initialize():
                    self.bots[wallet_id] = bot
                    print(f"[Engine] Initialized wallet {wallet_id}: {bot.state.wallet_address}")
                else:
                    print(f"[Engine] Failed to initialize wallet {wallet_id}")
            except Exception as e:
                print(f"[Engine] Error initializing wallet {wallet_id}: {e}")

        if not self.bots:
            print("[Engine] WARNING: No valid wallets configured!")
            return False

        print(f"[Engine] Initialized {len(self.bots)} wallet(s)")
        return True

    async def start(self):
        """Start all bot loops"""
        if self._running:
            print("[Engine] Already running")
            return

        self._running = True

        # Start all bots
        for wallet_id, bot in self.bots.items():
            try:
                tasks = await bot.start()
                self._tasks.extend(tasks)
                print(f"[Engine] Started bot for wallet {wallet_id}")
            except Exception as e:
                print(f"[Engine] Error starting bot {wallet_id}: {e}")

        print(f"[Engine] Started {len(self.bots)} bot(s) with {len(self._tasks)} tasks")

    async def stop(self):
        """Stop all bots"""
        if not self._running:
            return

        print("[Engine] Stopping all bots...")
        self._running = False

        # Stop each bot
        for wallet_id, bot in self.bots.items():
            try:
                await bot.stop()
                print(f"[Engine] Stopped bot {wallet_id}")
            except Exception as e:
                print(f"[Engine] Error stopping bot {wallet_id}: {e}")

        # Cancel tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._tasks.clear()
        print("[Engine] All bots stopped")

    def get_state(self, wallet_id: Optional[str] = None):
        """Get state for specific wallet or aggregate"""
        if wallet_id:
            if wallet_id in self.bots:
                return self.bots[wallet_id].state
            return None

        # Return first bot's state for backward compatibility
        if self.bots:
            return next(iter(self.bots.values())).state
        return None

    async def broadcast_update(self):
        """Broadcast state update to WebSocket clients"""
        from web.backend.api import manager

        if not manager.active_connections:
            return

        # Get aggregate state
        state_data = {
            "wallets": [],
            "timestamp": asyncio.get_event_loop().time(),
        }

        for wallet_id, bot in self.bots.items():
            state = bot.state
            state_data["wallets"].append(
                {
                    "id": wallet_id,
                    "address": state.wallet_address,
                    "usdc_balance": state.usdc_balance,
                    "portfolio_value": state.portfolio_value,
                    "is_connected": state.is_connected,
                    "auto_trade": state.auto_trade,
                    "assets": {
                        name: {
                            "price": asset.price,
                            "signal": asset.signal,
                            "has_position": asset.has_position,
                            "position_pnl": asset.position_pnl,
                        }
                        for name, asset in state.assets.items()
                    },
                }
            )

        await manager.broadcast({"type": "state_update", "data": state_data})


# Global engine instance
_global_engine: Optional[TradingEngine] = None


def get_engine() -> TradingEngine:
    """Get global engine instance"""
    global _global_engine
    if _global_engine is None:
        _global_engine = TradingEngine()
    return _global_engine


async def initialize_engine() -> TradingEngine:
    """Initialize and return global engine"""
    engine = get_engine()
    await engine.initialize()
    return engine
