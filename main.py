#!/usr/bin/env python3
"""
Trading Bot - Main Entry Point

A modular trading bot supporting multiple exchanges and strategies.
Uses core/ architecture for registry, context, and interfaces.

Features:
- Multi-exchange support (Polymarket, Binance, etc.)
- Multi-strategy execution (Trend, Arbitrage, Edge Hedge, Expiry Sniper)
- Multi-wallet management
- CLI and Web interfaces
- Dry-run mode for testing
- Graceful shutdown handling

Usage:
    python main.py                    # Run with CLI and Web interfaces
    python main.py --web-only         # Web interface only
    python main.py --dry-run          # Simulation mode (no real trades)
    python main.py --wallet main      # Run specific wallet only
    python main.py --port 8080        # Custom web port
"""

import asyncio
import argparse
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import core components
from config import BaseConfig, load_config
from core.context import BotState, ExecutionContext
from core.registry import RegistrationError, exchange_registry, strategy_registry

# Import exchanges
from exchanges.binance import BinanceFeed
from exchanges.polymarket import PolymarketClient

# Import strategies
from strategies.arbitrage import ArbitrageConfig, SurebetEngine
from strategies.edge_hedge import EdgeHedgeStrategy
from strategies.expiry_sniper import ExpirySniperStrategy
from strategies.trend import TrendConfig, TrendStrategy

# Setup logging
from src.utils.logger import setup_logger


# ========== Trading Engine ==========

