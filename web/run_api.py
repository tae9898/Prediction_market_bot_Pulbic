#!/usr/bin/env python3
"""
Run the FastAPI server with Trading Engine
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from web.backend.engine import initialize_engine, get_engine
from web.backend.api import app, set_trading_engine


async def main():
    """Main entry point"""
    print("=" * 60)
    print("Trading Bot API Server")
    print("=" * 60)

    # Initialize trading engine
    print("\n[1/3] Initializing Trading Engine...")
    engine = await initialize_engine()

    if not engine.bots:
        print("[ERROR] No valid wallets configured. Please check your config.json and .env file")
        print("\nRequired configuration:")
        print("  - PRIVATE_KEY in .env or private_key in config.json")
        print("  - PROXY_ADDRESS in .env or proxy_address in config.json")
        sys.exit(1)

    # Set engine reference for API
    set_trading_engine(engine)
    print(f"[OK] Initialized {len(engine.bots)} wallet(s)")

    # Start trading bots
    print("\n[2/3] Starting Trading Bots...")
    await engine.start()
    print("[OK] Trading bots started")

    # Start API server
    print("\n[3/3] Starting API Server...")
    print("=" * 60)
    print("API Endpoints:")
    print("  - REST API: http://localhost:8000")
    print("  - WebSocket: ws://localhost:8000/ws")
    print("  - Docs: http://localhost:8000/docs")
    print("  - Health: http://localhost:8000/health")
    print("=" * 60)
    print("\nPress Ctrl+C to stop\n")

    try:
        # Run uvicorn server
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    except KeyboardInterrupt:
        print("\n\n[INFO] Shutting down...")
        await engine.stop()
        print("[OK] Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted")
