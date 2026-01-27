# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "rich>=13.7.0",
#     "py-clob-client>=0.18.0",
#     "websockets>=12.0",
#     "aiohttp>=3.9.0",
#     "numpy>=1.26.0",
#     "scipy>=1.11.0",
#     "python-dotenv>=1.0.0",
#     "web3>=6.0.0",
#     "fastapi>=0.109.0",
#     "uvicorn>=0.27.0",
# ]
# ///

"""
BTC Polymarket ARB Bot - Main Entry Point
Supports CLI (Rich) and Web (FastAPI) interfaces.
"""

import asyncio
import argparse
import logging
import os

# Disable Uvicorn access logs to keep CLI clean
logging.getLogger("uvicorn.access").disabled = True

from bot_core import TradingBot
from config import get_config
from ui_cli import run_cli
from ui_web import run_web, app
import uvicorn


async def main():
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    parser = argparse.ArgumentParser(description="BTC Polymarket Bot")
    parser.add_argument(
        "--web-only", action="store_true", help="Run only the Web Interface (no CLI UI)"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Web Dashboard Port (overrides config)"
    )
    args = parser.parse_args()

    # Initialize Bots (Multi-Wallet Support)
    bots = []

    # 1. Base Bot (Default Config)
    base_config = get_config()
    if base_config.is_valid():
        bots.append(TradingBot(config=base_config, bot_id=""))
    else:
        print(
            "⚠ Base config is invalid (missing private_key or proxy_address). Checking for additional wallets..."
        )

    # 2. Additional Wallets (_1, _2, ...)
    index = 1
    while True:
        suffix = f"_{index}"
        extra_config = get_config(suffix=suffix)

        # Check if this specific config is valid (has its own private key/proxy)
        # Note: private_key and proxy_address are required.
        # get_config will return "" if not found, making is_valid() False.
        if extra_config.is_valid():
            print(f"✅ Found additional wallet config: {suffix}")
            bots.append(TradingBot(config=extra_config, bot_id=str(index)))
            index += 1
        else:
            break

    if not bots:
        print("❌ No valid bot configurations found. Please check config.json or .env.")
        return

    print(f"🚀 Initializing {len(bots)} Bot(s)...")

    # Determine Port: CLI arg > Config > Default(8000)
    # Use the first bot's config for port
    main_bot = bots[0]
    port = args.port if args.port is not None else main_bot.config.web_port

    # Start All Bots
    all_tasks = []
    for i, bot in enumerate(bots):
        print(f"  Starting Bot #{i + 1} ({bot.config.proxy_address[:8]}...)...")
        bot_tasks = await bot.start()
        if bot_tasks:
            all_tasks.extend(bot_tasks)

    if not all_tasks:
        print("❌ Failed to start any bots.")
        return

    tasks = []

    # 1. Web Server Task
    # We need to run uvicorn programmatically
    from ui_web import set_bot_instances

    set_bot_instances(bots)  # Pass all bots to Web UI

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)

    # Uvicorn runs as a task
    web_task = asyncio.create_task(server.serve())
    tasks.append(web_task)

    try:
        # 2. CLI Interface
        if not args.web_only:
            # Run CLI in the main flow (since Rich Live likes to control the screen)
            print(
                f"🚀 Web Dashboard available at http://localhost:{port} (or http://<YOUR_IP>:{port})"
            )

            # CLI currently supports visualizing one bot. We pass the main bot.
            # Ideally, we'd update CLI to cycle through bots.
            await run_cli(main_bot)

            # If CLI exits (user pressed Q), we stop everything
            server.should_exit = True
        else:
            print(
                f"🚀 Web Dashboard running at http://localhost:{port} (or http://<YOUR_IP>:{port})"
            )
            # If web only, we just wait for the web server
            await web_task

    finally:
        # Cleanup
        print("\n🛑 Shutting down bots...")
        for bot in bots:
            await bot.stop()

        for t in all_tasks:
            t.cancel()

        # Wait for tasks to cancel
        await asyncio.gather(*all_tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
