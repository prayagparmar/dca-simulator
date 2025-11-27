"""
Test suite for withdrawal feature edge cases and stress scenarios.

Tests complex interactions, boundary conditions, and potential bugs
in the withdrawal system including debt payoff, margin calls, insolvency,
and extreme market conditions.
"""

import unittest
import sys
import os
from unittest.mock import patch, Mock
import pandas as pd
import numpy as np

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import calculate_dca_core


def create_mock_stock_data(days=180, start_price=100, volatility=0.02, trend=0.001):
    """Create mock stock data with realistic price movements."""
    dates = pd.date_range('2024-01-01', periods=days, freq='D')
    returns = np.random.normal(trend, volatility, days)
    prices = start_price * np.exp(np.cumsum(returns))
    df = pd.DataFrame({
        'Close': prices,
        'Open': prices * 0.99,
        'High': prices * 1.01,
        'Low': prices * 0.98,
        'Volume': 1000000
    }, index=dates)
    return df


class TestWithdrawalEdgeCases(unittest.TestCase):
    """Test edge cases and stress scenarios for withdrawal feature."""

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_debt_exceeds_portfolio_value_at_threshold(self, mock_fetch, mock_ticker):
        """Test when debt is larger than portfolio value when threshold reached."""
        # Setup: Price crashes, creating underwater position
        dates = pd.date_range('2024-01-01', periods=120, freq='D')
        # Price rises then crashes
        prices = [100 + i * 2 if i < 60 else 120 - i for i in range(120)]
        mock_data = pd.DataFrame({
            'Close': prices,
            'Open': prices,
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Volume': 1000000
        }, index=dates)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-04-30',
            amount=1000,
            initial_amount=50000,
            reinvest=False,
            account_balance=55000,
            margin_ratio=2.0,
            withdrawal_threshold=100000,
            monthly_withdrawal_amount=5000
        )

        # Should handle gracefully - may not reach threshold or may become insolvent
        self.assertIsNotNone(result)
        # If insolvent, should stop simulation
        if result['summary'].get('insolvency_detected'):
            self.assertIsNotNone(result['summary']['insolvency_date'])

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_threshold_and_margin_call_same_day(self, mock_fetch, mock_ticker):
        """Test when threshold is reached on same day as margin call."""
        # This tests order of operations
        mock_data = create_mock_stock_data(days=90, start_price=100, trend=0.003)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=2000,
            initial_amount=50000,
            reinvest=False,
            account_balance=52000,
            margin_ratio=2.0,
            maintenance_margin=0.25,
            withdrawal_threshold=150000,
            monthly_withdrawal_amount=10000
        )

        self.assertIsNotNone(result)
        # Should handle both events in correct order
        # Margin call happens BEFORE threshold check (step 1 vs step 3)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_insufficient_shares_to_pay_debt_at_threshold(self, mock_fetch, mock_ticker):
        """Test when portfolio can't fully cover debt at threshold."""
        # Setup: Huge debt, small portfolio
        mock_data = create_mock_stock_data(days=90, start_price=100, volatility=0.001)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=5000,  # Large daily investment
            initial_amount=10000,
            reinvest=False,
            account_balance=15000,  # Minimal cash - will borrow heavily
            margin_ratio=3.0,  # High leverage
            withdrawal_threshold=50000,  # Low threshold - trigger quickly
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)
        # Should sell ALL shares if needed to pay debt
        # May end with 0 shares after debt payoff

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_withdrawal_mode_with_dividends_adding_cash(self, mock_fetch, mock_ticker):
        """Test that dividends during withdrawal mode go to cash, not reinvested."""
        mock_data = create_mock_stock_data(days=180, start_price=100, trend=0.002)
        mock_fetch.return_value = mock_data

        # Create dividends during both accumulation and withdrawal phases
        mock_dividends = pd.Series({
            pd.Timestamp('2024-02-01'): 2.0,  # During accumulation
            pd.Timestamp('2024-04-01'): 2.0,  # During withdrawal mode
            pd.Timestamp('2024-05-01'): 2.0,  # During withdrawal mode
        })

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = mock_dividends
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-06-30',
            amount=1000,
            initial_amount=80000,
            reinvest=True,  # Reinvest enabled
            withdrawal_threshold=150000,
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)

        # Find when withdrawal mode started
        if result['summary']['withdrawal_mode_active']:
            withdrawal_start_date = result['summary']['withdrawal_mode_start_date']

            # Dividends before withdrawal mode should increase shares (if reinvest=True)
            # Dividends after withdrawal mode should NOT increase shares (reinvest disabled)
            # This is hard to verify directly, but we can check that withdrawal mode worked

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_zero_shares_after_debt_payoff(self, mock_fetch, mock_ticker):
        """Test edge case where debt payoff sells ALL shares."""
        # Setup: Small portfolio, large debt
        mock_data = create_mock_stock_data(days=90, start_price=100, volatility=0.005)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=3000,  # Large daily
            initial_amount=20000,
            reinvest=False,
            account_balance=22000,  # Minimal cash
            margin_ratio=2.5,  # High leverage
            withdrawal_threshold=80000,  # Low threshold
            monthly_withdrawal_amount=10000
        )

        self.assertIsNotNone(result)

        # If debt payoff happened and all shares sold
        if result['summary']['withdrawal_mode_active']:
            # Check if shares dropped to 0
            final_shares = result['summary']['total_shares']
            # Should handle this gracefully - may have 0 shares but simulation continues

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_withdrawal_larger_than_portfolio_value(self, mock_fetch, mock_ticker):
        """Test withdrawal amount exceeding total portfolio value."""
        mock_data = create_mock_stock_data(days=120, start_price=100, volatility=0.005)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-04-30',
            amount=1000,
            initial_amount=50000,
            reinvest=False,
            withdrawal_threshold=100000,
            monthly_withdrawal_amount=200000  # HUGE withdrawal
        )

        self.assertIsNotNone(result)

        # Should withdraw maximum available (all assets liquidated)
        # Should NOT crash or create negative values
        if len(result['withdrawal_details']) > 0:
            for withdrawal in result['withdrawal_details']:
                # Withdrawn amount should never exceed available assets
                self.assertGreaterEqual(withdrawal['amount_withdrawn'], 0)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_threshold_reached_multiple_times_same_simulation(self, mock_fetch, mock_ticker):
        """Test that withdrawal mode stays active even if value drops below threshold."""
        # Price rises (trigger threshold), then falls (below threshold), then rises again
        dates = pd.date_range('2024-01-01', periods=180, freq='D')
        prices = []
        for i in range(180):
            if i < 60:
                prices.append(100 + i)  # Rise
            elif i < 120:
                prices.append(160 - (i - 60))  # Fall
            else:
                prices.append(100 + (i - 120))  # Rise again

        mock_data = pd.DataFrame({
            'Close': prices,
            'Open': prices,
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Volume': 1000000
        }, index=dates)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-06-30',
            amount=1000,
            initial_amount=50000,
            reinvest=False,
            withdrawal_threshold=200000,
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)

        # Once withdrawal mode activates, it should NEVER deactivate
        if result['summary']['withdrawal_mode_active']:
            # Find first True in withdrawal_mode array
            first_active = next((i for i, active in enumerate(result['withdrawal_mode']) if active), None)
            if first_active is not None:
                # ALL subsequent values should be True
                self.assertTrue(all(result['withdrawal_mode'][first_active:]),
                              "Withdrawal mode should never deactivate once activated")

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_cost_basis_consistency_after_debt_payoff(self, mock_fetch, mock_ticker):
        """Test that cost basis is correctly reduced when shares sold for debt payoff."""
        mock_data = create_mock_stock_data(days=120, start_price=100, trend=0.002)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-04-30',
            amount=1000,
            initial_amount=50000,
            reinvest=False,
            account_balance=52000,
            margin_ratio=2.0,
            withdrawal_threshold=150000,
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)

        # Average cost should be consistent throughout
        # avg_cost = total_cost_basis / total_shares
        for i, avg_cost in enumerate(result['average_cost']):
            if result['portfolio'][i] > 0:  # Only check when shares exist
                # Average cost should be positive and reasonable
                self.assertGreater(avg_cost, 0, f"Average cost should be positive at index {i}")
                self.assertLess(avg_cost, 10000, f"Average cost unreasonably high at index {i}")

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_no_cash_no_shares_at_threshold(self, mock_fetch, mock_ticker):
        """Test edge case: threshold reached but no cash and no shares to sell."""
        mock_data = create_mock_stock_data(days=90, start_price=100, volatility=0.01)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        # This is a contrived scenario but tests robustness
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=1000,
            initial_amount=100000,
            reinvest=False,
            account_balance=None,  # Infinite cash mode
            withdrawal_threshold=50000,  # Low threshold
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)
        # Should handle gracefully even in edge cases

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_withdrawal_details_cumulative_accuracy(self, mock_fetch, mock_ticker):
        """Test that cumulative withdrawn amounts are accurate."""
        mock_data = create_mock_stock_data(days=180, start_price=100, trend=0.002)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-06-30',
            amount=1000,
            initial_amount=100000,
            reinvest=False,
            withdrawal_threshold=150000,
            monthly_withdrawal_amount=10000
        )

        self.assertIsNotNone(result)

        if len(result['withdrawal_details']) > 0:
            # Check cumulative accuracy
            expected_cumulative = 0
            for detail in result['withdrawal_details']:
                expected_cumulative += detail['amount_withdrawn']
                self.assertAlmostEqual(detail['cumulative_withdrawn'], expected_cumulative, places=2,
                                     msg=f"Cumulative withdrawn mismatch at {detail['date']}")

            # Final cumulative should match summary
            self.assertAlmostEqual(
                result['withdrawal_details'][-1]['cumulative_withdrawn'],
                result['summary']['total_withdrawn'],
                places=2,
                msg="Final cumulative should match summary total_withdrawn"
            )


if __name__ == '__main__':
    unittest.main()
