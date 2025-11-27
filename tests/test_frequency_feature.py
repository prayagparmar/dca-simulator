"""
Test suite for investment frequency feature.

Tests the ability to configure Daily, Weekly, and Monthly investment frequencies,
ensuring correct investment counts, backward compatibility, and financial accuracy.
"""

import unittest
import sys
import os
from unittest.mock import patch, Mock
import pandas as pd

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import calculate_dca_core, should_invest_today


def create_mock_stock_data(days=90, start_price=100):
    """Create mock stock data with stable prices for easier calculation."""
    dates = pd.date_range('2024-01-01', periods=days, freq='D')
    prices = [start_price] * days  # Stable price
    df = pd.DataFrame({
        'Close': prices,
        'Open': prices,
        'High': [p * 1.01 for p in prices],
        'Low': [p * 0.99 for p in prices],
        'Volume': 1000000
    }, index=dates)
    return df


class TestShouldInvestTodayUnit(unittest.TestCase):
    """Unit tests for should_invest_today() helper function."""

    def test_daily_frequency_always_returns_true(self):
        """Test that DAILY frequency always allows investment."""
        should_invest, month = should_invest_today('2024-01-15', '2024-01-01', 'DAILY', None)
        self.assertTrue(should_invest)
        self.assertIsNone(month)

        should_invest, month = should_invest_today('2024-02-20', '2024-01-01', 'DAILY', None)
        self.assertTrue(should_invest)
        self.assertIsNone(month)

    def test_weekly_frequency_same_weekday(self):
        """Test that WEEKLY frequency returns True on matching weekday."""
        # 2024-01-01 is a Monday (weekday=0)
        # 2024-01-08 is also a Monday
        should_invest, month = should_invest_today('2024-01-08', '2024-01-01', 'WEEKLY', None)
        self.assertTrue(should_invest)
        self.assertIsNone(month)

    def test_weekly_frequency_different_weekday(self):
        """Test that WEEKLY frequency returns False on non-matching weekday."""
        # 2024-01-01 is a Monday (weekday=0)
        # 2024-01-02 is a Tuesday (weekday=1)
        should_invest, month = should_invest_today('2024-01-02', '2024-01-01', 'WEEKLY', None)
        self.assertFalse(should_invest)
        self.assertIsNone(month)

    def test_monthly_frequency_first_occurrence(self):
        """Test that MONTHLY frequency returns True on first day of new month."""
        should_invest, month = should_invest_today('2024-02-01', '2024-01-01', 'MONTHLY', None)
        self.assertTrue(should_invest)
        self.assertEqual(month, '2024-02')

    def test_monthly_frequency_same_month(self):
        """Test that MONTHLY frequency returns False within same month."""
        should_invest, month = should_invest_today('2024-01-15', '2024-01-01', 'MONTHLY', '2024-01')
        self.assertFalse(should_invest)
        self.assertEqual(month, '2024-01')


class TestDailyFrequencyIntegration(unittest.TestCase):
    """Integration tests for DAILY frequency (default behavior)."""

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_daily_frequency_matches_current_behavior(self, mock_fetch, mock_ticker):
        """Test that DAILY frequency produces same results as default (backward compatibility)."""
        mock_data = create_mock_stock_data(days=30, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        # Old behavior (no frequency parameter)
        result_old = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-30',
            amount=1000,
            initial_amount=50000,
            reinvest=False
        )

        # New behavior with explicit DAILY
        result_new = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-30',
            amount=1000,
            initial_amount=50000,
            reinvest=False,
            frequency='DAILY'
        )

        # Should produce identical results
        self.assertEqual(result_old['summary']['total_invested'], result_new['summary']['total_invested'])
        self.assertEqual(result_old['summary']['total_shares'], result_new['summary']['total_shares'])
        self.assertEqual(result_old['summary']['current_value'], result_new['summary']['current_value'])

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_daily_frequency_with_dividends_and_margin(self, mock_fetch, mock_ticker):
        """Test DAILY frequency with complex features (dividends, margin)."""
        mock_data = create_mock_stock_data(days=60, start_price=100)
        mock_fetch.return_value = mock_data

        mock_dividends = pd.Series({
            pd.Timestamp('2024-01-15'): 2.0,
            pd.Timestamp('2024-02-15'): 2.0,
        })

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = mock_dividends
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-01',
            amount=1000,
            initial_amount=50000,
            reinvest=True,
            margin_ratio=1.5,
            frequency='DAILY'
        )

        self.assertIsNotNone(result)
        self.assertGreater(result['summary']['total_shares'], 0)


class TestWeeklyFrequencyIntegration(unittest.TestCase):
    """Integration tests for WEEKLY frequency."""

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_weekly_frequency_reduces_investment_count(self, mock_fetch, mock_ticker):
        """Test that WEEKLY frequency invests approximately 1/5 as often as DAILY."""
        mock_data = create_mock_stock_data(days=90, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result_daily = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            frequency='DAILY'
        )

        result_weekly = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            frequency='WEEKLY'
        )

        # Weekly should invest much less than daily
        self.assertLess(result_weekly['summary']['total_invested'], result_daily['summary']['total_invested'])

        # Approximate ratio (trading week = 5 days)
        ratio = result_weekly['summary']['total_invested'] / result_daily['summary']['total_invested']
        self.assertGreater(ratio, 0.14)  # At least 14% (allowing for calendar variance)
        self.assertLess(ratio, 0.25)     # At most 25%

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_weekly_frequency_with_initial_investment(self, mock_fetch, mock_ticker):
        """Test that initial investment happens on day 1 regardless of WEEKLY frequency."""
        mock_data = create_mock_stock_data(days=30, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-30',
            amount=1000,
            initial_amount=50000,
            reinvest=False,
            frequency='WEEKLY'
        )

        # Total invested should include initial amount even with WEEKLY frequency
        self.assertGreaterEqual(result['summary']['total_invested'], 50000)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_weekly_frequency_respects_start_weekday(self, mock_fetch, mock_ticker):
        """Test that WEEKLY frequency invests on same weekday as start date."""
        # 2024-01-01 is a Monday
        mock_data = create_mock_stock_data(days=21, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-21',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            frequency='WEEKLY'
        )

        # In 21 days (3 weeks), should have 3 Monday investments
        # (Jan 1, 8, 15)
        expected_investments = 3 * 1000
        self.assertEqual(result['summary']['total_invested'], expected_investments)


