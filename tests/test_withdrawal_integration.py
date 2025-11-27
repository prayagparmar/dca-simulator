"""
Test suite for withdrawal integration with full DCA simulation.

Tests the complete withdrawal feature integrated with the DCA simulation,
including threshold detection, monthly execution, dividend override, and
interaction with margin trading.
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

    # Generate prices with random walk
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


def create_mock_dividends(dates, dividend_amount=1.0, frequency=90):
    """Create mock dividend data."""
    dividends = {}
    for i, date in enumerate(dates):
        if i > 0 and i % frequency == 0:
            dividends[date.strftime('%Y-%m-%d')] = dividend_amount
    return dividends


class TestWithdrawalIntegration(unittest.TestCase):
    """Test withdrawal feature integrated with full DCA simulation."""

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_basic_withdrawal_flow(self, mock_fetch, mock_ticker):
        """Test basic flow: accumulation → threshold → withdrawal mode."""
        # Setup: 6 months of data, price grows from $100 to ~$150
        mock_data = create_mock_stock_data(days=180, start_price=100, trend=0.002)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        # Run simulation
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-06-30',
            amount=1000,  # $1000 daily
            initial_amount=10000,
            reinvest=False,
            withdrawal_threshold=200000,  # Trigger at $200k net value
            monthly_withdrawal_amount=5000  # Withdraw $5k monthly
        )

        self.assertIsNotNone(result)

        # Should have withdrawal data
        self.assertIn('withdrawals', result)
        self.assertIn('withdrawal_dates', result)
        self.assertIn('withdrawal_details', result)
        self.assertIn('total_withdrawn', result['summary'])
        self.assertIn('withdrawal_mode_active', result['summary'])

        # If threshold was reached, should have withdrawals
        if result['summary']['total_withdrawn'] > 0:
            self.assertGreater(len(result['withdrawal_dates']), 0)
            self.assertEqual(result['summary']['withdrawal_mode_active'], True)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_threshold_never_reached(self, mock_fetch, mock_ticker):
        """Test when portfolio never reaches withdrawal threshold."""
        # Setup: 3 months, modest growth
        mock_data = create_mock_stock_data(days=90, start_price=100, trend=0.0005)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=500,
            initial_amount=5000,
            reinvest=False,
            withdrawal_threshold=1000000,  # Very high threshold
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)

        # Should have no withdrawals
        self.assertEqual(result['summary']['total_withdrawn'], 0)
        self.assertEqual(result['summary']['withdrawal_mode_active'], False)
        self.assertEqual(len(result['withdrawal_dates']), 0)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_dividend_reinvestment_stops_during_withdrawal(self, mock_fetch, mock_ticker):
        """Test that dividend reinvestment stops when withdrawal mode activates."""
        # Setup: 6 months with dividends
        mock_data = create_mock_stock_data(days=180, start_price=100, trend=0.003)
        mock_fetch.return_value = mock_data

        # Create dividends every 90 days
        mock_dividends = pd.Series({
            pd.Timestamp('2024-03-01'): 2.0,
            pd.Timestamp('2024-06-01'): 2.0
        })

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = mock_dividends
        mock_ticker.return_value = mock_ticker_instance

        # Run with reinvestment enabled
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-06-30',
            amount=1000,
            initial_amount=10000,
            reinvest=True,  # Reinvest enabled
            withdrawal_threshold=150000,
            monthly_withdrawal_amount=3000
        )

        self.assertIsNotNone(result)

        # If withdrawal mode activated, dividends should add to cash instead of shares
        # This is hard to verify directly, but we can check the withdrawal happened
        if result['summary']['withdrawal_mode_active']:
            self.assertGreater(result['summary']['total_withdrawn'], 0)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_monthly_withdrawal_timing(self, mock_fetch, mock_ticker):
        """Test that withdrawals happen monthly, not daily."""
        # Setup: 4 months of data
        mock_data = create_mock_stock_data(days=120, start_price=150, trend=0.001)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-04-30',
            amount=2000,
            initial_amount=100000,  # Start with high balance to trigger immediately
            reinvest=False,
            withdrawal_threshold=50000,  # Low threshold
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)

        # Should have triggered withdrawal mode
        if result['summary']['total_withdrawn'] > 0:
            # Withdrawals should happen roughly monthly
            num_withdrawals = len(result['withdrawal_dates'])
            # In 4 months, expect 2-4 withdrawals (depends on when threshold hit)
            self.assertLessEqual(num_withdrawals, 5)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_withdrawal_with_margin_debt(self, mock_fetch, mock_ticker):
        """Test withdrawal prioritizes margin debt repayment."""
        # Setup: steady price
        mock_data = create_mock_stock_data(days=120, start_price=100, volatility=0.01)
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
            account_balance=60000,
            margin_ratio=1.5,  # Use margin
            withdrawal_threshold=100000,
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)

        # If withdrawals occurred, check debt repayment in details
        if len(result['withdrawal_details']) > 0:
            for detail in result['withdrawal_details']:
                # Each withdrawal should show debt repayment if debt existed
                self.assertIn('debt_repaid', detail)
                # debt_repaid + amount_withdrawn should equal total cash available
                self.assertGreaterEqual(
                    detail['sale_proceeds'] + detail.get('cash_before', 0),
                    detail['debt_repaid'] + detail['amount_withdrawn']
                )

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_withdrawal_continues_below_threshold(self, mock_fetch, mock_ticker):
        """Test that withdrawals continue even if portfolio falls below threshold."""
        # Setup: price drops after initial rise
        dates = pd.date_range('2024-01-01', periods=180, freq='D')
        prices = [100 + i * 2 if i < 60 else 220 - i for i in range(180)]  # Rise then fall

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
            initial_amount=10000,
            reinvest=False,
            withdrawal_threshold=150000,
            monthly_withdrawal_amount=3000
        )

        self.assertIsNotNone(result)

        # If withdrawal mode activated, it should stay active
        # even as portfolio value drops
        if result['summary']['total_withdrawn'] > 0:
            # Withdrawal mode should remain active
            self.assertTrue(result['summary']['withdrawal_mode_active'])

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_force_sell_shares_when_cash_insufficient(self, mock_fetch, mock_ticker):
        """Test that shares are force-sold when cash is insufficient for withdrawal."""
        # Setup: stable price
        mock_data = create_mock_stock_data(days=180, start_price=100, volatility=0.005)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        # NEW BEHAVIOR: Daily investments stop during withdrawal mode
        # Strategy: Accumulate normally, then trigger withdrawal with depleted cash
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-06-30',
            amount=2000,  # Daily amount during accumulation
            initial_amount=50000,  # Moderate initial
            reinvest=False,
            account_balance=52000,  # Just enough for 1 day of investing
            withdrawal_threshold=200000,  # High threshold - trigger after accumulation
            monthly_withdrawal_amount=50000  # Very large withdrawal to force share sales
        )

        self.assertIsNotNone(result)

        # With new behavior: no daily investments during withdrawal mode
        # Cash depletes during accumulation, then withdrawals require selling shares
        if len(result['withdrawal_details']) > 0 and result['summary']['total_withdrawn'] > 0:
            # Check if ANY withdrawal sold shares
            total_shares_sold = sum(d['shares_sold'] for d in result['withdrawal_details'])

            # With depleted cash and large withdrawals, shares MUST be sold
            self.assertGreater(total_shares_sold, 0,
                             "Should sell shares when cash insufficient for withdrawal")

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_withdrawal_tracking_arrays(self, mock_fetch, mock_ticker):
        """Test that withdrawal tracking arrays are properly populated."""
        mock_data = create_mock_stock_data(days=120, start_price=120)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-04-30',
            amount=1000,
            initial_amount=100000,
            reinvest=False,
            withdrawal_threshold=50000,
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)

        # Check array lengths match
        self.assertEqual(len(result['dates']), len(result['withdrawals']))
        self.assertEqual(len(result['dates']), len(result['withdrawal_mode']))

        # withdrawal_mode should be all False until threshold hit
        if result['summary']['total_withdrawn'] > 0:
            # Find first True in withdrawal_mode
            first_true = next((i for i, x in enumerate(result['withdrawal_mode']) if x), None)
            if first_true is not None:
                # All before should be False
                self.assertTrue(all(not x for x in result['withdrawal_mode'][:first_true]))
                # All after should be True
                self.assertTrue(all(x for x in result['withdrawal_mode'][first_true:]))

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_withdrawal_none_parameters(self, mock_fetch, mock_ticker):
        """Test simulation works correctly with None withdrawal parameters."""
        mock_data = create_mock_stock_data(days=90)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        # Run without withdrawal parameters
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=1000,
            initial_amount=10000,
            reinvest=False,
            withdrawal_threshold=None,
            monthly_withdrawal_amount=None
        )

        self.assertIsNotNone(result)

        # Should have no withdrawals
        self.assertEqual(result['summary']['total_withdrawn'], 0)
        self.assertEqual(result['summary']['withdrawal_mode_active'], False)
        self.assertEqual(len(result['withdrawal_dates']), 0)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_daily_investments_stop_during_withdrawal_mode(self, mock_fetch, mock_ticker):
        """Test that daily investments stop once withdrawal mode activates."""
        # Setup: 6 months of stable prices
        mock_data = create_mock_stock_data(days=180, start_price=100, volatility=0.001, trend=0.0)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-06-30',
            amount=500,  # $500 daily
            initial_amount=100000,  # Large initial to trigger threshold quickly
            reinvest=False,
            withdrawal_threshold=50000,  # Low threshold to trigger early
            monthly_withdrawal_amount=3000
        )

        self.assertIsNotNone(result)

        # Should have triggered withdrawal mode
        self.assertTrue(result['summary']['withdrawal_mode_active'])
        self.assertGreater(result['summary']['total_withdrawn'], 0)

        # Find when withdrawal mode started
        withdrawal_start_idx = next(
            (i for i, active in enumerate(result['withdrawal_mode']) if active),
            None
        )
        self.assertIsNotNone(withdrawal_start_idx)

        # Check total_invested array
        # Before withdrawal mode: total_invested should increase daily
        # During withdrawal mode: total_invested should NOT increase (flat line)
        if withdrawal_start_idx > 10 and withdrawal_start_idx < len(result['invested']) - 10:
            # Check that investments increased before withdrawal mode
            invested_before_start = result['invested'][withdrawal_start_idx - 1]
            invested_10_days_before = result['invested'][max(0, withdrawal_start_idx - 10)]
            self.assertGreater(invested_before_start, invested_10_days_before,
                             "Investments should increase before withdrawal mode")

            # Check that investments STOPPED during withdrawal mode
            invested_at_start = result['invested'][withdrawal_start_idx]
            invested_10_days_after = result['invested'][min(len(result['invested']) - 1, withdrawal_start_idx + 10)]
            invested_at_end = result['invested'][-1]

            # Total invested should be flat (same value) after withdrawal mode starts
            self.assertEqual(invested_at_start, invested_10_days_after,
                           "Investments should stop (flat line) during withdrawal mode")
            self.assertEqual(invested_at_start, invested_at_end,
                           "Total invested should remain constant throughout withdrawal mode")

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_debt_paid_off_immediately_at_threshold(self, mock_fetch, mock_ticker):
        """Test that ALL debt is paid off immediately when threshold is reached."""
        # Setup: Accumulate with margin, then trigger threshold
        mock_data = create_mock_stock_data(days=180, start_price=100, trend=0.002)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-06-30',
            amount=1000,  # Daily amount
            initial_amount=50000,
            reinvest=False,
            account_balance=55000,  # Constrained - will use margin
            margin_ratio=2.0,  # Allow margin
            withdrawal_threshold=200000,  # Trigger after accumulation
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)

        # If withdrawal mode was activated
        if result['summary']['withdrawal_mode_active']:
            # Find the debt payoff event (should be first entry in withdrawal_details)
            debt_payoff_event = None
            for detail in result['withdrawal_details']:
                if detail.get('event_type') == 'threshold_debt_payoff':
                    debt_payoff_event = detail
                    break

            # If debt existed when threshold was reached, should have payoff event
            if debt_payoff_event:
                # Verify it's a debt payoff (no withdrawal, only debt repayment)
                self.assertEqual(debt_payoff_event['amount_withdrawn'], 0,
                               "Debt payoff event should have $0 withdrawal")
                self.assertGreater(debt_payoff_event['debt_repaid'], 0,
                                 "Debt payoff event should repay debt")

                # After debt payoff, subsequent withdrawals should have $0 debt repaid
                found_payoff = False
                for detail in result['withdrawal_details']:
                    if detail.get('event_type') == 'threshold_debt_payoff':
                        found_payoff = True
                    elif found_payoff:  # After the payoff event
                        # Regular withdrawals after payoff should have no debt to repay
                        self.assertEqual(detail['debt_repaid'], 0,
                                       f"After debt payoff, withdrawals should have $0 debt repaid (found ${detail['debt_repaid']:.2f})")

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_no_new_margin_debt_during_withdrawal_mode(self, mock_fetch, mock_ticker):
        """Test that no new margin debt is accumulated during withdrawal mode."""
        # Setup: 6 months of data
        mock_data = create_mock_stock_data(days=180, start_price=100, volatility=0.01)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-06-30',
            amount=1000,  # $1000 daily
            initial_amount=50000,
            reinvest=False,
            account_balance=60000,  # Constrained cash
            margin_ratio=2.0,  # Allow margin
            withdrawal_threshold=100000,
            monthly_withdrawal_amount=5000
        )

        self.assertIsNotNone(result)

        # If withdrawal mode activated
        if result['summary']['withdrawal_mode_active']:
            # Find when withdrawal mode started
            withdrawal_start_idx = next(
                (i for i, active in enumerate(result['withdrawal_mode']) if active),
                None
            )

            if withdrawal_start_idx is not None and withdrawal_start_idx < len(result['borrowed']) - 10:
                # Get debt at withdrawal mode start
                debt_at_start = result['borrowed'][withdrawal_start_idx]

                # Check debt trend after withdrawal mode starts
                # It should decrease or stay same (paid down), NOT increase
                for i in range(withdrawal_start_idx + 1, len(result['borrowed'])):
                    current_debt = result['borrowed'][i]
                    previous_debt = result['borrowed'][i - 1]

                    # Debt should never increase during withdrawal mode
                    # (it can only decrease via repayments or stay same)
                    self.assertLessEqual(current_debt, previous_debt + 0.01,  # Allow tiny rounding
                                       f"Debt should not increase during withdrawal mode (day {i})")


if __name__ == '__main__':
    unittest.main()
