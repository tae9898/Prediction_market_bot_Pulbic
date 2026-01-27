#!/usr/bin/env python3
"""Test script for arbitrage strategy"""

import sys
sys.path.insert(0, '/root/work/tae')

from strategies.arbitrage import SurebetEngine, ArbitrageConfig
from core.interfaces.exchange_base import OrderBook, OrderBookLevel
import time

def main():
    # Create strategy
    config = ArbitrageConfig(min_profit_rate=1.0)
    strategy = SurebetEngine(config)

    # Create sample orderbooks - YES and NO tokens
    # Scenario: YES @ 0.45, NO @ 0.52 = 0.97 total (3% profit)
    yes_asks = [
        OrderBookLevel(price=0.45, size=100),
        OrderBookLevel(price=0.46, size=200),
        OrderBookLevel(price=0.47, size=300),
    ]

    no_asks = [
        OrderBookLevel(price=0.52, size=100),
        OrderBookLevel(price=0.53, size=200),
        OrderBookLevel(price=0.54, size=300),
    ]

    yes_orderbook = OrderBook(
        symbol='YES_TOKEN',
        bids=[],
        asks=yes_asks,
        timestamp=time.time()
    )

    no_orderbook = OrderBook(
        symbol='NO_TOKEN',
        bids=[],
        asks=no_asks,
        timestamp=time.time()
    )

    # Analyze
    market_data = {
        'yes_orderbook': yes_orderbook,
        'no_orderbook': no_orderbook,
    }

    signal = strategy.analyze(market_data)

    if signal:
        print('Signal found!')
        print(f'Action: {signal.action.value}')
        print(f'Direction: {signal.direction.value}')
        print(f'Confidence: {signal.confidence}')
        print(f'Edge: {signal.edge:.2f}%')
        print(f'Reason: {signal.reason}')

        opp = signal.metadata.get('opportunity', {})
        print(f'\nOpportunity details:')
        print(f'  VWAP YES: {opp.get("vwap_yes", 0):.4f}')
        print(f'  VWAP NO: {opp.get("vwap_no", 0):.4f}')
        print(f'  Total Cost: {opp.get("total_cost", 0):.4f}')
        print(f'  Spread: {opp.get("spread", 0):.4f}')
        print(f'  Profit Rate: {opp.get("profit_rate", 0):.2f}%')
        print(f'  Max Size: {opp.get("max_size", 0):.2f}')
        print(f'  Max Profit: {opp.get("max_profit", 0):.2f}')
    else:
        print('No signal found')
        return

    # Test execution params calculation
    opportunity_data = signal.metadata.get('opportunity')
    if opportunity_data:
        from strategies.arbitrage.strategy import ArbitrageOpportunity
        opp = ArbitrageOpportunity(**opportunity_data)
        params = strategy.calculate_execution_params(opp, amount_usdc=100.0)
        print(f'\nExecution params for $100 investment:')
        print(f'  YES size: {params.yes_size:.2f} @ {params.yes_max_price:.4f}')
        print(f'  NO size: {params.no_size:.2f} @ {params.no_max_price:.4f}')
        print(f'  Expected profit: ${params.expected_profit:.2f}')
        print(f'  Profit rate: {params.profit_rate:.2f}%')

    # Test quick check
    print('\n--- Quick Check Tests ---')
    test_cases = [
        (0.45, 0.52, True),   # 3% profit
        (0.48, 0.48, True),   # 4% profit
        (0.50, 0.50, False),  # Break even
        (0.51, 0.51, False),  # Loss
    ]

    for yes_price, no_price, expected in test_cases:
        result = strategy.quick_check(yes_price, no_price)
        status = 'PASS' if result == expected else 'FAIL'
        print(f'[{status}] YES={yes_price:.2f}, NO={no_price:.2f} -> {result}')

if __name__ == '__main__':
    main()
