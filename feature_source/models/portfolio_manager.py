
import asyncio
import json
import os
import time
from typing import List, Dict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from config import get_config

HISTORY_FILE = "portfolio_history.json"

@dataclass
class PortfolioSnapshot:
    timestamp: float
    date_str: str
    usdc_balance: float
    invested_value: float
    total_value: float
    wallets: Dict[str, float] = field(default_factory=dict) # NEW: Breakdown per wallet

class PortfolioManager:
    """
    Manages portfolio history:
    1. Loads/Saves local history file.
    2. Reconstructs past history from Polymarket Activity API if file is empty.
    3. Appends new snapshots periodically.
    """
    def __init__(self, client, filepath: str = HISTORY_FILE):
        self.client = client
        self.filepath = filepath
        self.history: List[PortfolioSnapshot] = []
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Handle legacy data (missing wallets field)
                    cleaned_data = []
                    for item in data:
                        if 'wallets' not in item:
                            item['wallets'] = {}
                        cleaned_data.append(item)
                        
                    self.history = [PortfolioSnapshot(**item) for item in cleaned_data]
                    # Sort to be sure
                    self.history.sort(key=lambda x: x.timestamp)
            except Exception as e:
                print(f"[Portfolio] Failed to load history: {e}")
                self.history = []

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump([asdict(s) for s in self.history], f, indent=2)
        except Exception as e:
            print(f"[Portfolio] Failed to save history: {e}")

    def add_snapshot(self, usdc: float, invested: float, wallets_data: Dict[str, float] = None):
        """Add a real-time snapshot (USDC + Market Value of Positions)"""
        now = time.time()
        
        # Don't save too often (limit 5 min)
        if self.history and (now - self.history[-1].timestamp < 300):
            return

        total = usdc + invested
        snapshot = PortfolioSnapshot(
            timestamp=now,
            date_str=datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
            usdc_balance=usdc,
            invested_value=invested,
            total_value=total,
            wallets=wallets_data or {}
        )
        self.history.append(snapshot)
        
        # Limit size (10k points)
        if len(self.history) > 10000:
            self.history = self.history[-10000:]
            
        self.save()

    async def fetch_portfolio_history(self, period: str = "all") -> List[Dict]:
        """API endpoint for frontend"""
        # If history is sparse (fresh start), try to rebuild/merge
        if len(self.history) < 5:
            print("[Portfolio] History sparse. Attempting to rebuild from activity...")
            await self.rebuild_history_from_activity()
            
        if not self.history:
            return []

        now = time.time()
        start_time = 0
        if period == "1d":
            start_time = now - 86400
        elif period == "7d":
            start_time = now - 86400 * 7
            
        return [asdict(s) for s in self.history if s.timestamp >= start_time]

    async def rebuild_history_from_activity(self):
        """
        Reconstruct history by REVERSE calculating from current balance.
        This ensures the end point matches the current actual balance.
        """
        print("[Portfolio] Fetching activity history for reconstruction...")
        activities = await self.client.fetch_activity(limit=2000) # Fetch more to cover 30 days
        print(f"[Portfolio] Fetched {len(activities)} activity records.")
        
        if not activities:
            return

        # Get Current Balance (Anchor point)
        current_usdc = await self.client.get_usdc_balance()
        
        # Sort chronological: Oldest first
        activities.sort(key=lambda x: float(x.get("timestamp", 0)))
        
        # We need to process from NEWEST to OLDEST to reverse engineer balances.
        # But we want to PLOT from Oldest to Newest.
        
        # Strategy:
        # 1. Calculate balances backwards from Now.
        # 2. Store (timestamp, balance) pairs.
        # 3. Sort by timestamp for display.
        
        snapshots = []
        running_balance = current_usdc
        
        # Reverse iterate
        for act in reversed(activities):
            ts = float(act.get("timestamp", 0))
            
            # Skip if older than 30 days
            if time.time() - ts > 30 * 86400:
                continue
                
            # Current 'running_balance' is the balance AFTER this activity occurred.
            # We want to find the balance BEFORE this activity.
            # Then that 'Before' balance becomes the 'After' balance for the previous activity.
            
            # Record state AFTER this activity (which is the current running_balance)
            # Actually, to make a graph, we want the state at this timestamp.
            snapshots.append(PortfolioSnapshot(
                timestamp=ts,
                date_str=datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                usdc_balance=running_balance,
                invested_value=0, # Hard to reverse-calc invested value accurately, keeping 0 for history
                total_value=running_balance # Approx
            ))
            
            # Reverse the operation to get Previous Balance
            type_ = act.get("type", "").upper()
            
            if type_ == "DEPOSIT":
                # Balance increased by deposit. Previous was lower.
                amount = float(act.get("amount", 0))
                running_balance -= amount
            elif type_ == "WITHDRAWAL":
                # Balance decreased. Previous was higher.
                amount = float(act.get("amount", 0))
                running_balance += amount
            elif type_ == "TRADE":
                side = act.get("side", "").upper()
                usdc_size = float(act.get("usdcSize", 0) or 0)
                if side == "BUY":
                    # Buy means we spent USDC. Previous was higher.
                    running_balance += usdc_size
                elif side == "SELL":
                    # Sell means we got USDC. Previous was lower.
                    running_balance -= usdc_size
            elif type_ == "REDEMPTION":
                # Redeem means we got USDC. Previous was lower.
                # Data API for redemption: check payload structure.
                # Assuming 'usdcSize' or 'amount' is present.
                # If not available, we might drift.
                # For now, try 'amount' then 'usdcSize'.
                amt = float(act.get("amount", 0) or act.get("usdcSize", 0) or 0)
                running_balance -= amt
        
        # Add the starting point (30 days ago)
        snapshots.append(PortfolioSnapshot(
            timestamp=time.time() - 30*86400,
            date_str=datetime.fromtimestamp(time.time() - 30*86400).strftime("%Y-%m-%d %H:%M:%S"),
            usdc_balance=running_balance,
            invested_value=0,
            total_value=running_balance
        ))
        
        # Sort chronologically for chart
        snapshots.sort(key=lambda x: x.timestamp)
        
        self.history = snapshots
        self.save()
        print(f"[Portfolio] Reconstructed {len(self.history)} history points (Reverse Calc).")

    async def get_current_positions(self) -> List[Dict]:
        """Get current open positions with PnL using Real-time Market Data"""
        raw_positions = await self.client.fetch_positions()
        processed = []
        
        # Current Market Data from Client (Real-time)
        market = self.client.market
        
        for p in raw_positions:
            size = float(p.get("size", 0))
            if size < 0.001: continue
            
            asset_id = p.get("asset")
            avg_price = float(p.get("avgPrice", 0))
            
            # Default to API price, but override with Real-time Bid if matches current market
            cur_price = float(p.get("currentPrice", 0))
            
            if market:
                # Debugging PnL issue
                # print(f"[DEBUG PnL] Checking {asset_id} vs UP:{market.token_id_up} DOWN:{market.token_id_down}")
                
                if str(asset_id) == str(market.token_id_up):
                    cur_price = market.up_bid
                    # print(f"[DEBUG PnL] Match UP! Bid: {market.up_bid}")
                elif str(asset_id) == str(market.token_id_down):
                    cur_price = market.down_bid
                    # print(f"[DEBUG PnL] Match DOWN! Bid: {market.down_bid}")
            
            # Fallback: If price is still 0 (maybe market mismatch or illiquid), use 0 but log it.
            # If API currentPrice is 0, try to check if it's expired?
            
            # Calculate PnL
            invested = size * avg_price
            current_val = size * cur_price
            pnl = current_val - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0
            
            processed.append({
                "market": p.get("title", "Unknown"),
                "asset": asset_id,
                "side": p.get("outcome", "Unknown"),
                "size": size,
                "avg_price": avg_price,
                "cur_price": cur_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct
            })
            
        return processed
