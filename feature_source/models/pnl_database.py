"""
Polymarket Bot - PnL Database System

Stores trade history and PnL metrics in SQLite for:
- Fast querying (no log parsing)
- Historical analysis
- Per-wallet tracking
- Strategy performance metrics
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class TradeRecord:
    """Single trade record"""

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
    realized_pnl: float = 0.0
    condition_id: str = ""


@dataclass
class PnLSnapshot:
    """Portfolio PnL snapshot for tracking over time"""

    id: int
    timestamp: float
    wallet_id: str
    asset: str
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    position_size: float
    portfolio_value: float


class PnLDatabase:
    """SQLite database for PnL tracking"""

    def __init__(self, db_path: str = "data/pnl.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create database schema"""
        os.makedirs(
            os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else "data",
            exist_ok=True,
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    wallet_id TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    asset_name TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    size REAL NOT NULL,
                    price REAL NOT NULL,
                    cost REAL NOT NULL,
                    strategy TEXT NOT NULL,
                    is_exit INTEGER NOT NULL DEFAULT 0,
                    realized_pnl REAL DEFAULT 0.0,
                    condition_id TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pnl_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    wallet_id TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    total_pnl REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    position_size REAL NOT NULL,
                    portfolio_value REAL NOT NULL
                )
            """)

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trades_wallet ON trades(wallet_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON pnl_snapshots(timestamp)"
            )

            conn.commit()

    def record_trade(
        self,
        wallet_id: str,
        asset: str,
        asset_name: str,
        direction: str,
        size: float,
        price: float,
        cost: float,
        strategy: str,
        is_exit: bool = False,
        realized_pnl: float = 0.0,
        condition_id: str = "",
    ) -> int:
        """Record a trade execution"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO trades (
                    timestamp, wallet_id, asset, asset_name, direction, size,
                    price, cost, strategy, is_exit, realized_pnl, condition_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now().timestamp(),
                    wallet_id,
                    asset,
                    asset_name,
                    direction,
                    size,
                    price,
                    cost,
                    strategy,
                    1 if is_exit else 0,
                    realized_pnl,
                    condition_id,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def record_snapshot(
        self,
        wallet_id: str,
        asset: str,
        total_pnl: float,
        realized_pnl: float,
        unrealized_pnl: float,
        position_size: float,
        portfolio_value: float,
    ):
        """Record PnL snapshot"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pnl_snapshots (
                    timestamp, wallet_id, asset, total_pnl, realized_pnl,
                    unrealized_pnl, position_size, portfolio_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now().timestamp(),
                    wallet_id,
                    asset,
                    total_pnl,
                    realized_pnl,
                    unrealized_pnl,
                    position_size,
                    portfolio_value,
                ),
            )
            conn.commit()

    def get_total_pnl(self, wallet_id: str = "") -> float:
        """Calculate total PnL from all trades"""
        query = "SELECT SUM(realized_pnl) FROM trades"
        params = []

        if wallet_id:
            query += " WHERE wallet_id = ?"
            params.append(wallet_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result[0] else 0.0

    def get_pnl_history(
        self, wallet_id: str = "", hours: int = 24, interval_minutes: int = 5
    ) -> List[PnLSnapshot]:
        """Get PnL history as snapshots"""
        since = datetime.now().timestamp() - (hours * 3600)
        query = """
            SELECT * FROM pnl_snapshots
            WHERE timestamp >= ?
        """
        params = [since]

        if wallet_id:
            query += " AND wallet_id = ?"
            params.append(wallet_id)

        query += " ORDER BY timestamp ASC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [PnLSnapshot(**dict(row)) for row in rows]

    def get_trades(
        self, wallet_id: str = "", limit: int = 100, asset: str = ""
    ) -> List[TradeRecord]:
        """Get recent trades"""
        query = "SELECT * FROM trades"
        conditions = []
        params = []

        if wallet_id:
            conditions.append("wallet_id = ?")
            params.append(wallet_id)

        if asset:
            conditions.append("asset = ?")
            params.append(asset)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [TradeRecord(**dict(row)) for row in rows]

    def get_strategy_performance(self, wallet_id: str = "") -> Dict[str, Dict]:
        """Calculate performance metrics per strategy"""
        query = """
            SELECT
                strategy,
                COUNT(*) as trade_count,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as win_count,
                SUM(realized_pnl) as total_pnl,
                AVG(realized_pnl) as avg_pnl
            FROM trades
            WHERE is_exit = 1 AND realized_pnl IS NOT NULL
        """
        params = []

        if wallet_id:
            query += " AND wallet_id = ?"
            params.append(wallet_id)

        query += " GROUP BY strategy"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = {}
            for row in rows:
                result[row["strategy"]] = {
                    "trade_count": row["trade_count"],
                    "win_count": row["win_count"],
                    "loss_count": row["trade_count"] - row["win_count"],
                    "win_rate": (row["win_count"] / row["trade_count"] * 100)
                    if row["trade_count"] > 0
                    else 0,
                    "total_pnl": row["total_pnl"],
                    "avg_pnl": row["avg_pnl"],
                }
            return result

    def cleanup_old_data(self, days: int = 90):
        """Remove data older than specified days"""
        cutoff = datetime.now().timestamp() - (days * 86400)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM trades WHERE timestamp < ?", (cutoff,))
            deleted_trades = cursor.rowcount

            cursor.execute("DELETE FROM pnl_snapshots WHERE timestamp < ?", (cutoff,))
            deleted_snapshots = cursor.rowcount

            conn.commit()

        return {
            "deleted_trades": deleted_trades,
            "deleted_snapshots": deleted_snapshots,
        }

    def get_stats(self, wallet_id: str = "") -> Dict:
        """Get overall statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = "SELECT COUNT(*), SUM(realized_pnl) FROM trades WHERE is_exit = 1"
            params = []

            if wallet_id:
                query += " AND wallet_id = ?"
                params.append(wallet_id)

            cursor.execute(query, params)
            row = cursor.fetchone()

            return {"total_trades": row[0] or 0, "total_realized_pnl": row[1] or 0.0}


_global_db: Optional[PnLDatabase] = None


def get_pnl_db(db_path: str = "data/pnl.db") -> PnLDatabase:
    """Get global PnL database instance"""
    global _global_db
    if _global_db is None:
        _global_db = PnLDatabase(db_path)
    return _global_db
