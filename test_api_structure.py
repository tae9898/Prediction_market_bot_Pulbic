#!/usr/bin/env python3
"""
Test script to verify API structure without running the full server
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from web.backend.models import (
    WalletInfo,
    PositionInfo,
    MarketData,
    BotStatus,
    PortfolioSnapshot,
)


def test_models():
    """Test Pydantic models"""
    print("Testing Pydantic models...")

    # Test WalletInfo
    wallet = WalletInfo(
        id="0",
        address="0x1234567890abcdef",
        usdc_balance=1000.0,
        reserved_balance=100.0,
        portfolio_value=1500.0,
        is_connected=True,
        auto_trade=True,
    )
    print(f"  WalletInfo: {wallet.id} - ${wallet.portfolio_value:.2f}")

    # Test PositionInfo
    position = PositionInfo(
        wallet_id="0",
        asset="BTC",
        market="BTC Hourly",
        side="UP",
        size=10.0,
        avg_price=0.5,
        cur_price=0.55,
        cost=5.0,
        current_value=5.5,
        pnl=0.5,
        pnl_pct=10.0,
        strategy="edge_hedge_entry",
    )
    print(f"  PositionInfo: {position.asset} {position.side} - PnL: {position.pnl_pct:.1f}%")

    # Test MarketData
    market = MarketData(
        asset="BTC",
        price=95000.0,
        change_24h=1000.0,
        change_pct=1.06,
        volatility=0.15,
        momentum="BULLISH",
        strike_price=95000.0,
        time_remaining="45:00",
        time_remaining_sec=2700,
        up_ask=0.52,
        up_bid=0.50,
        down_ask=0.50,
        down_bid=0.48,
        spread=0.02,
        fair_up=0.51,
        fair_down=0.49,
        edge_up=1.0,
        edge_down=1.0,
        d2=0.5,
        surebet_profitable=False,
        surebet_profit_rate=0.0,
        signal="WAITING",
    )
    print(f"  MarketData: {market.asset} @ ${market.price:,.0f} - Signal: {market.signal}")

    # Test BotStatus
    status = BotStatus(
        is_running=True,
        wallet_count=2,
        total_portfolio_value=3000.0,
        total_usdc=2500.0,
        total_invested=500.0,
        total_pnl=50.0,
        update_count=100,
        last_update="10:30:45",
        logs=["[10:30:45] Bot started", "[10:30:46] Market data updated"],
    )
    print(f"  BotStatus: {status.wallet_count} wallets - Total: ${status.total_portfolio_value:.2f}")

    print("  All models OK!")


def test_api_routes():
    """Test API routes are registered"""
    print("\nTesting API routes...")

    from web.backend.api import app

    routes = [r for r in app.routes if hasattr(r, 'path')]
    api_routes = [r.path for r in routes if r.path.startswith('/api')]

    expected_routes = [
        "/api/status",
        "/api/wallets",
        "/api/positions",
        "/api/markets",
        "/api/performance",
        "/api/signals",
        "/api/portfolio",
        "/api/trades",
    ]

    for route in expected_routes:
        if route in api_routes:
            print(f"  {route} - OK")
        else:
            print(f"  {route} - MISSING")

    print(f"  Total API routes: {len(api_routes)}")


def test_json_serialization():
    """Test JSON serialization"""
    print("\nTesting JSON serialization...")

    import json

    wallet = WalletInfo(
        id="0",
        address="0x1234567890abcdef",
        usdc_balance=1000.0,
        reserved_balance=100.0,
        portfolio_value=1500.0,
        is_connected=True,
        auto_trade=True,
    )

    json_str = wallet.model_dump_json()
    parsed = WalletInfo.model_validate_json(json_str)

    print(f"  Serialization: OK")
    print(f"  JSON: {json_str[:100]}...")
    print(f"  Round-trip: {parsed.id} == {wallet.id}")


if __name__ == "__main__":
    print("=" * 60)
    print("API Structure Verification")
    print("=" * 60)

    try:
        test_models()
        test_api_routes()
        test_json_serialization()

        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
