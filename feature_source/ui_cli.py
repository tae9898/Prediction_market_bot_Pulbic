"""
BTC Polymarket ARB Bot - CLI Interface (Rich)
"""

import asyncio
import sys
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.align import Align

from bot_core import TradingBot, BotState, AssetState
from config import Config

# ========== UI Panels ==========

def create_sniper_panel(state: BotState, config: Config) -> Panel:
    """Expiry Sniper Status Panel"""
    content = Text()
    content.append("   ⚙️ Config: ", style="dim")
    content.append(f"{config.expiry_sniper_minutes_before}m before, ", style="cyan")
    content.append(f">={config.expiry_sniper_prob_threshold}%\n", style="cyan")
    content.append("   ─────────────────────\n", style="dim")
    
    for asset, info in state.sniper_info.items():
        content.append(f"   {asset}: ", style="bold")
        content.append(f"{info}\n", style="yellow")
        
    if not state.sniper_info:
        content.append("   Waiting for market data...\n", style="dim italic")
    
    return Panel(content, title="▓▓ SNIPER STATUS ▓▓", border_style="red", height=8)

def create_header(state: BotState) -> Panel:
    """Header Panel"""
    now = datetime.now().strftime("%H:%M:%S")
    title = Text()
    title.append("  ⚡ ", style="yellow")
    title.append("BTC POLYMARKET ARB BOT", style="bold cyan")
    
    status_icon = "●" if state.is_connected else "○"
    status_color = "green" if state.is_connected else "red"
    status_text = "CONNECTED" if state.is_connected else "DISCONNECTED"
    
    right = Text()
    right.append(f"[{now}] ", style="dim")
    if state.is_connected:
        right.append(f"Cash: ${state.usdc_balance:,.2f} ", style="bold green")
        port_val = state.portfolio_value if state.portfolio_value > state.usdc_balance else state.usdc_balance
        right.append(f"Equity: ~${port_val:,.2f}  ", style="bold cyan")
    
    right.append(f"[{status_icon} {status_text}]", style=f"bold {status_color}")
    
    header_text = Text()
    header_text.append(str(title))
    header_text.append(" " * 10)
    header_text.append(str(right))
    
    return Panel(Align.center(header_text), style="bold", height=3)

def create_binance_panel(asset: AssetState) -> Panel:
    """Binance Live Panel"""
    content = Text()
    price_str = f"${asset.price:,.2f}"
    change_color = "green" if asset.change_pct >= 0 else "red"
    change_str = f"{'+' if asset.change_pct >= 0 else ''}{asset.change_pct:.2f}%"
    
    content.append(f"   {asset.asset_type}/USDT   ", style="bold")
    content.append(price_str, style=f"bold {change_color}")
    content.append(f"  {change_str}\n", style=change_color)
    
    momentum_style = {"BULLISH": "green", "BEARISH": "red", "NEUTRAL": "yellow"}.get(asset.momentum, "white")
    content.append("              ", style="dim")
    if asset.momentum == "BULLISH": content.append("▲▲ BULLISH\n", style=momentum_style)
    elif asset.momentum == "BEARISH": content.append("▼▼ BEARISH\n", style=momentum_style)
    else: content.append("── NEUTRAL\n", style=momentum_style)
    
    content.append("\n")
    change_24h_color = "green" if asset.change_24h >= 0 else "red"
    content.append("   24h:       ", style="dim")
    content.append(f"{'+' if asset.change_24h >= 0 else ''}${asset.change_24h:,.2f}", style=change_24h_color)
    content.append(f"  ({'+' if asset.change_pct >= 0 else ''}{asset.change_pct:.2f}%)\n", style=change_24h_color)
    
    vol_pct = asset.volatility * 100
    vol_bar = "█" * int(min(vol_pct / 10, 10)) + "░" * (10 - int(min(vol_pct / 10, 10)))
    content.append("   Vol:       ", style="dim")
    content.append(f"{vol_pct:.1f}% ", style="cyan")
    content.append(f"{vol_bar}\n", style="cyan")
    
    content.append("   High/Low:  ", style="dim")
    content.append(f"${asset.high:,.0f} / ${asset.low:,.0f}", style="white")
    
    return Panel(content, title=f"▓▓ {asset.asset_type} BINANCE LIVE ▓▓", border_style="blue")

def create_polymarket_panel(asset: AssetState) -> Panel:
    """Polymarket Panel"""
    content = Text()
    content.append("   Strike:    ", style="dim")
    content.append(f"${asset.strike_price:,.2f}\n", style="bold yellow")
    content.append("   Expires:   ", style="dim")
    content.append(f"⏱ {asset.time_remaining}\n", style="bold white")
    content.append("\n")
    
    content.append("   ▲ UP    ", style="green")
    content.append(f"Ask: {asset.up_ask*100:.1f}%  Bid: {asset.up_bid*100:.1f}%\n", style="white")
    
    content.append("   ▼ DOWN  ", style="red")
    content.append(f"Ask: {asset.down_ask*100:.1f}%  Bid: {asset.down_bid*100:.1f}%\n", style="white")
    
    content.append("   Spread: ", style="dim")
    content.append(f"{asset.spread*100:.1f}¢", style="yellow")
    
    return Panel(content, title=f"▓▓ {asset.asset_type} POLYMARKET ▓▓", border_style="magenta", height=10)