class TradingEngine:
    """
    Main trading engine that orchestrates exchanges and strategies.

    Coordinates:
    - Multiple exchange connections
    - Multiple strategy instances
    - Per-wallet execution contexts
    - Event routing and callbacks
    """

    def __init__(
        self,
        config: BaseConfig,
        dry_run: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize trading engine.

        Args:
            config: Bot configuration
            dry_run: If True, simulate trades without execution
            logger: Logger instance
        """
        self.config = config
        self.dry_run = dry_run
        self.logger = logger or logging.getLogger("trading_engine")

        # Exchange instances
        self.exchanges: Dict[str, Any] = {}

        # Strategy instances per wallet
        self.strategies: Dict[str, List[Any]] = {}

        # Execution contexts per wallet
        self.contexts: Dict[str, ExecutionContext] = {}

        # Running state
        self.running = False

        self.logger.info(f"TradingEngine initialized (dry_run={dry_run})")

    async def initialize(self) -> bool:
        """
        Initialize exchanges and strategies.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Initialize exchanges
            await self._initialize_exchanges()

            # Initialize strategies for each wallet
            await self._initialize_strategies()

            self.logger.info("TradingEngine initialization complete")
            return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    async def _initialize_exchanges(self) -> None:
        """Initialize exchange connections."""
        self.logger.info("Initializing exchanges...")

        for exchange_name, exchange_config in self.config.exchanges.items():
            if not exchange_config.enabled:
                self.logger.info(f"Skipping disabled exchange: {exchange_name}")
                continue

            try:
                # Create exchange instance from registry
                if exchange_name == "binance":
                    exchange = BinanceFeed(
                        api_key=exchange_config.credentials.get("api_key", ""),
                        api_secret=exchange_config.credentials.get("api_secret", ""),
                        logger=self.logger.getChild(f"exchange.{exchange_name}"),
                    )
                    await exchange.connect()
                    self.exchanges[exchange_name] = exchange
                    self.logger.info(f"Exchange initialized: {exchange_name}")

                elif exchange_name == "polymarket":
                    # Get credentials from first active wallet or global config
                    active_wallets = self.config.get_active_wallets()
                    if not active_wallets:
                        raise ValueError("No active wallets found for Polymarket")

                    wallet = active_wallets[0]
                    wallet_creds = wallet.get_exchange_credentials("polymarket")

                    exchange = PolymarketClient(
                        private_key=wallet.private_key,
                        host=exchange_config.host,
                        signature_type=exchange_config.signature_type,
                        logger=self.logger.getChild(f"exchange.{exchange_name}"),
                    )
                    await exchange.connect()
                    self.exchanges[exchange_name] = exchange
                    self.logger.info(f"Exchange initialized: {exchange_name}")

                else:
                    self.logger.warning(f"Unknown exchange: {exchange_name}")

            except Exception as e:
                self.logger.error(f"Failed to initialize {exchange_name}: {e}")
                raise

    async def _initialize_strategies(self) -> None:
        """Initialize strategies for each active wallet."""
        self.logger.info("Initializing strategies...")

        active_wallets = self.config.get_active_wallets()

        for wallet in active_wallets:
            wallet_id = wallet.name
            self.logger.info(f"Setting up wallet: {wallet_id}")

            # Create execution context for this wallet
            context = ExecutionContext(
                bot_id=wallet_id,
                logger=self.logger.getChild(f"context.{wallet_id}"),
                auto_trade=not self.dry_run,
            )

            # Setup callbacks
            context.log_callback = self._on_log
            context.log_error_callback = self._on_error
            context.log_pnl_callback = self._on_pnl
            context.on_signal_callback = self._on_signal
            context.on_trade_callback = self._on_trade
            context.on_error_callback = self._on_strategy_error

            self.contexts[wallet_id] = context
            self.strategies[wallet_id] = []

            # Initialize strategies for this wallet
            for strategy_name in wallet.strategies:
                strategy_config = self.config.get_strategy(strategy_name)

                if not strategy_config or not strategy_config.enabled:
                    self.logger.warning(f"Strategy not enabled: {strategy_name}")
                    continue

                try:
                    strategy = await self._create_strategy(
                        strategy_name,
                        strategy_config,
                        context,
                    )
                    if strategy:
                        self.strategies[wallet_id].append(strategy)
                        self.logger.info(f"Strategy initialized: {strategy_name} for wallet {wallet_id}")

                except Exception as e:
                    self.logger.error(f"Failed to initialize {strategy_name}: {e}")

            self.logger.info(f"Wallet {wallet_id}: {len(self.strategies[wallet_id])} strategies ready")

    async def _create_strategy(
        self,
        strategy_name: str,
        strategy_config: Any,
        context: ExecutionContext,
    ) -> Optional[Any]:
        """
        Create a strategy instance.

        Args:
            strategy_name: Strategy identifier
            strategy_config: Strategy configuration
            context: Execution context

        Returns:
            Strategy instance or None if creation failed
        """
        try:
            if strategy_name == "trend":
                # Convert to TrendConfig
                trend_config = TrendConfig(
                    name="trend",
                    enabled=strategy_config.enabled,
                    mode=strategy_config.parameters.get("mode", "directional"),
                    edge_threshold_pct=strategy_config.parameters.get("edge_threshold_pct", 3.0),
                    min_confidence=strategy_config.parameters.get("min_confidence", 0.6),
                    max_position_size=strategy_config.parameters.get("max_position_size", 1000.0),
                    risk_per_trade=strategy_config.parameters.get("risk_per_trade", 0.02),
                    exit_edge_threshold=strategy_config.parameters.get("exit_edge_threshold", 1.0),
                    stoploss_edge_pct=strategy_config.parameters.get("stoploss_edge_pct", -10.0),
                    time_exit_seconds=strategy_config.parameters.get("time_exit_seconds", 300),
                )

                strategy = TrendStrategy(
                    config=trend_config,
                    exchange_client=self.exchanges.get("polymarket"),
                    prob_model=None,  # TODO: create probability model
                    logger=context.logger,
                )

                # Validate config
                if not strategy.validate_config():
                    raise ValueError(f"Invalid {strategy_name} configuration")

                return strategy

            elif strategy_name == "arbitrage":
                arbitrage_config = ArbitrageConfig(
                    name="arbitrage",
                    enabled=strategy_config.enabled,
                    min_profit_rate=strategy_config.parameters.get("min_profit_rate", 0.02),
                    max_position_size=strategy_config.parameters.get("max_position_size", 1000.0),
                )

                strategy = SurebetEngine(
                    config=arbitrage_config,
                    exchange_client=self.exchanges.get("polymarket"),
                    logger=context.logger,
                )

                return strategy

            elif strategy_name == "edge_hedge":
                # Edge hedge strategy
                strategy = EdgeHedgeStrategy(
                    config=strategy_config,
                    exchange_client=self.exchanges.get("polymarket"),
                    logger=context.logger,
                )

                return strategy

            elif strategy_name == "expiry_sniper":
                # Expiry sniper strategy
                strategy = ExpirySniperStrategy(
                    config=strategy_config,
                    exchange_client=self.exchanges.get("polymarket"),
                    logger=context.logger,
                )

                return strategy

            else:
                self.logger.warning(f"Unknown strategy: {strategy_name}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to create {strategy_name}: {e}", exc_info=True)
            return None

    async def start(self) -> None:
        """Start the trading engine."""
        self.logger.info("Starting TradingEngine...")
        self.running = True

        # Start all contexts
        for context in self.contexts.values():
            context.start()

        # Start main trading loop
        asyncio.create_task(self._trading_loop())

        self.logger.info("TradingEngine started")

    async def stop(self) -> None:
        """Stop the trading engine."""
        self.logger.info("Stopping TradingEngine...")
        self.running = False

        # Stop all contexts
        for context in self.contexts.values():
            context.stop()

        # Disconnect exchanges
        for exchange in self.exchanges.values():
            try:
                await exchange.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting exchange: {e}")

        self.logger.info("TradingEngine stopped")

    async def _trading_loop(self) -> None:
        """Main trading loop."""
        self.logger.info("Trading loop started")

        while self.running:
            try:
                # Run strategy analysis for each wallet
                for wallet_id, strategies in self.strategies.items():
                    context = self.contexts[wallet_id]

                    if not context.is_running():
                        continue

                    context.update_time()

                    # Run each strategy
                    for strategy in strategies:
                        try:
                            # Analyze and generate signals
                            signal = await strategy.analyze(context)

                            if signal and signal.action != "hold":
                                # Execute signal if auto_trade is enabled
                                if context.auto_trade:
                                    await self._execute_signal(wallet_id, strategy, signal, context)
                                else:
                                    self.logger.info(f"[DRY RUN] Would execute: {signal}")

                        except Exception as e:
                            context.emit_error(strategy.__class__.__name__, e)

                # Wait before next iteration
                await asyncio.sleep(1.0)

            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}", exc_info=True)
                await asyncio.sleep(5.0)

        self.logger.info("Trading loop stopped")

    async def _execute_signal(
        self,
        wallet_id: str,
        strategy: Any,
        signal: Any,
        context: ExecutionContext,
    ) -> None:
        """
        Execute a trading signal.

        Args:
            wallet_id: Wallet identifier
            strategy: Strategy instance
            signal: Trading signal
            context: Execution context
        """
        try:
            # Get exchange client
            exchange_name = "polymarket"  # Default
            exchange = self.exchanges.get(exchange_name)

            if not exchange:
                raise ValueError(f"Exchange not available: {exchange_name}")

            # Execute trade based on signal
            if signal.action == "buy":
                # Execute buy order
                order = await exchange.buy(
                    symbol=signal.symbol,
                    size=signal.size,
                    price=signal.price,
                )
                await context.emit_trade(strategy.__class__.__name__, {
                    "side": "BUY",
                    "symbol": signal.symbol,
                    "size": signal.size,
                    "price": signal.price,
                    "order_id": order.get("id"),
                })

            elif signal.action == "sell":
                # Execute sell order
                order = await exchange.sell(
                    symbol=signal.symbol,
                    size=signal.size,
                    price=signal.price,
                )
                await context.emit_trade(strategy.__class__.__name__, {
                    "side": "SELL",
                    "symbol": signal.symbol,
                    "size": signal.size,
                    "price": signal.price,
                    "order_id": order.get("id"),
                })

            elif signal.action == "close":
                # Close position
                await self._close_position(wallet_id, signal.symbol, context)

        except Exception as e:
            context.emit_error(strategy.__class__.__name__, e)

    async def _close_position(
        self,
        wallet_id: str,
        symbol: str,
        context: ExecutionContext,
    ) -> None:
        """Close a position for a wallet."""
        # TODO: Implement position closing logic
        context.log(f"Closing position: {symbol}", log_type="debug")

    # ===== Callbacks =====

    def _on_log(self, message: str, log_type: str) -> None:
        """Log callback."""
        if log_type == "error":
            self.logger.error(f"[{log_type.upper()}] {message}")
        elif log_type == "pnl":
            self.logger.info(f"[PNL] {message}")
        else:
            self.logger.debug(message)

    def _on_error(self, message: str) -> None:
        """Error callback."""
        self.logger.error(f"[ERROR] {message}")

    def _on_pnl(self, bot_id: str, pnl: float) -> None:
        """PnL callback."""
        self.logger.info(f"[PNL] {bot_id}: ${pnl:+.2f}")

    async def _on_signal(self, strategy_name: str, signal: Dict[str, Any]) -> None:
        """Signal callback."""
        self.logger.info(
            f"[SIGNAL] {strategy_name}: {signal.get('action')} "
            f"{signal.get('direction')} {signal.get('symbol')} "
            f"@ {signal.get('edge')}% edge"
        )

    async def _on_trade(self, strategy_name: str, trade: Dict[str, Any]) -> None:
        """Trade callback."""
        self.logger.info(
            f"[TRADE] {strategy_name}: {trade.get('side')} "
            f"{trade.get('size')} {trade.get('symbol')} @ {trade.get('price')}"
        )

    def _on_strategy_error(self, strategy_name: str, error: Exception) -> None:
        """Strategy error callback."""
        self.logger.error(f"[STRATEGY ERROR] {strategy_name}: {error}")


