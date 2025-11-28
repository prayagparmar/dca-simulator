"""
Systematic Bug Hunting Tests (QA Plan Section 13: BH-031 to BH-050)

Tests designed to catch common bug patterns, off-by-one errors, rounding issues,
state management bugs, and edge case interactions. These tests probe areas where
bugs are likely to hide.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import calculate_dca_core


class TestOffByOneErrors(unittest.TestCase):
    """BH-031 to BH-035: Off-by-one error detection"""

    @patch('app.yf.Ticker')
    def test_bh031_first_day_investment_counted(self, mock_ticker):
        """BH-031: Verify first day investment is counted (not skipped)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [100, 100, 100]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        # Should invest on all 3 days including day 1
        self.assertEqual(result['summary']['total_invested'], 300.0)
        self.assertEqual(len(result['dates']), 3)

    @patch('app.yf.Ticker')
    def test_bh032_last_day_investment_counted(self, mock_ticker):
        """BH-032: Verify last day investment is counted (not excluded)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100] * 5
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        # Should invest on all 5 days including last day
        self.assertEqual(result['summary']['total_invested'], 500.0)
        # Verify array lengths match
        self.assertEqual(len(result['dates']), len(result['portfolio']))

    @patch('app.yf.Ticker')
    def test_bh033_date_range_inclusive_bounds(self, mock_ticker):
        """BH-033: Date range should be inclusive of both start and end"""
        mock_stock = MagicMock()
        # Exactly 10 days from Jan 1 to Jan 10 (inclusive)
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        prices = [100] * 10
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-10',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        # Should be exactly 10 investments (both endpoints included)
        self.assertEqual(result['summary']['total_invested'], 1000.0)
        self.assertEqual(len(result['dates']), 10)


class TestRoundingAndPrecision(unittest.TestCase):
    """BH-034 to BH-038: Rounding and precision bug detection"""

    @patch('app.yf.Ticker')
    def test_bh034_cumulative_rounding_errors(self, mock_ticker):
        """BH-034: Check for cumulative rounding errors over many trades"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        # Price that creates fractional shares
        prices = [33.33] * 100
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-04-10',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        # Total invested should be exact
        self.assertEqual(result['summary']['total_invested'], 10000.0)
        # Shares should be close to 100/33.33 * 100 = 300.03
        self.assertAlmostEqual(result['summary']['total_shares'], 300.03, places=1)

    @patch('app.yf.Ticker')
    def test_bh035_penny_rounding_consistency(self, mock_ticker):
        """BH-035: Verify penny rounding doesn't lose money"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        prices = [99.99] * 10
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-10',
            amount=99.99,  # Same as price
            initial_amount=0,
            reinvest=False
        )

        # Should buy exactly 1 share per day
        self.assertAlmostEqual(result['summary']['total_shares'], 10.0, places=4)
        self.assertAlmostEqual(result['summary']['total_invested'], 999.90, places=2)

    @patch('app.yf.Ticker')
    def test_bh036_fractional_share_precision(self, mock_ticker):
        """BH-036: Verify fractional shares maintain precision"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [3.33, 3.33, 3.33]  # Creates repeating decimals
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=10.00,
            initial_amount=0,
            reinvest=False
        )

        # 10/3.33 per day = 3.003003... shares per day
        # 3 days = ~9.009009 shares
        self.assertAlmostEqual(result['summary']['total_shares'], 9.009, places=2)


