"""
BTC Polymarket ARB Bot - Core Logic & State Management
"""

import asyncio
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable

from config import Config, get_config
from exchanges.binance import BinanceFeed
from exchanges.polymarket import PolymarketClient, MarketData
from models.probability import ProbabilityModel
from models.portfolio_manager import PortfolioManager
from models.pnl_database import get_pnl_db
from strategies.trend import TrendStrategy, TrendConfig
from strategies.arbitrage import SurebetEngine, ArbitrageOpportunity
from strategies.edge_hedge import EdgeHedgeStrategy, StrategyConfig
from strategies.expiry_sniper import ExpirySniperStrategy, SniperConfig
from logger import setup_logging, get_logger

# ========== State Definitions ==========


@dataclass
class AssetState:
    """Individual Asset State Data"""

    asset_type: str = "BTC"

    # Binance
    price: float = 0.0
    change_24h: float = 0.0
    change_pct: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volatility: float = 0.0
    momentum: str = "NEUTRAL"

    # Polymarket
    strike_price: float = 0.0
    time_remaining: str = "00:00"
    time_remaining_sec: int = 0
    up_ask: float = 0.0
    up_bid: float = 0.0
    down_ask: float = 0.0
    down_bid: float = 0.0
    spread: float = 0.0

    # Probability Model
    fair_up: float = 0.5
    fair_down: float = 0.5
    edge_up: float = 0.0
    edge_down: float = 0.0
    d2: float = 0.0

    # Position
    has_position: bool = False
    position_direction: str = ""
    position_size: float = 0.0
    position_avg_price: float = 0.0
    position_cost: float = 0.0
    position_pnl: float = 0.0
    position_strategy: str = ""
    position_entry_prob: float = 0.0

    # Sure-Bet
    surebet_profitable: bool = False
    surebet_spread: float = 0.0
    surebet_profit_rate: float = 0.0
    surebet_max_size: float = 0.0
    surebet_max_profit: float = 0.0
    surebet_vwap_yes: float = 0.0
    surebet_vwap_no: float = 0.0
    surebet_yes_liquidity: float = 0.0
    surebet_no_liquidity: float = 0.0
    surebet_reason: str = ""

    # Signal
    signal: str = "HOLD"
    total_pnl: float = 0.0
    transactions: List[Dict] = field(default_factory=list)


@dataclass
class BotState:
    """Global Bot State"""

    # Asset States
    assets: Dict[str, AssetState] = field(default_factory=dict)

    # Trading Control
    auto_trade: bool = False

    # Logs (Shared)
    logs: List[str] = field(default_factory=list)

    # Wallet Info
    wallet_address: str = ""
    usdc_balance: float = 0.0
    reserved_balance: float = 0.0  # Funds committed but not yet deducted
    portfolio_value: float = 0.0  # Invested + Cash
    is_connected: bool = False

    # Meta
    update_count: int = 0
    last_update: str = ""

    # Sniper Info
    sniper_info: Dict[str, str] = field(default_factory=dict)