def create_probability_panel(asset: AssetState) -> Panel:
    """Probability Model Panel"""
    content = Text()
    content.append("   ▲ UP\n", style="bold green")
    
    fair_up_pct = int(asset.fair_up * 40)
    fair_up_bar = "█" * fair_up_pct + "░" * (40 - fair_up_pct)
    content.append("   FAIR   ", style="cyan")
    content.append(f"{fair_up_bar} ", style="cyan")
    content.append(f"{asset.fair_up*100:.1f}%\n", style="bold cyan")
    
    market_up_pct = int(asset.up_ask * 40)
    market_up_bar = "█" * market_up_pct + "░" * (40 - market_up_pct)
    content.append("   MARKET ", style="yellow")
    content.append(f"{market_up_bar} ", style="yellow")
    content.append(f"{asset.up_ask*100:.1f}%\n", style="bold yellow")
    
    if asset.edge_up > 0:
        edge_label = "DISCOUNT"
        edge_style = "bold green"
    else:
        edge_label = "PREMIUM"
        edge_style = "bold red"
    content.append(f"   EDGE   {edge_label} ", style="dim")
    content.append(f"{'+' if asset.edge_up >= 0 else ''}{asset.edge_up:.2f}%\n", style=edge_style)
    
    content.append("\n")
    content.append("   ▼ DOWN\n", style="bold red")
    
    fair_down_pct = int(asset.fair_down * 40)
    fair_down_bar = "█" * fair_down_pct + "░" * (40 - fair_down_pct)
    content.append("   FAIR   ", style="cyan")
    content.append(f"{fair_down_bar} ", style="cyan")
    content.append(f"{asset.fair_down*100:.1f}%\n", style="bold cyan")
    
    market_down_pct = int(asset.down_ask * 40)
    market_down_bar = "█" * market_down_pct + "░" * (40 - market_down_pct)
    content.append("   MARKET ", style="yellow")
    content.append(f"{market_down_bar} ", style="yellow")
    content.append(f"{asset.down_ask*100:.1f}%\n", style="bold yellow")
    
    if asset.edge_down > 0:
        edge_label = "DISCOUNT"
        edge_style = "bold green"
    else:
        edge_label = "PREMIUM"
        edge_style = "bold red"
    content.append(f"   EDGE   {edge_label} ", style="dim")
    content.append(f"{'+' if asset.edge_down >= 0 else ''}{asset.edge_down:.2f}%\n", style=edge_style)
    
    content.append(f"\n   d2: {asset.d2:+.4f}", style="dim")
    
    return Panel(content, title=f"▓▓ {asset.asset_type} FAIR vs MARKET ▓▓", border_style="cyan")

def create_transactions_panel(state: BotState) -> Panel:
    """Transactions Panel"""
    all_transactions = []
    for asset_name, asset_state in state.assets.items():
        for tx in asset_state.transactions:
            tx_copy = tx.copy()
            tx_copy['asset'] = asset_name
            all_transactions.append(tx_copy)
    
    all_transactions.sort(key=lambda x: x.get('time', ''), reverse=True)
    
    if not all_transactions:
        return Panel(Text("   No recent transactions", style="dim italic"), title="▓▓ RECENT TRANSACTIONS ▓▓", border_style="white")
    
    table = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 1))
    table.add_column("ASSET", width=5)
    table.add_column("TIME", width=10)
    table.add_column("SIDE", width=6)
    table.add_column("DIR", width=6)
    table.add_column("PRICE", width=8)
    table.add_column("SIZE", width=8)
    table.add_column("INFO", width=15)
    
    for tx in all_transactions[:5]:
        side_color = "green" if tx.get("side") == "BUY" else "red"
        dir_icon = "▲ UP" if tx.get("direction") == "UP" else "▼ DN"
        table.add_row(
            tx.get("asset", ""), tx.get("time", ""),
            Text(tx.get("side", ""), style=side_color), dir_icon,
            f"${tx.get('price', 0):.2f}", str(int(tx.get("size", 0))), tx.get("info", "")
        )
    
    return Panel(table, title="▓▓ RECENT TRANSACTIONS ▓▓", border_style="white", height=10)

