"""
Test margin call logic with large cash buffers (DCA scenario).

User observed: -87.87% drawdown with 2x margin, but zero margin calls.
This tests whether large cash balances prevent margin calls when they shouldn't.
"""

import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from app import calculate_dca_core, calculate_equity_ratio
from tests.conftest import create_mock_stock_data


class TestMarginCallWithCashBuffer(unittest.TestCase):
    """Test that margin calls trigger correctly even with cash buffers"""

    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()

    def tearDown(self):
        self.mock_ticker_patcher.stop()

    def setup_mock_data(self, prices):
        """Helper using conftest"""
        self.mock_ticker.return_value = create_mock_stock_data(prices, start_date='2024-01-01')

    def test_equity_ratio_with_large_cash_buffer(self):
        """
        Test if equity ratio includes cash balance in the calculation.

        Question: Should uninvested cash count toward margin equity?

        Scenario:
        - Portfolio: $10,000
        - Debt: $8,000
        - Cash: $100,000 (large uninvested balance)
        - Equity ratio: ($10K + $100K - $8K) / $10K = 10.2 (1020%!)

        This seems wrong - cash buffer makes margin call impossible!
        """
        portfolio_value = 10000
        cash_balance = 100000  # Large uninvested cash
        debt = 8000
        maintenance_margin = 0.25

        equity_ratio = calculate_equity_ratio(portfolio_value, cash_balance, debt)

        print(f"\nPortfolio: ${portfolio_value}")
        print(f"Debt: ${debt}")
        print(f"Cash: ${cash_balance}")
        print(f"Equity ratio: {equity_ratio:.2%}")
        print(f"Maintenance margin: {maintenance_margin:.2%}")

        # With cash included, equity ratio is absurdly high
        self.assertGreater(equity_ratio, 10.0,
            "Equity ratio is >1000% due to cash buffer!")

        # Without cash, equity ratio would be:
        equity_no_cash = (portfolio_value - debt) / portfolio_value
        print(f"\nEquity ratio WITHOUT cash: {equity_no_cash:.2%}")

        # Without cash, this would be a margin call!
        self.assertLess(equity_no_cash, maintenance_margin,
            "WITHOUT cash buffer, this should trigger margin call")

    def test_severe_drawdown_with_cash_prevents_margin_call(self):
        """
        Reproduce user's scenario: -87% drawdown, but large cash buffer prevents margin call

        This tests if DCA cash injections prevent margin calls that should happen
        """
        # Simulate extreme crash scenario
        prices = [100, 90, 70, 50, 30, 15, 12]  # -88% crash!
        self.setup_mock_data(prices)

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-07',
            amount=500,  # Daily investment
            initial_amount=10000,  # Initial lump sum
            reinvest=False,
            account_balance=100000,  # Large cash buffer
            margin_ratio=2.0,
            maintenance_margin=0.25
        )

        print(f"\nFinal portfolio value: ${result['summary']['current_value']}")
        print(f"Final debt: ${result['summary']['total_borrowed']}")
        print(f"Final cash: ${result['summary']['account_balance']}")
        print(f"Margin calls: {result['summary']['margin_calls']}")

        # With large cash buffer, no margin call despite -88% crash
        # This might be incorrect behavior!

    def test_margin_call_without_cash_buffer(self):
        """
        Test that margin call DOES trigger when there's no cash buffer
        """
        # Same crash, but minimal cash
        prices = [100, 90, 70, 50, 30, 15, 12]
        self.setup_mock_data(prices)

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-07',
            amount=100,
            initial_amount=10000,
            reinvest=False,
            account_balance=5000,  # Minimal cash buffer
            margin_ratio=2.0,
            maintenance_margin=0.25
        )

        print(f"\nFinal portfolio value: ${result['summary']['current_value']}")
        print(f"Final debt: ${result['summary']['total_borrowed']}")
        print(f"Final cash: ${result['summary']['account_balance']}")
        print(f"Margin calls: {result['summary']['margin_calls']}")

        # Should this trigger margin calls?


if __name__ == '__main__':
    unittest.main(verbosity=2)
