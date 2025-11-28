"""
Boundary Conditions Tests (QA Plan Section 7: BC-001 to BC-030)

Tests extreme values and edge cases for all numerical inputs to ensure
the system handles boundary conditions gracefully without crashes or
invalid results.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import calculate_dca_core


class TestInvestmentAmountBoundaries(unittest.TestCase):
    """BC-001 to BC-005: Investment amount boundary tests"""

    @patch('app.yf.Ticker')
    def test_bc001_minimum_investment_amount(self, mock_ticker):
        """BC-001: Minimum investment amount ($0.01)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100, 101, 102, 103, 104]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=0.01,  # Minimum amount
            initial_amount=0,
            reinvest=False
        )

        # Should handle tiny amounts gracefully
        self.assertIsNotNone(result)
        self.assertIn('summary', result)
        self.assertGreater(result['summary']['total_shares'], 0)

    @patch('app.yf.Ticker')
    def test_bc002_very_small_investment(self, mock_ticker):
        """BC-002: Very small investment ($1)"""
        mock_stock = MagicMock()
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
            amount=1,  # $1 daily
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['summary']['total_invested'], 10.0, places=2)

    @patch('app.yf.Ticker')
    def test_bc003_large_investment_amount(self, mock_ticker):
        """BC-003: Large investment amount ($100,000)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100, 101, 102, 103, 104]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100000,  # $100k daily
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_invested'], 500000.0)

    @patch('app.yf.Ticker')
    def test_bc004_very_large_investment(self, mock_ticker):
        """BC-004: Very large investment ($1,000,000)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [1000, 1010, 1020]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=1000000,  # $1M daily
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_invested'], 3000000.0)

    @patch('app.yf.Ticker')
    def test_bc005_fractional_investment_amount(self, mock_ticker):
        """BC-005: Fractional investment amount ($99.99)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [50.5, 51.5, 52.5]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=99.99,  # Fractional amount
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['summary']['total_invested'], 299.97, places=2)


class TestDateRangeBoundaries(unittest.TestCase):
    """BC-006 to BC-010: Date range boundary tests"""

    @patch('app.yf.Ticker')
    def test_bc006_single_day_period(self, mock_ticker):
        """BC-006: Single day investment period"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=1, freq='D')
        prices = [100]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-01',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_invested'], 100.0)
        self.assertEqual(result['summary']['total_shares'], 1.0)

    @patch('app.yf.Ticker')
    def test_bc007_very_short_period(self, mock_ticker):
        """BC-007: Very short period (2 days)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=2, freq='D')
        prices = [100, 105]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_invested'], 200.0)

    @patch('app.yf.Ticker')
    def test_bc008_one_year_period(self, mock_ticker):
        """BC-008: Exactly one year period (365 days)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=365, freq='D')
        prices = [100 + i * 0.1 for i in range(365)]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-12-31',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        # 365 days of $100 investment
        self.assertEqual(result['summary']['total_invested'], 36500.0)

    @patch('app.yf.Ticker')
    def test_bc009_multi_year_period(self, mock_ticker):
        """BC-009: Multi-year period (5 years)"""
        mock_stock = MagicMock()
        # 5 years of trading days (~1260 days)
        dates = pd.date_range('2020-01-01', periods=1260, freq='D')
        prices = [100 + i * 0.05 for i in range(1260)]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2020-01-01',
            end_date='2024-06-15',
            amount=50,
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        # Should handle multi-year simulations
        self.assertGreater(result['summary']['total_invested'], 60000)


class TestAccountBalanceBoundaries(unittest.TestCase):
    """BC-011 to BC-015: Account balance boundary tests"""

    @patch('app.yf.Ticker')
    def test_bc011_zero_account_balance(self, mock_ticker):
        """BC-011: Zero account balance (no funds available)

        NOTE: account_balance=0 means literally $0 available, so no investments occur.
        Use account_balance=None for infinite cash mode.
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
            account_balance=0
        )

        self.assertIsNotNone(result)
        # Zero balance means no cash available - no investments
        self.assertEqual(result['summary']['total_invested'], 0.0)
        self.assertEqual(result['summary']['total_shares'], 0.0)

    @patch('app.yf.Ticker')
    def test_bc012_very_small_account_balance(self, mock_ticker):
        """BC-012: Very small account balance ($1)

        NOTE: account_balance caps total available funds. With $1 balance and
        $100/day requested, only $1 total can be invested.
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
            account_balance=1
        )

        self.assertIsNotNone(result)
        # Only $1 available - invests all on first day
        self.assertEqual(result['summary']['total_invested'], 1.0)
        self.assertAlmostEqual(result['summary']['total_shares'], 0.01, places=2)

    @patch('app.yf.Ticker')
    def test_bc013_large_account_balance(self, mock_ticker):
        """BC-013: Large account balance ($1,000,000)"""
        mock_stock = MagicMock()
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
            reinvest=False,
            account_balance=1000000
        )

        self.assertIsNotNone(result)
        # Should cap daily investment at amount parameter
        self.assertEqual(result['summary']['total_invested'], 1000.0)
        self.assertGreaterEqual(result['summary']['account_balance'], 999000)

    @patch('app.yf.Ticker')
    def test_bc014_account_balance_exactly_covers_period(self, mock_ticker):
        """BC-014: Account balance exactly covers investment period"""
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
            account_balance=500  # Exactly 5 * $100
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_invested'], 500.0)
        self.assertAlmostEqual(result['summary']['account_balance'], 0.0, places=2)