class TestMonthlyFrequencyIntegration(unittest.TestCase):
    """Integration tests for MONTHLY frequency."""

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_monthly_frequency_invests_first_trading_day(self, mock_fetch, mock_ticker):
        """Test that MONTHLY frequency invests on first trading day of each month."""
        mock_data = create_mock_stock_data(days=90, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            frequency='MONTHLY'
        )

        # 3 months (Jan, Feb, Mar) = 3 investments
        expected_investments = 3 * 1000
        self.assertEqual(result['summary']['total_invested'], expected_investments)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_monthly_frequency_with_margin(self, mock_fetch, mock_ticker):
        """Test MONTHLY frequency with margin trading."""
        mock_data = create_mock_stock_data(days=90, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=5000,
            initial_amount=20000,
            reinvest=False,
            account_balance=25000,
            margin_ratio=2.0,
            frequency='MONTHLY'
        )

        self.assertIsNotNone(result)
        self.assertGreater(result['summary']['total_shares'], 0)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_monthly_frequency_with_withdrawal_mode(self, mock_fetch, mock_ticker):
        """Test MONTHLY frequency with withdrawal mode enabled."""
        mock_data = create_mock_stock_data(days=180, start_price=100)
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
            monthly_withdrawal_amount=5000,
            frequency='MONTHLY'
        )

        self.assertIsNotNone(result)
        # Investments should stop once withdrawal mode activates
        if result['summary']['withdrawal_mode_active']:
            self.assertIsNotNone(result['summary']['withdrawal_mode_start_date'])


class TestFrequencyEdgeCases(unittest.TestCase):
    """Edge case tests for frequency feature."""

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_frequency_parameter_defaults_to_daily(self, mock_fetch, mock_ticker):
        """Test that omitting frequency parameter defaults to DAILY."""
        mock_data = create_mock_stock_data(days=30, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-30',
            amount=1000,
            initial_amount=0,
            reinvest=False
            # frequency NOT specified - should default to DAILY
        )

        # Should invest every trading day
        # Approximately 22 trading days in January
        self.assertGreater(result['summary']['total_invested'], 20000)

    def test_invalid_frequency_rejected_by_api(self):
        """Test that invalid frequency values are rejected (would be caught by API validation)."""
        # This test verifies the helper function handles unknown frequencies gracefully
        # (defaults to DAILY)
        should_invest, month = should_invest_today('2024-01-15', '2024-01-01', 'INVALID', None)
        self.assertTrue(should_invest)  # Defaults to daily

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_benchmark_always_uses_daily_frequency(self, mock_fetch, mock_ticker):
        """Test that benchmark calculations always use DAILY frequency regardless of user's choice."""
        mock_data = create_mock_stock_data(days=60, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        # User chooses WEEKLY frequency
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-01',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            frequency='WEEKLY'
        )

        # Simulate benchmark calculation (in reality done by /calculate endpoint)
        # Benchmark MUST use DAILY frequency
        benchmark_result = calculate_dca_core(
            ticker='BENCH',
            start_date='2024-01-01',
            end_date='2024-03-01',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            target_dates=result['dates'],
            frequency='DAILY'  # CRITICAL: Always DAILY for benchmark
        )

        # Benchmark should have higher total_invested (daily vs weekly)
        self.assertGreater(benchmark_result['summary']['total_invested'],
                         result['summary']['total_invested'])


class TestFrequencyFinancialAccuracy(unittest.TestCase):
    """Financial accuracy tests for frequency feature."""

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_total_invested_accounts_for_frequency(self, mock_fetch, mock_ticker):
        """Test that total_invested correctly reflects investment count based on frequency."""
        mock_data = create_mock_stock_data(days=90, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result_monthly = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            frequency='MONTHLY'
        )

        # 3 months = 3 investments of $1000
        self.assertEqual(result_monthly['summary']['total_invested'], 3000)

    @patch('app.yf.Ticker')
    @patch('app.fetch_stock_data')
    def test_average_cost_consistent_across_frequencies(self, mock_fetch, mock_ticker):
        """Test that average cost calculation remains correct regardless of frequency."""
        mock_data = create_mock_stock_data(days=90, start_price=100)
        mock_fetch.return_value = mock_data

        mock_ticker_instance = Mock()
        mock_ticker_instance.dividends = pd.Series()
        mock_ticker.return_value = mock_ticker_instance

        result_daily = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            frequency='DAILY'
        )

        result_weekly = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            frequency='WEEKLY'
        )

        # With stable price of $100, average cost should be $100 for both
        self.assertAlmostEqual(result_daily['summary']['average_cost'], 100.0, places=2)
        self.assertAlmostEqual(result_weekly['summary']['average_cost'], 100.0, places=2)


if __name__ == '__main__':
    unittest.main()
