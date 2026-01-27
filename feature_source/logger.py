"""
Polymarket Bot - Centralized Logging System

Features:
- Wallet-specific log directories
- Size-based rotation with automatic compression
- Separate log levels (trading, pnl, errors)
- Console and file output
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime


class BotLogger:
    """
    Wallet-specific logger with rotation and compression

    Directory Structure:
    logs/
    ├── wallet_0/           # Main wallet
    │   ├── trading.log      # General trading logs (50MB, 20 backups)
    │   ├── pnl.log         # PnL logs (10MB, 10 backups)
    │   └── errors.log      # Error logs only (10MB, 10 backups)
    ├── wallet_1/           # Additional wallet 1
    │   ├── trading.log
    │   ├── pnl.log
    │   └── errors.log
    └── wallet_2/           # Additional wallet 2
        └── ...
    """

    # Log Configuration
    TRADING_MAX_BYTES = 50 * 1024 * 1024  # 50MB
    TRADING_BACKUP_COUNT = 20  # Keep 20 files (max 1GB)

    PNL_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    PNL_BACKUP_COUNT = 10  # Keep 10 files (max 100MB)

    ERROR_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    ERROR_BACKUP_COUNT = 10  # Keep 10 files (max 100MB)

    # Log Format
    FORMAT = "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    _loggers = {}  # Cache of created loggers

    @classmethod
    def get_logger(cls, bot_id: str = "") -> "WalletLoggers":
        """
        Get or create logger instance for a specific wallet

        Args:
            bot_id: Empty string for main wallet, "1", "2", etc. for additional wallets

        Returns:
            WalletLoggers instance with trading, pnl, and error loggers
        """
        if bot_id in cls._loggers:
            return cls._loggers[bot_id]

        wallet_dir = f"wallet_{bot_id}" if bot_id else "wallet_0"
        loggers = WalletLoggers(wallet_dir, bot_id)
        cls._loggers[bot_id] = loggers
        return loggers

    @classmethod
    def setup_logging(cls, level: int = logging.INFO):
        """
        Setup root logger configuration

        Args:
            level: Logging level (default: INFO)
        """
        # Create logs directory if not exists
        os.makedirs("logs", exist_ok=True)

        # Root logger configuration
        logging.basicConfig(
            level=level, format=cls.FORMAT, datefmt=cls.DATE_FORMAT, handlers=[]
        )

        # Disable overly verbose loggers
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("websockets").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    @classmethod
    def clear_cache(cls):
        """Clear logger cache (useful for testing)"""
        cls._loggers.clear()


class WalletLoggers:
    """
    Container for wallet-specific loggers

    Attributes:
        trading: General trading operations
        pnl: Profit/Loss tracking
        error: Error messages only
        console: Output to terminal
    """

    def __init__(self, wallet_dir: str, bot_id: str = ""):
        """
        Initialize loggers for a wallet

        Args:
            wallet_dir: Directory name (e.g., "wallet_0", "wallet_1")
            bot_id: Bot ID for log prefix (empty for main wallet)
        """
        self.wallet_dir = wallet_dir
        self.bot_id = bot_id
        self.prefix = f"[Bot {bot_id}] " if bot_id else ""

        log_path = os.path.join("logs", wallet_dir)
        os.makedirs(log_path, exist_ok=True)

        self.trading = self._setup_logger(
            "trading",
            log_path,
            BotLogger.TRADING_MAX_BYTES,
            BotLogger.TRADING_BACKUP_COUNT,
        )
        self.pnl = self._setup_logger(
            "pnl", log_path, BotLogger.PNL_MAX_BYTES, BotLogger.PNL_BACKUP_COUNT
        )
        self.error = self._setup_logger(
            "error",
            log_path,
            BotLogger.ERROR_MAX_BYTES,
            BotLogger.ERROR_BACKUP_COUNT,
            level=logging.ERROR,
        )

        self.console = self._setup_console_logger()

    def _setup_logger(
        self,
        name: str,
        log_path: str,
        max_bytes: int,
        backup_count: int,
        level: int = logging.INFO,
    ) -> logging.Logger:
        """
        Setup a logger with rotating file handler

        Args:
            name: Logger name (e.g., "trading", "pnl", "error")
            log_path: Directory path
            max_bytes: Maximum file size before rotation
            backup_count: Number of backup files to keep
            level: Logging level (default: INFO)

        Returns:
            Configured logger instance
        """
        logger_name = f"{self.wallet_dir}.{name}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)

        # Avoid duplicate handlers
        if logger.handlers:
            return logger

        # File handler with rotation (append mode by default)
        log_file = os.path.join(log_path, f"{name}.log")
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

        file_handler.setLevel(level)

        formatter = logging.Formatter(BotLogger.FORMAT, BotLogger.DATE_FORMAT)
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        return logger

    def _setup_console_logger(self) -> logging.Logger:
        """Setup logger for console output only"""
        logger = logging.getLogger(f"{self.wallet_dir}.console")
        logger.setLevel(logging.INFO)

        if logger.handlers:
            return logger

        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(BotLogger.FORMAT, BotLogger.DATE_FORMAT)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    def trading_log(self, message: str, level: int = logging.INFO):
        """
        Log trading message

        Args:
            message: Log message
            level: Log level (default: INFO)
        """
        msg = f"{self.prefix}{message}"
        self.trading.log(level, msg)

    def pnl_log(self, message: str, level: int = logging.INFO):
        """
        Log PnL message

        Args:
            message: PnL log message
            level: Log level (default: INFO)
        """
        msg = f"{self.prefix}[PNL] {message}"
        self.pnl.log(level, msg)

    def error_log(self, message: str):
        """
        Log error message

        Args:
            message: Error message
        """
        msg = f"{self.prefix}[ERROR] {message}"
        self.error.error(msg)

    def console_log(self, message: str):
        """
        Log to console only

        Args:
            message: Console message
        """
        self.console.info(f"{self.prefix}{message}")

    def get_recent_trading_logs(self, lines: int = 100) -> list:
        """
        Get recent trading log lines from file

        Args:
            lines: Number of lines to return

        Returns:
            List of recent log lines
        """
        log_file = os.path.join("logs", self.wallet_dir, "trading.log")

        if not os.path.exists(log_file):
            return []

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception as e:
            self.error_log(f"Failed to read trading logs: {e}")
            return []


# Convenience function for quick access
def get_logger(bot_id: str = "") -> WalletLoggers:
    """Get logger for a specific wallet"""
    return BotLogger.get_logger(bot_id)


def setup_logging(level: int = logging.INFO):
    """Setup global logging configuration"""
    return BotLogger.setup_logging(level)