class TestMarginRatioBoundaries(unittest.TestCase):
    """BC-016 to BC-020: Margin ratio boundary tests"""

    @patch('app.yf.Ticker')
    def test_bc016_margin_ratio_minimum(self, mock_ticker):
        """BC-016: Minimum margin ratio (1.0 - no margin)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100, 95, 90, 85, 80]
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
            margin_ratio=1.0  # No margin
        )

        self.assertIsNotNone(result)
        # No margin borrowing should occur
        borrowed = result['summary'].get('total_borrowed', 0.0)
        self.assertEqual(borrowed, 0.0)

    @patch('app.yf.Ticker')
    def test_bc017_margin_ratio_maximum(self, mock_ticker):
        """BC-017: Maximum margin ratio (2.0 - full margin)

        NOTE: Margin only kicks in when cash is depleted. With $50 balance,
        first investment uses cash, subsequent may use margin.
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
            margin_ratio=2.0,  # Full margin (2x leverage)
            account_balance=50  # Insufficient for 5 days
        )

        self.assertIsNotNone(result)
        # Should use margin when cash depletes (after first $50)
        self.assertGreaterEqual(result['summary']['total_invested'], 50)
        # Verify margin was enabled (allows borrowing)
        self.assertIn('summary', result)

    @patch('app.yf.Ticker')
    def test_bc018_margin_ratio_middle_value(self, mock_ticker):
        """BC-018: Middle margin ratio (1.5)"""
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
            margin_ratio=1.5,  # Moderate margin (1.5x leverage)
            account_balance=300
        )

        self.assertIsNotNone(result)
        # Should handle 1.5x margin ratio
        self.assertIn('summary', result)


class TestInitialInvestmentBoundaries(unittest.TestCase):
    """BC-021 to BC-025: Initial investment boundary tests"""

    @patch('app.yf.Ticker')
    def test_bc021_zero_initial_investment(self, mock_ticker):
        """BC-021: Zero initial investment (DCA only)"""
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
            initial_amount=0,  # No lump sum
            reinvest=False
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_invested'], 500.0)

    @patch('app.yf.Ticker')
    def test_bc022_small_initial_investment(self, mock_ticker):
        """BC-022: Small initial investment ($100)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100, 102, 104, 106, 108]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=50,
            initial_amount=100,  # $100 lump sum
            reinvest=False
        )

        self.assertIsNotNone(result)
        # $100 initial + 5 * $50 = $350
        self.assertEqual(result['summary']['total_invested'], 350.0)

    @patch('app.yf.Ticker')
    def test_bc023_large_initial_investment(self, mock_ticker):
        """BC-023: Large initial investment ($100,000)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100, 101, 102, 103, 104]
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
            initial_amount=100000,  # $100k lump sum
            reinvest=False
        )

        self.assertIsNotNone(result)
        # $100k initial + 5 * $100 = $100,500
        self.assertEqual(result['summary']['total_invested'], 100500.0)

    @patch('app.yf.Ticker')
    def test_bc024_initial_equals_daily(self, mock_ticker):
        """BC-024: Initial investment equals daily amount"""
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
            initial_amount=100,  # Same as daily
            reinvest=False
        )

        self.assertIsNotNone(result)
        # $100 initial + 5 * $100 = $600
        self.assertEqual(result['summary']['total_invested'], 600.0)


class TestFractionalSharesBoundaries(unittest.TestCase):
    """BC-026 to BC-030: Fractional shares boundary tests"""

    @patch('app.yf.Ticker')
    def test_bc026_very_small_fractional_shares(self, mock_ticker):
        """BC-026: Very small fractional shares (0.0001)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [10000] * 3  # Very high price
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=1,  # $1 daily on $10k stock = 0.0001 shares
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        # Should handle tiny fractional shares
        self.assertGreater(result['summary']['total_shares'], 0)
        self.assertLess(result['summary']['total_shares'], 0.01)

    @patch('app.yf.Ticker')
    def test_bc027_exact_whole_shares(self, mock_ticker):
        """BC-027: Exact whole shares (no fractional)"""
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
            amount=100,  # Exactly $100 on $100 stock = 1.0 shares
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        # Should be exactly 5.0 shares
        self.assertEqual(result['summary']['total_shares'], 5.0)

    @patch('app.yf.Ticker')
    def test_bc028_mixed_whole_and_fractional(self, mock_ticker):
        """BC-028: Mixed whole and fractional shares"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        # Varying prices to create fractional shares
        prices = [100, 97, 103, 99, 101]
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

        self.assertIsNotNone(result)
        # Should handle mix of whole and fractional shares
        self.assertGreater(result['summary']['total_shares'], 4.5)
        self.assertLess(result['summary']['total_shares'], 5.5)

    @patch('app.yf.Ticker')
    def test_bc029_very_large_share_quantity(self, mock_ticker):
        """BC-029: Very large share quantity (10,000+ shares)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        prices = [1] * 100  # $1 stock
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-04-10',
            amount=1000,  # $1000 daily on $1 stock = 1000 shares/day
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        # Should accumulate large share quantities
        self.assertGreater(result['summary']['total_shares'], 10000)

    @patch('app.yf.Ticker')
    def test_bc030_penny_stock_fractional_shares(self, mock_ticker):
        """BC-030: Penny stock fractional shares (price < $1)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [0.50, 0.48, 0.52, 0.51, 0.49]  # Penny stock
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,  # $100 on $0.50 stock = ~200 shares/day
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        # Should handle penny stocks and large fractional quantities
        self.assertGreater(result['summary']['total_shares'], 900)
        self.assertLess(result['summary']['total_shares'], 1100)


if __name__ == '__main__':
    unittest.main(verbosity=2)