class TradingBot:
    """Core Trading Bot Engine"""

    def __init__(self, config: Optional[Config] = None, bot_id: str = ""):
        self.config = config if config else get_config()
        self.bot_id = bot_id

        setup_logging()
        self.logger = get_logger(self.bot_id)

        # Enabled Assets
        self.enabled_assets = self.config.enabled_assets

        # State
        self.state = BotState()
        self.state.auto_trade = True

        # Initialize Asset States
        for asset in self.enabled_assets:
            self.state.assets[asset] = AssetState(asset_type=asset)

        # Modules
        self.binance_feeds: Dict[str, BinanceFeed] = {}
        self.polymarkets: Dict[str, PolymarketClient] = {}

        # Initialize Binance Feeds
        for asset in self.enabled_assets:
            self.binance_feeds[asset] = BinanceFeed(
                symbol=asset,
                volatility_window_minutes=self.config.volatility_window_minutes,
            )

        # Initialize Polymarket Clients
        for asset in self.enabled_assets:
            self.polymarkets[asset] = PolymarketClient(
                private_key=self.config.private_key,
                proxy_address=self.config.proxy_address,
                api_key=self.config.polymarket_api_key,
                api_secret=self.config.polymarket_api_secret,
                passphrase=self.config.polymarket_passphrase,
                asset_type=asset,
                log_callback=self.add_log,
                pnl_callback=lambda msg: self.add_log(msg, log_type="pnl"),
            )

        # Shared Models
        self.prob_model = ProbabilityModel(
            subtract_spread=self.config.subtract_spread_from_edge
        )
        self.portfolio_manager = None  # Initialized in start()

        # Strategies
        self.trend_strategy = TrendStrategy(
            config=TrendConfig(
                enabled=self.config.trend_enabled,
                mode=self.config.trend_mode,
                edge_threshold_pct=self.config.edge_threshold_pct,
                contrarian_entry_edge_min=self.config.contrarian_entry_edge_min,
                contrarian_entry_edge_max=self.config.contrarian_entry_edge_max,
                contrarian_take_profit_pct=self.config.contrarian_take_profit_pct,
                bet_amount_usdc=self.config.bet_amount_usdc,
                max_position_size=self.config.max_position_size,
                use_kelly=self.config.use_kelly,
            ),
            prob_model=self.prob_model,
            log_callback=self.add_log,
        )

        self.surebet_engine = SurebetEngine(
            enabled=self.config.surebet_enabled,
            min_profit_rate=1.0,
            slippage_tolerance=0.005,
            min_size=5.0,
        )

        self.edge_hedge_strategy = EdgeHedgeStrategy(
            config=StrategyConfig(
                enabled=self.config.edge_hedge_enabled,
                min_edge_pct=self.config.edge_hedge_min_edge_pct,
                profit_hedge_threshold_pct=self.config.edge_hedge_profit_threshold_pct,
                stoploss_trigger_pct=self.config.edge_hedge_stoploss_pct,
                position_size_usdc=self.config.bet_amount_usdc,
            ),
            log_callback=self.add_log,
        )

        self.expiry_sniper = ExpirySniperStrategy(
            config=SniperConfig(
                enabled=self.config.expiry_sniper_enabled,
                minutes_before=self.config.expiry_sniper_minutes_before,
                prob_threshold=self.config.expiry_sniper_prob_threshold,
                amount_usdc=self.config.expiry_sniper_amount_usdc,
                max_times=self.config.expiry_sniper_max_times,
                interval_seconds=self.config.expiry_sniper_interval_seconds,
            ),
            log_callback=self.add_log,
        )

        self.pnl_db = get_pnl_db()

        # Control Flags
        self._running = False
        self.last_balance_update = 0.0

    def add_log(self, message: str, log_type: str = "debug") -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        id_prefix = f"[Bot {self.bot_id}] " if self.bot_id else ""
        log_message = f"[{timestamp}] {id_prefix}{message}"

        prefix = "[PNL] " if log_type == "pnl" else ""
        self.state.logs.append(f"{prefix}{log_message}")
        if len(self.state.logs) > 100:
            self.state.logs.pop(0)

        if log_type == "pnl":
            self.logger.pnl_log(message)
        elif log_type == "error":
            self.logger.error_log(message)
        else:
            self.logger.trading_log(message)

    async def initialize(self) -> bool:
        """Initialize all components"""
        self.add_log(f"🚀 Initializing Bot ({', '.join(self.enabled_assets)})...")

        success = True

        # Initialize Polymarket Clients
        for asset in self.enabled_assets:
            pm = self.polymarkets[asset]

            if not await pm.initialize():
                self.add_log(f"❌ {asset} Polymarket Init Failed")
                success = False
                continue

            if not await pm.find_hourly_market():
                self.add_log(f"⚠ {asset} Hourly market not found")
            else:
                await pm.sync_position_from_api()
                self.add_log(
                    f"✅ {asset} Connected (Strike: ${pm.market.strike_price:,.2f})"
                )

            # 과거 정산되지 않은 포지션 체크 및 정산 (제거: 시작 시 블로킹 방지, 루프에서 처리)
            # redeemed = await pm.redeem_all_resolved_positions()
            # if redeemed > 0:
            #     self.add_log(f"💰 [{asset}] {redeemed}개의 과거 포지션을 정산했습니다.")

        # [Emergency] Cleanup on Start
        if self.config.emergency_cleanup_on_start:
            self.add_log(
                "🚨 [EMERGENCY] Cleanup mode enabled. Locking all positions..."
            )
            cleanup_count = 0
            for asset in self.enabled_assets:
                pm = self.polymarkets[asset]
                if pm.has_position:
                    hedge_dir = "DOWN" if pm.position.direction == "UP" else "UP"
                    self.add_log(
                        f"🧹 [{asset}] Emergency Hedge: Buying {pm.position.size:.2f} {hedge_dir} to lock."
                    )

                    # Force buy opposite
                    await pm.buy(
                        direction=hedge_dir,
                        size=pm.position.size,
                        strategy="emergency_cleanup",
                    )
                    cleanup_count += 1

            if cleanup_count > 0:
                self.add_log(
                    f"🚨 Processed {cleanup_count} emergency hedges. Auto-trade DISABLED for safety."
                )
                self.state.auto_trade = False
            else:
                self.add_log("✨ No active positions to clean up.")

        if not success:
            self.add_log("⚠ Some assets failed to initialize")

        # Set Wallet Address and Init Portfolio Manager
        first_pm = list(self.polymarkets.values())[0] if self.polymarkets else None
        if first_pm:
            self.state.wallet_address = first_pm.address
            self.portfolio_manager = PortfolioManager(first_pm)

        self.add_log("✅ Initialization Complete")
        return True

    async def update_state(self) -> None:
        """Update global state"""
        total_update_count = 0

        for asset in self.enabled_assets:
            binance = self.binance_feeds.get(asset)
            pm = self.polymarkets.get(asset)
            asset_state = self.state.assets.get(asset)

            if not binance or not pm or not asset_state:
                continue

            # Update Binance Data
            new_price = binance.get_price()
            if new_price > 0:
                asset_state.price = new_price
                stats = binance.get_24h_stats()
                asset_state.change_24h = stats["change"]
                asset_state.change_pct = stats["change_pct"]
                asset_state.high = stats["high"]
                asset_state.low = stats["low"]
                asset_state.volatility = binance.calculate_volatility()
                asset_state.momentum = binance.get_momentum()

            # Update Polymarket Data
            if pm.market.strike_price > 0:
                asset_state.strike_price = pm.market.strike_price

            if pm.market.end_time:
                asset_state.time_remaining = pm.get_time_remaining_str()
                asset_state.time_remaining_sec = pm.get_time_remaining()

            if pm.market.up_ask > 0:
                asset_state.up_ask = pm.market.up_ask
            if pm.market.up_bid > 0:
                asset_state.up_bid = pm.market.up_bid
            if pm.market.down_ask > 0:
                asset_state.down_ask = pm.market.down_ask
            if pm.market.down_bid > 0:
                asset_state.down_bid = pm.market.down_bid
            asset_state.spread = pm.get_spread()

            # Probability Analysis
            if asset_state.price > 0 and asset_state.strike_price > 0:
                result = self.prob_model.analyze(
                    current_price=asset_state.price,
                    strike_price=asset_state.strike_price,
                    time_remaining_seconds=pm.get_time_remaining(),
                    volatility_annual=asset_state.volatility,
                    market_up=asset_state.up_ask,
                    market_down=asset_state.down_ask,
                    spread_up=pm.market.spread_up,
                    spread_down=pm.market.spread_down,
                )

                asset_state.fair_up = result.fair_up
                asset_state.fair_down = result.fair_down
                asset_state.edge_up = result.edge_up
                asset_state.edge_down = result.edge_down
                asset_state.d2 = result.d2

            # Position Data
            pm.update_unrealized_pnl()
            asset_state.has_position = pm.has_position
            asset_state.position_direction = pm.position.direction
            asset_state.position_size = pm.position.size
            asset_state.position_avg_price = pm.position.avg_price
            asset_state.position_cost = pm.position.cost
            asset_state.position_pnl = pm.position.unrealized_pnl
            asset_state.position_strategy = pm.position.strategy
            asset_state.total_pnl = pm.total_pnl
            asset_state.transactions = pm.transactions

            # Sure-Bet Analysis
            if pm.market.yes_asks and pm.market.no_asks:
                opportunity = self.surebet_engine.analyze(
                    pm.market.yes_asks, pm.market.no_asks
                )
                asset_state.surebet_profitable = opportunity.is_profitable
                asset_state.surebet_spread = opportunity.spread
                asset_state.surebet_profit_rate = opportunity.profit_rate
                asset_state.surebet_max_size = opportunity.max_size
                asset_state.surebet_max_profit = opportunity.max_profit
                asset_state.surebet_vwap_yes = opportunity.vwap_yes
                asset_state.surebet_vwap_no = opportunity.vwap_no
                asset_state.surebet_yes_liquidity = opportunity.yes_liquidity
                asset_state.surebet_no_liquidity = opportunity.no_liquidity
                asset_state.surebet_reason = opportunity.reason

                if opportunity.is_profitable:
                    asset_state.signal = f"SUREBET +{opportunity.profit_rate:.2f}%"
                else:
                    asset_state.signal = "WAITING"

            total_update_count += binance.update_count

        # Sniper Status Update
        for asset in self.enabled_assets:
            pm = self.polymarkets.get(asset)
            if not pm:
                continue

            rem_sec = pm.get_time_remaining()
            rem_min = rem_sec / 60
            target_min = self.config.expiry_sniper_minutes_before

            sniper_state = self.expiry_sniper.states.get(asset)
            exec_count = sniper_state.executions_count if sniper_state else 0
            max_exec = self.config.expiry_sniper_max_times

            if rem_min > target_min:
                wait_min = rem_min - target_min
                status = f"Waiting ({wait_min:.1f}m)"
            elif exec_count >= max_exec:
                status = "Done (Max Exec)"
            else:
                status = f"ACTIVE! ({exec_count}/{max_exec})"

            self.state.sniper_info[asset] = status

        # Global Metadata
        self.state.update_count = total_update_count
        self.state.last_update = datetime.now().strftime("%H:%M:%S")
        self.state.is_connected = any(
            pm.is_initialized for pm in self.polymarkets.values()
        )

        # Balance Update (Every 5s)
        if self.state.is_connected and (time.time() - self.last_balance_update > 5.0):
            for pm in self.polymarkets.values():
                if pm.is_initialized:
                    try:
                        bal = await pm.get_usdc_balance()
                        invested = await pm.get_global_invested_value()
                        self.state.usdc_balance = bal
                        self.state.reserved_balance = (
                            0.0  # Reset reservation on fresh sync
                        )
                        self.state.portfolio_value = bal + invested

                        if self.portfolio_manager:
                            self.portfolio_manager.add_snapshot(bal, invested)

                        self.last_balance_update = time.time()
                        break
                    except Exception:
                        pass

    async def trading_loop(self) -> None:
        """Strategy Execution Loop"""
        while self._running:
            try:
                if not self.state.auto_trade:
                    await asyncio.sleep(1)
                    continue

                for asset in self.enabled_assets:
                    pm = self.polymarkets.get(asset)
                    asset_state = self.state.assets.get(asset)

                    if not pm or not asset_state:
                        continue

                    market_up_ask = pm.market.up_ask
                    market_down_ask = pm.market.down_ask
                    market_up_bid = pm.market.up_bid
                    market_down_bid = pm.market.down_bid

                    fair_up = asset_state.fair_up
                    fair_down = asset_state.fair_down

                    if market_up_ask <= 0 or market_down_ask <= 0:
                        continue

                    # ==================================================================
                    # GLOBAL SAFETY NET (Emergency Stop Loss)
                    # 전략과 무관하게 -20% 이상 손실 시 강제 헷지
                    # ==================================================================
                    if (
                        asset_state.has_position
                        and not "hedged" in asset_state.position_strategy
                    ):
                        # PnL 직접 재계산 (Bid 기준)
                        current_val = (
                            market_up_bid
                            if asset_state.position_direction == "UP"
                            else market_down_bid
                        )
                        if asset_state.position_avg_price > 0:
                            pnl_pct = (
                                (current_val - asset_state.position_avg_price)
                                / asset_state.position_avg_price
                            ) * 100

                            # -20% 이하이고, 아직 헷지 안된 상태면 강제 실행
                            if pnl_pct <= -self.config.global_stoploss_pct:
                                self.add_log(
                                    f"🚨 [GLOBAL SAFETY] {asset} CRITICAL LOSS: {pnl_pct:.1f}%. Forcing Hedge."
                                )
                                hedge_dir = (
                                    "DOWN"
                                    if asset_state.position_direction == "UP"
                                    else "UP"
                                )

                                # 헷지 실행
                                hedge_result = await pm.buy(
                                    direction=hedge_dir,
                                    size=asset_state.position_size,
                                    strategy="global_safety_hedge",
                                )

                                if not hedge_result:
                                    self.add_log(
                                        f"⚠️ [GLOBAL SAFETY] Hedge Failed. Retrying in 30s to avoid spam..."
                                    )
                                    await asyncio.sleep(30)

                                continue  # 헷지 실행했으므로 다음으로 넘어감

                    # ==================================================================
                    # NEW: Buzzer Beater (Expiry Sniper) HEDGE LOGIC
                    # ==================================================================
                    if (
                        asset_state.has_position
                        and asset_state.position_strategy == "expiry_sniper"
                        and asset_state.position_entry_prob >= 97.0
                    ):
                        current_prob = 0.0
                        # 현재 내 포지션의 가치는 반대 포지션의 매수가격(ask)으로 추정할 수 있다
                        if asset_state.position_direction == "UP":
                            current_prob = (1 - market_down_ask) * 100
                        else:  # DOWN
                            current_prob = (1 - market_up_ask) * 100

                        # Debug log to monitor the probability check
                        self.add_log(
                            f"~Hedge Check~ [{asset}] Entry: {asset_state.position_entry_prob:.1f}%, Now: {current_prob:.1f}% (Trig: <{self.config.sniper_hedge_prob_threshold}%)"
                        )

                        if current_prob < self.config.sniper_hedge_prob_threshold:
                            hedge_direction = (
                                "DOWN"
                                if asset_state.position_direction == "UP"
                                else "UP"
                            )
                            self.add_log(
                                f"📉 [{asset}] SNIPER HEDGE! Prob dropped from {asset_state.position_entry_prob:.1f}% to {current_prob:.1f}%. Hedging {asset_state.position_size:.2f} shares {hedge_direction}."
                            )

                            # 동일 수량으로 반대 포지션 매수
                            hedge_result = await pm.buy(
                                direction=hedge_direction,
                                size=asset_state.position_size,  # 동일 수량 사용
                                strategy="expiry_sniper_hedged",
                            )

                            if hedge_result:
                                self.add_log(f"✅ [{asset}] Sniper Hedge successful.")
                                # 헷지 완료 상태로 변경하여 중복 실행 방지
                                pm.position.strategy = "expiry_sniper_hedged"
                            else:
                                self.add_log(f"❌ [{asset}] Sniper Hedge FAILED.")

                            continue  # 이번 루프에서는 이 자산에 대한 추가 로직 생략

                    # 이미 헷지된 포지션이 있다면, 새로운 스나이퍼 진입 방지
                    if (
                        asset_state.has_position
                        and "hedged" in asset_state.position_strategy
                    ):
                        continue

                    # 0. Expiry Sniper (기존 진입 로직)
                    sniper_action = self.expiry_sniper.analyze(
                        asset_type=asset,
                        time_remaining_sec=pm.get_time_remaining(),
                        market_up_ask=market_up_ask,
                        market_down_ask=market_down_ask,
                        has_position=asset_state.has_position,
                    )

                    if sniper_action:
                        self.add_log(
                            f"🎯 [{asset}] SNIPER! {sniper_action['direction']} Prob: {sniper_action['prob']:.1f}%"
                        )
                        result = await pm.buy(
                            direction=sniper_action["direction"],
                            amount_usdc=sniper_action["amount"],
                            edge=0.0,
                            strategy="expiry_sniper",  # 진입 시 전략 이름 지정
                        )
                        if result:
                            self.expiry_sniper.record_execution(asset)
                            # NEW: 진입 시점의 확률 기록
                            asset_state.position_entry_prob = sniper_action["prob"]
                        continue

                    # 2. Sure-Bet Arbitrage
                    if (
                        self.config.surebet_enabled
                        and asset_state.surebet_profitable
                        and not asset_state.has_position
                    ):
                        self.add_log(
                            f"💰 [{asset}] Sure-Bet opportunity found! Profit: {asset_state.surebet_profit_rate:.2f}%"
                        )

                        # 기회를 바탕으로 주문 파라미터 계산
                        # ArbitrageOpportunity 객체를 생성하여 전달
                        opportunity = ArbitrageOpportunity(
                            is_profitable=asset_state.surebet_profitable,
                            spread=asset_state.surebet_spread,
                            profit_rate=asset_state.surebet_profit_rate,
                            max_size=asset_state.surebet_max_size,
                            max_profit=asset_state.surebet_max_profit,
                            vwap_yes=asset_state.surebet_vwap_yes,
                            vwap_no=asset_state.surebet_vwap_no,
                        )

                        order_params = self.surebet_engine.calculate_order_params(
                            opportunity=opportunity,
                            amount_usdc=self.config.bet_amount_usdc,
                        )

                        if order_params:
                            # Execute the arbitrage
                            result = await pm.execute_surebet(
                                yes_size=order_params["yes_size"],
                                yes_max_price=order_params["yes_max_price"],
                                no_size=order_params["no_size"],
                                no_max_price=order_params["no_max_price"],
                                profit_rate=order_params["profit_rate"],
                            )

                            if result["success"]:
                                self.add_log(
                                    f"✅ [{asset}] Sure-Bet executed successfully."
                                )
                            elif result["panic_mode"]:
                                self.add_log(
                                    f"🚨 [{asset}] Sure-Bet failed, panic mode handled."
                                )
                            else:
                                self.add_log(
                                    f"❌ [{asset}] Sure-Bet execution failed: {result['message']}"
                                )
                            continue

                    # 1. Edge Hedge Strategy (Manage Positions)

                    # 만약 포지션이 있는데, 헷지 전략이 추적하고 있지 않다면, 추적 시작
                    if (
                        asset_state.has_position
                        and not self.edge_hedge_strategy.get_position_status(asset)
                    ):
                        # Wait for valid data
                        if (
                            asset_state.position_avg_price <= 0
                            or asset_state.position_size <= 0
                        ):
                            # self.add_log(f"Waiting for valid position data for {asset}...")
                            pass
                        else:
                            self.add_log(
                                f"~EdgeHedge~ [{asset}] 새 포지션 감지됨. 헷지 추적 시작."
                            )

                            # Calculate approx params
                            fair_val = (
                                asset_state.fair_up
                                if asset_state.position_direction == "UP"
                                else asset_state.fair_down
                            )
                            # Edge at current moment (not entry moment, but best we have)
                            current_edge = (
                                fair_val - asset_state.position_avg_price
                            ) * 100

                            self.edge_hedge_strategy.record_entry(
                                asset_type=asset,
                                direction=asset_state.position_direction,
                                entry_price=asset_state.position_avg_price,
                                size=asset_state.position_size,
                                cost=asset_state.position_cost,
                                fair_price=fair_val,
                                edge=current_edge,
                            )

                    position = self.edge_hedge_strategy.get_position_status(asset)
                    if position and not position["is_hedged"]:
                        # Profit Hedge
                        profit_hedge = self.edge_hedge_strategy.analyze_profit_hedge(
                            asset,
                            market_up_bid,
                            market_down_bid,
                            market_up_ask,
                            market_down_ask,
                        )
                        if profit_hedge:
                            self.add_log(
                                f"🎯 [{asset}] Profit Hedge! Gain +{profit_hedge['position_gain_pct']:.1f}%"
                            )
                            await pm.buy(
                                direction=profit_hedge["direction"],
                                size=position["size"],
                                edge=profit_hedge["expected_profit_pct"],
                                strategy="edge_hedge_profit",
                            )
                            # Record hedge logic omitted for brevity, assuming pm.buy handles basic logic or we add it here
                            # Note: The original code called self.edge_hedge_strategy.record_hedge here.
                            # We should include it.
                            hedge_price = profit_hedge["opposite_price"]
                            hedge_size = position["size"]
                            hedge_cost = hedge_size * hedge_price
                            self.edge_hedge_strategy.record_hedge(
                                asset,
                                "PROFIT",
                                profit_hedge["direction"],
                                hedge_price,
                                hedge_size,
                                hedge_cost,
                                profit_hedge["expected_profit_pct"],
                            )
                            continue

                        # Stoploss Hedge
                        stoploss_hedge = (
                            self.edge_hedge_strategy.analyze_stoploss_hedge(
                                asset,
                                market_up_bid,
                                market_down_bid,
                                market_up_ask,
                                market_down_ask,
                            )
                        )
                        self.add_log(
                            f"~EdgeHedge SL Result~ [{asset}] Signal: {stoploss_hedge is not None}"
                        )
                        if stoploss_hedge:
                            print(
                                f"🛑 [STOPLOSS TRIGGERED] {asset} Loss: {stoploss_hedge['position_loss_pct']:.1f}%"
                            )
                            hedge_size = position["size"]
                            hedge_price = stoploss_hedge["opposite_price"]

                            # Min value check (e.g. $0.5)
                            if hedge_size * hedge_price < 0.5:
                                self.add_log(
                                    f"⚠️ [Stoploss] Skipping dust order: {hedge_size:.4f} shares @ {hedge_price:.4f}"
                                )
                                continue

                            self.add_log(
                                f"🛑 [{asset}] Stoploss Hedge! Loss {stoploss_hedge['position_loss_pct']:.1f}% | Buy {hedge_size:.2f} @ {hedge_price:.4f}"
                            )

                            await pm.buy(
                                direction=stoploss_hedge["direction"],
                                size=hedge_size,
                                edge=stoploss_hedge["expected_pnl_pct"],
                                strategy="edge_hedge_stoploss",
                            )
                            hedge_price = stoploss_hedge["opposite_price"]
                            hedge_size = position["size"]
                            hedge_cost = hedge_size * hedge_price
                            self.edge_hedge_strategy.record_hedge(
                                asset,
                                "STOPLOSS",
                                stoploss_hedge["direction"],
                                hedge_price,
                                hedge_size,
                                hedge_cost,
                                stoploss_hedge["expected_pnl_pct"],
                            )
                            continue

                    # 신규 진입 (Edge Hedge Entry) - 포지션이 없을 때
                    elif not asset_state.has_position:
                        # [Sync Fix] If state says no position, force clear strategy memory to allow re-entry
                        if self.edge_hedge_strategy.get_position_status(asset):
                            self.add_log(
                                f"🔄 [Sync] Clearing stuck strategy memory for {asset}"
                            )
                            self.edge_hedge_strategy.clear_position(asset)

                        # Debug entry check
                        # self.add_log(f"[Debug] Checking Entry {asset}: Fair({fair_up:.2f}/{fair_down:.2f}) Market({market_up_ask:.2f}/{market_down_ask:.2f})")

                        entry_signal = self.edge_hedge_strategy.analyze_entry(
                            asset_type=asset,
                            fair_up=fair_up,
                            fair_down=fair_down,
                            market_up=market_up_ask,
                            market_down=market_down_ask,
                        )

                        if entry_signal:
                            direction = entry_signal["direction"]
                            edge = entry_signal["edge"]
                            price = entry_signal["market"]

                            # Buy fixed amount (or use Kelly if implemented there)
                            buy_amount = self.config.bet_amount_usdc

                            # [Safety Check] Ensure we have enough funds for Entry + Future Hedge
                            current_balance = await pm.get_usdc_balance()
                            effective_balance = (
                                current_balance - self.state.reserved_balance
                            )
                            required_balance = buy_amount * 2.0  # Reserve for 1:1 Hedge

                            if effective_balance < required_balance:
                                self.add_log(
                                    f"⚠️ [EdgeHedge] Skipping Entry {asset}: Insufficient funds. Need ${required_balance:.2f}, Have ${effective_balance:.2f} (Reserved: ${self.state.reserved_balance:.2f})"
                                )
                                continue

                            # Reserve funds immediately
                            self.state.reserved_balance += buy_amount

                            self.add_log(
                                f"🚀 [EdgeHedge] Entry Signal: {direction} (Edge: {edge:.1f}%)"
                            )

                            result = await pm.buy(
                                direction=direction,
                                amount_usdc=buy_amount,
                                edge=edge,
                                strategy="edge_hedge_entry",
                            )

                            if result:
                                # Record entry immediately (don't wait for next loop)
                                # Recalculate size based on execution
                                executed_size = buy_amount / price  # Approx
                                self.edge_hedge_strategy.record_entry(
                                    asset_type=asset,
                                    direction=direction,
                                    entry_price=price,
                                    fair_price=entry_signal["fair"],
                                    edge=edge,
                                    size=executed_size,
                                    cost=buy_amount,
                                )

                    if (
                        asset_state.has_position
                        and asset_state.position_strategy == "contrarian"
                    ):
                        edge = (
                            asset_state.edge_up
                            if asset_state.position_direction == "UP"
                            else asset_state.edge_down
                        )
                        strategy_type = asset_state.position_strategy
                        exit_signal = self.trend_strategy.analyze_exit(
                            direction=asset_state.position_direction,
                            strategy=strategy_type,
                            edge=edge,
                            pnl_pct=asset_state.position_pnl,
                            time_remaining_seconds=pm.get_time_remaining(),
                        )
                        if exit_signal:
                            hedge_dir = (
                                "DOWN"
                                if asset_state.position_direction == "UP"
                                else "UP"
                            )
                            self.add_log(
                                f"📊 [{asset}] Trend Exit ({strategy_type}): {exit_signal['reason']}. Selling {asset_state.position_size:.2f} {asset_state.position_direction}..."
                            )
                            result = await pm.buy(
                                direction=hedge_dir,
                                size=asset_state.position_size,
                                strategy="trend_exit",
                            )
                            if result:
                                self.add_log(f"✅ [{asset}] Trend Exit successful.")
                            continue

                    trend_entry = self.trend_strategy.analyze_entry(
                        btc_price=asset_state.price,
                        strike_price=asset_state.strike_price,
                        fair_up=asset_state.fair_up,
                        fair_down=asset_state.fair_down,
                        market_up=market_up_ask,
                        market_down=market_down_ask,
                        has_position=asset_state.has_position,
                    )
                    if trend_entry:
                        direction = trend_entry["direction"]
                        strategy_type = trend_entry["strategy"]
                        edge = trend_entry["edge"]
                        amount = trend_entry["amount_usdc"]
                        self.add_log(
                            f"📊 [{asset}] Trend Entry ({strategy_type}): {direction} (Edge: {edge:.1f}%)"
                        )
                        result = await pm.buy(
                            direction=direction,
                            amount_usdc=amount,
                            edge=edge,
                            strategy=strategy_type,
                        )
                        if result:
                            self.add_log(f"✅ [{asset}] Trend Entry successful.")

                await asyncio.sleep(0.5)

                # Heartbeat Log (Every 60s approx)
                if time.time() % 60 < 1:
                    for asset in self.enabled_assets:
                        state = self.state.assets.get(asset)
                        if state:
                            msg = f"💓 [{asset}] Price: {state.price:.0f} | Spread: {state.spread:.3f} | Pos: {state.position_size:.1f} ({state.position_pnl:.2f})"
                            if state.surebet_profitable:
                                msg += f" | SureBet: +{state.surebet_profit_rate:.2f}%"
                            self.add_log(msg)
                    await asyncio.sleep(1)  # Prevent duplicate logs

            except Exception as e:
                self.add_log(f"Trading loop error: {e}")
                await asyncio.sleep(5)

    async def market_refresh_loop(self) -> None:
        """Market Data Refresh & Rollover Loop"""
        loop_count = 0
        while self._running:
            try:
                for asset in self.enabled_assets:
                    pm = self.polymarkets.get(asset)
                    if not pm:
                        continue

                    # Rollover check
                    time_remaining = pm.get_time_remaining()
                    if time_remaining <= 0 and pm.market.end_time:
                        self.add_log(f"⚠ [{asset}] Market Expired. Rolling over...")
                        await pm.archive_current_market()
                        pm.market = MarketData()
                        if await pm.find_hourly_market():
                            self.add_log(
                                f"✅ [{asset}] New Market Found: ${pm.market.strike_price:,.2f}"
                            )
                            await pm.sync_position_from_api()
                        else:
                            self.add_log(f"❌ [{asset}] No next market found")
                            continue

                    await pm.update_full_orderbook()

                loop_count += 1
                if loop_count % 20 == 0:
                    for pm in self.polymarkets.values():
                        if pm:
                            await pm.sync_position_from_api()

                if loop_count % 60 == 0:
                    for asset in self.enabled_assets:
                        pm = self.polymarkets.get(asset)
                        if pm and pm.expired_markets:
                            for old_market in pm.expired_markets[:]:
                                if await pm.redeem_market(old_market):
                                    pm.expired_markets.remove(old_market)
                                    self.add_log(
                                        f"💰 [{asset}] Redeemed archived expired market"
                                    )

                    # 2. (재시도) 전체 정산되지 않은 포지션 스캔 및 정산 (전체 포트폴리오에 대해 한 번만 실행)
                    first_pm = next(iter(self.polymarkets.values()), None)
                    if first_pm:
                        self.add_log("[Redeem] 주기적인 정산 스캔 시작...")
                        redeemed_count = await first_pm.redeem_all_resolved_positions()
                        if redeemed_count > 0:
                            self.add_log(
                                f"💰 Redeemed {redeemed_count} previously unresolved positions."
                            )

                    for asset in self.enabled_assets:
                        pm = self.polymarkets.get(asset)
                        if pm:
                            asset_state = self.state.assets.get(asset)
                            if asset_state:
                                self.pnl_db.record_snapshot(
                                    wallet_id=self.bot_id or "0",
                                    asset=asset,
                                    total_pnl=asset_state.total_pnl,
                                    realized_pnl=pm.realized_pnl,
                                    unrealized_pnl=pm.position.unrealized_pnl,
                                    position_size=pm.position.size,
                                    portfolio_value=self.state.portfolio_value,
                                )

                    if loop_count % 120 == 0:
                        for asset in self.enabled_assets:
                            pm = self.polymarkets.get(asset)
                            if not pm:
                                continue

                            try:
                                # Fetch all positions for this asset's market
                                positions = await pm.fetch_positions()
                                if not positions:
                                    continue

                                # Group by Condition ID
                                market_positions = {}
                                for pos in positions:
                                    cond_id = pos.get("conditionId")
                                    if not cond_id:
                                        continue

                                    if cond_id not in market_positions:
                                        market_positions[cond_id] = {
                                            "YES": 0.0,
                                            "NO": 0.0,
                                            "title": pos.get("title"),
                                        }

                                    outcome = pos.get("outcome", "").upper()
                                    size = float(pos.get("size", 0))

                                    if outcome == "YES" or outcome == "UP":
                                        market_positions[cond_id]["YES"] += size
                                    elif outcome == "NO" or outcome == "DOWN":
                                        market_positions[cond_id]["NO"] += size

                                # Check for merge opportunities
                                for cond_id, sizes in market_positions.items():
                                    mergeable = min(sizes["YES"], sizes["NO"])
                                    # Threshold: Merge if > 1 USDC worth (approx 1 share)
                                    if mergeable > 1.0:
                                        self.add_log(
                                            f"🔄 [Merge] Found mergeable positions for {sizes['title']}: {mergeable:.2f} shares"
                                        )
                                        await pm.merge_positions(cond_id, mergeable)

                            except Exception as e:
                                self.add_log(f"Merge check failed: {e}")

                if loop_count >= 10000:
                    loop_count = 0
                await asyncio.sleep(0.5)
            except Exception as e:
                self.add_log(f"Market refresh error: {e}")
                loop_count += 1
                await asyncio.sleep(5)

    async def state_refresh_loop(self) -> None:
        """Internal loop to keep bot state (prices, balance, edge) updated"""
        while self._running:
            try:
                await self.update_state()
                await asyncio.sleep(1.0)
            except Exception as e:
                self.add_log(f"State refresh loop error: {e}")
                await asyncio.sleep(5)

    async def start(self):
        """Start the bot loops"""
        if not await self.initialize():
            return

        self._running = True

        # Start Binance feeds
        tasks = []
        for binance in self.binance_feeds.values():
            tasks.append(asyncio.create_task(binance.start()))

        tasks.append(
            asyncio.create_task(self.state_refresh_loop())
        )  # NEW: Independent state refresh
        tasks.append(asyncio.create_task(self.market_refresh_loop()))
        tasks.append(asyncio.create_task(self.trading_loop()))

        return tasks

    async def stop(self):
        """Stop the bot and lock positions"""
        self.add_log("🛑 Bot stop sequence initiated...")

        # [Quit Lock] Lock all positions before exit
        self.add_log("🔒 Checking for open positions to lock...")
        for asset in self.enabled_assets:
            pm = self.polymarkets.get(asset)
            if pm and pm.has_position:
                # Check if already hedged/locked to avoid double spending
                if "hedged" in pm.position.strategy or "lock" in pm.position.strategy:
                    self.add_log(
                        f"👌 [{asset}] Position already locked/hedged. Skipping."
                    )
                    continue

                hedge_dir = "DOWN" if pm.position.direction == "UP" else "UP"
                self.add_log(
                    f"🔒 [{asset}] Locking position: Buying {pm.position.size:.2f} {hedge_dir}..."
                )

                try:
                    await pm.buy(
                        direction=hedge_dir, size=pm.position.size, strategy="quit_lock"
                    )
                    self.add_log(f"✅ [{asset}] Position Locked.")
                except Exception as e:
                    self.add_log(f"❌ [{asset}] Failed to lock position: {e}")

        self.add_log("👋 Shutting down tasks...")
        self._running = False
        for binance in self.binance_feeds.values():
            await binance.stop()
        for pm in self.polymarkets.values():
            await pm.close()
