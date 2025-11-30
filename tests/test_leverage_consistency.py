"""
Test to verify leverage chart data matches summary card value.

User reported: Chart shows double the leverage compared to summary card.
"""

import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from app import calculate_dca_core
from tests.conftest import create_mock_stock_data


class TestLeverageConsistency(unittest.TestCase):
    """Test that leverage values are consistent between chart and summary"""

    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()

    def tearDown(self):
        self.mock_ticker_patcher.stop()

    def setup_mock_data(self, prices):
        """Helper using conftest"""
        self.mock_ticker.return_value = create_mock_stock_data(prices, start_date='2024-01-01')

    def test_leverage_chart_matches_summary_card(self):
        """
        Verify that the final value in leverage array matches current_leverage in summary

        If they differ, this indicates a bug in how leverage is calculated
        """
        # Create declining prices to trigger margin usage
        prices = [100 - (i * 0.05) for i in range(100)]
        self.setup_mock_data(prices)

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-04-30',
            amount=1000,
            initial_amount=10000,
            reinvest=False,
            account_balance=50000,
            margin_ratio=2.0,  # Enable margin
            maintenance_margin=0.25
        )

        # Get leverage from chart (last value in array)
        chart_leverage = result['leverage'][-1] if result['leverage'] else None

        # Get leverage from summary card
        card_leverage = result['summary']['current_leverage']

        print(f"\nChart leverage (last value): {chart_leverage}")
        print(f"Card leverage: {card_leverage}")

        # They should match exactly
        self.assertIsNotNone(chart_leverage, "Chart leverage should not be None")
        self.assertIsNotNone(card_leverage, "Card leverage should not be None")

        # Allow for small rounding differences (0.01 tolerance)
        self.assertAlmostEqual(chart_leverage, card_leverage, places=2,
            msg=f"Chart leverage ({chart_leverage}) should match card leverage ({card_leverage})")

    def test_leverage_calculation_formula(self):
        """
        Verify leverage = portfolio_value / equity

        Also check that equity = portfolio_value + cash - debt
        """
        prices = [100, 95, 90, 85, 80]
        self.setup_mock_data(prices)

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=1000,
            initial_amount=5000,
            reinvest=False,
            account_balance=20000,
            margin_ratio=2.0,
            maintenance_margin=0.25
        )

        # Calculate expected leverage manually
        portfolio_value = result['summary']['current_value']
        borrowed = result['summary']['total_borrowed']
        cash = result['summary']['account_balance'] or 0

        equity = portfolio_value + cash - borrowed
        expected_leverage = portfolio_value / equity if equity > 0 else 0

        actual_leverage = result['summary']['current_leverage']

        print(f"\nPortfolio: ${portfolio_value}")
        print(f"Borrowed: ${borrowed}")
        print(f"Cash: ${cash}")
        print(f"Equity: ${equity}")
        print(f"Expected leverage: {expected_leverage:.2f}x")
        print(f"Actual leverage: {actual_leverage}x")

        self.assertAlmostEqual(actual_leverage, expected_leverage, places=2,
            msg="Leverage should equal portfolio_value / equity")


if __name__ == '__main__':
    unittest.main(verbosity=2)