def create_debug_panel(state: BotState) -> Panel:
    """Debug Logs Panel"""
    if not state.logs:
        return Panel(Text("   Waiting for logs...", style="dim italic"), title="▓▓ DEBUG LOGS ▓▓", border_style="white", height=10)
    
    log_text = Text()
    for log in state.logs[-8:]:
        log_text.append(f"{log}\n")
        
    return Panel(log_text, title="▓▓ DEBUG LOGS ▓▓", border_style="cyan", height=10)

def create_footer(state: BotState) -> Panel:
    """Footer Panel"""
    content = Text()
    
    signals = []
    total_pnl = 0.0
    for asset_name, asset_state in state.assets.items():
        if "SUREBET" in asset_state.signal:
            signals.append(f"{asset_name}:🟢")
        total_pnl += asset_state.total_pnl
    
    signal_str = " ".join(signals) if signals else "WAITING"
    signal_style = "bold green" if signals else "dim"
    signal_icon = "🟢" if signals else "⚪"
    
    content.append(f"  {signal_icon} SIGNAL: ", style="dim")
    content.append(signal_str, style=signal_style)
    content.append("  │  ", style="dim")
    
    auto_icon = "🟢 ON" if state.auto_trade else "🔴 OFF"
    content.append(f"Auto: {auto_icon}", style="dim")
    content.append("  │  ", style="dim")
    
    content.append("[A]uto [Q]uit", style="dim italic")
    content.append("  │  ", style="dim")
    
    pnl_color = "green" if total_pnl >= 0 else "red"
    pnl_str = f"{'+' if total_pnl >= 0 else ''}${total_pnl:.2f}"
    content.append("Total PnL: ", style="dim")
    content.append(pnl_str, style=f"bold {pnl_color}")
    
    return Panel(Align.center(content), style="dim", height=3)

def init_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )
    layout["main"].split_column(
        Layout(name="assets_row", size=20),
        Layout(name="probability_row", size=18),
        Layout(name="bottom_section"),
    )
    layout["assets_row"].split_row(Layout(name="btc_column"), Layout(name="eth_column"))
    layout["btc_column"].split_column(Layout(name="btc_binance", ratio=1), Layout(name="btc_polymarket", ratio=1))
    layout["eth_column"].split_column(Layout(name="eth_binance", ratio=1), Layout(name="eth_polymarket", ratio=1))
    layout["probability_row"].split_row(Layout(name="btc_prob"), Layout(name="eth_prob"), Layout(name="sniper", ratio=1))
    layout["bottom_section"].split_row(Layout(name="transactions", ratio=1), Layout(name="debug", ratio=1))
    return layout

def update_layout(layout: Layout, state: BotState, config: Config) -> None:
    layout["header"].update(create_header(state))
    layout["footer"].update(create_footer(state))
    
    if "BTC" in state.assets:
        btc = state.assets["BTC"]
        layout["btc_binance"].update(create_binance_panel(btc))
        layout["btc_polymarket"].update(create_polymarket_panel(btc))
        layout["btc_prob"].update(create_probability_panel(btc))
    else:
        layout["btc_column"].update(Panel("BTC Not Enabled"))
        
    if "ETH" in state.assets:
        eth = state.assets["ETH"]
        layout["eth_binance"].update(create_binance_panel(eth))
        layout["eth_polymarket"].update(create_polymarket_panel(eth))
        layout["eth_prob"].update(create_probability_panel(eth))
    else:
        layout["eth_column"].update(Panel("ETH Not Enabled"))
        
    layout["sniper"].update(create_sniper_panel(state, config))
    layout["transactions"].update(create_transactions_panel(state))
    layout["debug"].update(create_debug_panel(state))

async def run_cli(bot: TradingBot):
    """Run CLI Interface"""
    console = Console()
    layout = init_layout()
    
    # Start bot tasks if not already started
    if not bot._running:
        bot_tasks = await bot.start()
    
    # Keyboard handler
    async def keyboard_listener():
        if sys.platform == 'win32':
            import msvcrt
            while bot._running:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', errors='ignore').upper()
                    if key == 'A': bot.state.auto_trade = not bot.state.auto_trade
                    elif key == 'Q': bot._running = False
                await asyncio.sleep(0.1)
        else:
            import termios, tty, select
            fd = sys.stdin.fileno()
            try:
                old_settings = termios.tcgetattr(fd)
            except:
                return
            try:
                tty.setcbreak(fd)
                while bot._running:
                    if select.select([sys.stdin], [], [], 0)[0]:
                        key = sys.stdin.read(1).upper()
                        if key == 'A': bot.state.auto_trade = not bot.state.auto_trade
                        elif key == 'Q': bot._running = False
                    await asyncio.sleep(0.1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    kb_task = asyncio.create_task(keyboard_listener())
    
    try:
        with Live(layout, auto_refresh=False, console=console, screen=True) as live:
            while bot._running:
                await bot.update_state()
                update_layout(layout, bot.state, bot.config)
                live.refresh()
                await asyncio.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        bot._running = False
        kb_task.cancel()