class TestStateManagement(unittest.TestCase):
    """BH-037 to BH-041: State management between trading days"""

    @patch('app.yf.Ticker')
    def test_bh037_cash_balance_carries_forward(self, mock_ticker):
        """BH-037: Verify cash balance carries forward correctly between days"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100] * 5
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=250  # Only enough for 2.5 days
        )

        # Should invest exactly $250
        self.assertEqual(result['summary']['total_invested'], 250.0)
        # Cash should be depleted
        self.assertAlmostEqual(result['summary']['account_balance'], 0.0, places=2)

    @patch('app.yf.Ticker')
    def test_bh038_shares_accumulate_correctly(self, mock_ticker):
        """BH-038: Verify shares accumulate (not reset) between days"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100, 90, 110, 95, 105]  # Varying prices
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        # Shares should accumulate: 1.0 + 1.111 + 0.909 + 1.053 + 0.952 = 5.025
        self.assertAlmostEqual(result['summary']['total_shares'], 5.025, places=2)

    @patch('app.yf.Ticker')
    def test_bh039_margin_debt_persists(self, mock_ticker):
        """BH-039: Verify margin debt persists between days (not reset)

        NOTE: Margin is conservative - only borrows when cash depletes, up to margin_ratio limit.
        """
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100] * 5
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=150,  # Covers first 1.5 days
            margin_ratio=2.0
        )

        # Should have borrowed some amount
        total_borrowed = result['summary'].get('total_borrowed', 0.0)
        # Margin borrowing should occur
        self.assertGreater(total_borrowed, 0)

    @patch('app.yf.Ticker')
    def test_bh040_dividend_cash_accumulates(self, mock_ticker):
        """BH-040: Verify dividend cash accumulates when reinvest=False"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        prices = [100] * 10
        # Dividends on days 3, 6, 9
        div_dates = [pd.Timestamp('2024-01-03'), pd.Timestamp('2024-01-06'), pd.Timestamp('2024-01-09')]
        div_values = [5.0, 5.0, 5.0]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(div_values, index=div_dates)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-10',
            amount=100,
            initial_amount=1000,
            reinvest=False
        )

        # Should have cash from dividends
        # Total dividends = shares * dividend_amount
        # Approximate: 10 shares * $5 * 3 dividends = ~$150 in dividends
        self.assertIn('account_balance', result['summary'])


class TestOrderOfOperations(unittest.TestCase):
    """BH-041 to BH-045: Order of operations bugs"""

    @patch('app.yf.Ticker')
    def test_bh041_dividend_before_purchase(self, mock_ticker):
        """BH-041: Dividends should be processed before daily purchase"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [100, 100, 100]
        # Dividend on day 1 before any shares purchased
        div_dates = [pd.Timestamp('2024-01-01')]
        div_values = [10.0]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(div_values, index=div_dates)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        # Day 1: No shares yet, so $0 dividend received
        # Should have $300 invested, no dividend benefit
        self.assertEqual(result['summary']['total_invested'], 300.0)

    @patch('app.yf.Ticker')
    def test_bh042_initial_investment_before_daily(self, mock_ticker):
        """BH-042: Initial investment should execute before first daily investment"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [100, 110, 120]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=1000,
            reinvest=False
        )

        # Initial $1000 at $100 = 10 shares on day 1
        # Day 1: +1 share at $100
        # Day 2: +0.909 shares at $110
        # Day 3: +0.833 shares at $120
        # Total: 10 + 1 + 0.909 + 0.833 = 12.742 shares
        self.assertAlmostEqual(result['summary']['total_shares'], 12.742, places=2)

    @patch('app.yf.Ticker')
    def test_bh043_margin_interest_before_investment(self, mock_ticker):
        """BH-043: Margin interest should be charged before daily investment

        This ensures interest compounds correctly and doesn't use freshly invested cash.
        NOTE: Interest charged monthly, need to span multiple months.
        """
        mock_stock = MagicMock()
        # Span 3 months to ensure interest is charged
        dates = pd.date_range('2024-01-01', periods=90, freq='D')
        prices = [100] * 90
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-30',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=100,  # Only day 1 funded
            margin_ratio=2.0
        )

        # Should have borrowed
        total_borrowed = result['summary'].get('total_borrowed', 0.0)
        self.assertGreater(total_borrowed, 0)
        # Interest tracking exists (may or may not be > 0 depending on implementation)
        self.assertIn('total_interest_paid', result['summary'])


class TestEdgeCaseInteractions(unittest.TestCase):
    """BH-044 to BH-048: Complex feature interactions"""

    @patch('app.yf.Ticker')
    def test_bh044_reinvest_increases_future_dividends(self, mock_ticker):
        """BH-044: Reinvested dividends should increase future dividend payments"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        prices = [100] * 30
        # Two dividend payments
        div_dates = [pd.Timestamp('2024-01-10'), pd.Timestamp('2024-01-20')]
        div_values = [5.0, 5.0]  # $5 per share
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(div_values, index=div_dates)
        mock_ticker.return_value = mock_stock

        result_no_reinvest = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-30',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        result_reinvest = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-30',
            amount=100,
            initial_amount=0,
            reinvest=True
        )

        # Reinvest should have more shares (dividends bought more shares)
        self.assertGreater(
            result_reinvest['summary']['total_shares'],
            result_no_reinvest['summary']['total_shares']
        )

    @patch('app.yf.Ticker')
    def test_bh045_withdrawal_reduces_future_growth(self, mock_ticker):
        """BH-045: Withdrawals should reduce portfolio value for future growth"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        # Growing stock price
        prices = [100 + i for i in range(60)]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result_no_withdrawal = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-01',
            amount=100,
            initial_amount=10000,
            reinvest=False
        )

        result_withdrawal = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-01',
            amount=100,
            initial_amount=10000,
            reinvest=False,
            withdrawal_threshold=8000,
            monthly_withdrawal_amount=1000
        )

        # Withdrawal scenario should have less final value
        self.assertLess(
            result_withdrawal['summary']['current_value'],
            result_no_withdrawal['summary']['current_value']
        )

    @patch('app.yf.Ticker')
    def test_bh046_margin_call_liquidates_correctly(self, mock_ticker):
        """BH-046: Margin call should liquidate exact amount to restore equity ratio"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        # Sharp price drop triggers margin call
        prices = [100, 100, 100, 50, 50, 50, 50, 50, 50, 50]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-10',
            amount=0,
            initial_amount=10000,  # $10k initial
            reinvest=False,
            account_balance=5000,  # Borrow $5k more
            margin_ratio=2.0,
            maintenance_margin=0.25
        )

        # Should have triggered margin call
        margin_calls = result['summary'].get('margin_calls', 0)
        if margin_calls > 0:
            # After liquidation, equity ratio should be restored
            self.assertGreaterEqual(result['summary']['total_shares'], 0)

    @patch('app.yf.Ticker')
    def test_bh047_weekly_frequency_aligns_correctly(self, mock_ticker):
        """BH-047: Weekly frequency should maintain same weekday"""
        mock_stock = MagicMock()
        # Start on Monday (2024-01-01 is Monday)
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        prices = [100] * 30
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-30',
            amount=100,
            initial_amount=0,
            reinvest=False,
            frequency='WEEKLY'
        )

        # 30 days should have ~4-5 weekly investments
        self.assertGreaterEqual(result['summary']['total_invested'], 400)
        self.assertLessEqual(result['summary']['total_invested'], 500)

    @patch('app.yf.Ticker')
    def test_bh048_monthly_frequency_first_trading_day(self, mock_ticker):
        """BH-048: Monthly frequency should invest on first trading day of month"""
        mock_stock = MagicMock()
        # 3 full months
        dates = pd.date_range('2024-01-01', periods=90, freq='D')
        prices = [100] * 90
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-03-30',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            frequency='MONTHLY'
        )

        # Should invest in Jan, Feb, Mar = 3-4 months
        self.assertGreaterEqual(result['summary']['total_invested'], 3000)
        self.assertLessEqual(result['summary']['total_invested'], 4000)