# ========== Web Server ==========

async def start_web_server(
    engine: TradingEngine,
    port: int,
    logger: logging.Logger,
) -> None:
    """
    Start the web server.

    Args:
        engine: Trading engine instance
        port: Web server port
        logger: Logger instance
    """
    try:
        import uvicorn
        from fastapi import FastAPI

        app = FastAPI(title="Trading Bot API")

        # Basic health check endpoint
        @app.get("/health")
        async def health_check():
            return {"status": "ok", "running": engine.running}

        # TODO: Add more API endpoints for monitoring and control

        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
        server = uvicorn.Server(config)

        logger.info(f"Web server starting on port {port}")
        await server.serve()

    except ImportError:
        logger.warning("FastAPI/Uvicorn not available, web server disabled")


# ========== CLI Utilities ==========

def setup_argument_parser() -> argparse.ArgumentParser:
    """Setup CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Trading Bot - Multi-exchange, multi-strategy trading bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run with CLI and Web interfaces
  python main.py --web-only         # Web interface only
  python main.py --dry-run          # Simulation mode (no real trades)
  python main.py --wallet main      # Run specific wallet only
  python main.py --port 8080        # Custom web port
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in simulation mode without executing real trades",
    )

    parser.add_argument(
        "--wallet",
        type=str,
        metavar="WALLET",
        help="Run only the specified wallet (default: all active wallets)",
    )

    parser.add_argument(
        "--web-only",
        action="store_true",
        help="Run only the web interface, disable CLI",
    )

    parser.add_argument(
        "--port",
        type=int,
        metavar="PORT",
        help="Web server port (overrides config)",
    )

    parser.add_argument(
        "--config",
        type=str,
        metavar="PATH",
        default="config.json",
        help="Path to config file (default: config.json)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    return parser


async def run_cli_interface(engine: TradingEngine) -> None:
    """
    Run the CLI interface.

    Args:
        engine: Trading engine instance
    """
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    console = Console()

    try:
        with Live(console=console, refresh_per_second=1) as live:
            while engine.running:
                # Build dashboard
                table = Table(title="Trading Bot Dashboard", show_header=True)
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")

                # Add engine status
                table.add_row("Status", "Running" if engine.running else "Stopped")
                table.add_row("Mode", "DRY RUN" if engine.dry_run else "LIVE")
                table.add_row("Exchanges", str(len(engine.exchanges)))

                # Add wallet status
                for wallet_id, context in engine.contexts.items():
                    state = context.get_bot_state().value.upper()
                    table.add_row(f"Wallet: {wallet_id}", state)

                live.update(table)
                await asyncio.sleep(1.0)

    except KeyboardInterrupt:
        pass


# ========== Main Entry Point ==========

async def main_async(args: argparse.Namespace) -> int:
    """
    Main async entry point.

    Args:
        args: Parsed CLI arguments

    Returns:
        int: Exit code (0 = success, non-zero = error)
    """
    # Setup logging
    os.makedirs("logs", exist_ok=True)
    logger = setup_logger("main", "trading_bot.log", level=args.log_level)

    logger.info("=" * 60)
    logger.info("Trading Bot Starting")
    logger.info("=" * 60)

    # Load configuration
    try:
        logger.info(f"Loading configuration from: {args.config}")
        config = load_config(args.config)
        logger.info(f"Configuration loaded successfully")
        logger.info(f"  - Exchanges: {len(config.exchanges)}")
        logger.info(f"  - Strategies: {len(config.strategies)}")
        logger.info(f"  - Wallets: {len(config.wallets)}")

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.error("Create a config.json file or set up .env variables")
        return 1
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    # Filter wallet if specified
    if args.wallet:
        if args.wallet not in config.wallets:
            logger.error(f"Wallet not found: {args.wallet}")
            return 1

        # Disable all other wallets
        for wallet_name in config.wallets:
            config.wallets[wallet_name].enabled = (wallet_name == args.wallet)

        logger.info(f"Running single wallet: {args.wallet}")

    # Determine web port
    web_port = args.port if args.port else config.web_port

    # Create trading engine
    logger.info("Initializing trading engine...")
    engine = TradingEngine(
        config=config,
        dry_run=args.dry_run,
        logger=logger.getChild("engine"),
    )

    # Initialize engine
    if not await engine.initialize():
        logger.error("Failed to initialize trading engine")
        return 1

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, initiating shutdown...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start engine
    await engine.start()

    # Start web server
    web_task = None
    if web_port:
        web_task = asyncio.create_task(
            start_web_server(engine, web_port, logger.getChild("web"))
        )

        # Log web server URL
        logger.info(f"Web dashboard: http://localhost:{web_port}")

    # Run CLI or web-only mode
    try:
        if args.web_only:
            logger.info("Running in web-only mode")

            # Wait for shutdown signal
            await shutdown_event.wait()

        else:
            logger.info("Running CLI interface")

            # Run CLI interface
            cli_task = asyncio.create_task(run_cli_interface(engine))

            # Wait for either CLI to finish or shutdown signal
            done, pending = await asyncio.wait(
                [cli_task, asyncio.create_task(shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()

    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
        return 1

    finally:
        # Shutdown
        logger.info("Shutting down...")

        await engine.stop()

        if web_task:
            web_task.cancel()
            try:
                await web_task
            except asyncio.CancelledError:
                pass

        logger.info("Shutdown complete")

    return 0


def main() -> int:
    """
    Main entry point.

    Returns:
        int: Exit code
    """
    parser = setup_argument_parser()
    args = parser.parse_args()

    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        return 0
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