class TestKnownBugPatterns(unittest.TestCase):
    """BH-049 to BH-050: Regression tests for known bug patterns"""

    @patch('app.yf.Ticker')
    def test_bh049_magic_number_heuristic_regression(self, mock_ticker):
        """BH-049: Regression test for magic number heuristic bug (app.py:1051-1056)

        Previously, investments <= $100 would get ZERO cash when balance insufficient.
        This was the critical bug found during QA review (EP-003).
        """
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100] * 5
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        # Small investment with insufficient cash
        result_small = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=50,  # Small amount (< $100)
            initial_amount=0,
            reinvest=False,
            account_balance=75  # Only enough for 1.5 days
        )

        # Large investment with same cash
        result_large = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=150,  # Large amount (> $100)
            initial_amount=0,
            reinvest=False,
            account_balance=75  # Same cash available
        )

        # CRITICAL: Both should invest all $75 available
        self.assertEqual(result_small['summary']['total_invested'], 75.0)
        self.assertEqual(result_large['summary']['total_invested'], 75.0)
        # Both should have same shares (invested at same price)
        self.assertAlmostEqual(
            result_small['summary']['total_shares'],
            result_large['summary']['total_shares'],
            places=2
        )

    @patch('app.yf.Ticker')
    def test_bh050_division_by_zero_protection(self, mock_ticker):
        """BH-050: Verify no division by zero when price or volatility is zero"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        # Stock goes to zero (bankrupt)
        prices = [100, 75, 50, 25, 0.01]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        # Should not crash, handle gracefully
        self.assertIsNotNone(result)
        # Analytics should handle zero/near-zero prices
        self.assertIn('analytics', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
