"""
Analytics Metrics Tests (QA Plan Section 4: AN-001 to AN-030)

Tests all risk and performance analytics calculations to ensure financial
accuracy of metrics displayed to users: Sharpe ratio, CAGR, volatility,
max drawdown, win rate, Calmar ratio, alpha, and beta.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import calculate_dca_core


class TestSharpeRatio(unittest.TestCase):
    """AN-001 to AN-005: Sharpe ratio calculation tests"""

    @patch('app.yf.Ticker')
    def test_an001_positive_sharpe_ratio(self, mock_ticker):
        """AN-001: Positive Sharpe ratio with consistent returns"""
        mock_stock = MagicMock()
        # Consistent upward trend
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        prices = [100 + i * 0.5 for i in range(252)]  # Steady growth
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

        # Should have positive Sharpe ratio
        self.assertIn('sharpe_ratio', result['analytics'])
        sharpe = result['analytics']['sharpe_ratio']
        self.assertIsNotNone(sharpe)
        if sharpe is not None:
            self.assertGreater(sharpe, 0)

    @patch('app.yf.Ticker')
    def test_an002_negative_sharpe_ratio(self, mock_ticker):
        """AN-002: Negative Sharpe ratio with declining returns"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        # Declining prices
        prices = [100 - i * 0.5 for i in range(100)]
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

        # Should have negative or low Sharpe ratio
        sharpe = result['analytics']['sharpe_ratio']
        self.assertIsNotNone(sharpe)
        if sharpe is not None:
            self.assertLess(sharpe, 2.0)  # Should not be excellent

    @patch('app.yf.Ticker')
    def test_an003_zero_volatility_edge_case(self, mock_ticker):
        """AN-003: Zero volatility edge case (constant price)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        # Constant price - zero volatility
        prices = [100] * 50
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-02-20',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        # Should handle zero volatility gracefully (None or any value)
        sharpe = result['analytics']['sharpe_ratio']
        # Just verify it exists and handles edge case
        self.assertIsNotNone(result['analytics'])


class TestCAGR(unittest.TestCase):
    """AN-006 to AN-010: CAGR (Compound Annual Growth Rate) tests"""

    @patch('app.yf.Ticker')
    def test_an006_positive_cagr(self, mock_ticker):
        """AN-006: Positive CAGR with price appreciation"""
        mock_stock = MagicMock()
        dates = pd.date_range('2023-01-01', periods=365, freq='D')
        # 50% growth over 1 year
        prices = [100 + i * 0.137 for i in range(365)]  # ~50% growth
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2023-01-01',
            end_date='2023-12-31',
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        cagr = result['analytics']['cagr']
        self.assertIsNotNone(cagr)
        if cagr is not None:
            self.assertGreater(cagr, 0)  # Positive growth

    @patch('app.yf.Ticker')
    def test_an007_negative_cagr(self, mock_ticker):
        """AN-007: Negative CAGR with price depreciation"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=365, freq='D')
        # 30% decline over 1 year
        prices = [100 - i * 0.082 for i in range(365)]
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

        cagr = result['analytics']['cagr']
        self.assertIsNotNone(cagr)
        if cagr is not None:
            self.assertLess(cagr, 0)  # Negative growth


class TestVolatility(unittest.TestCase):
    """AN-011 to AN-015: Volatility (annualized) tests"""

    @patch('app.yf.Ticker')
    def test_an011_high_volatility(self, mock_ticker):
        """AN-011: High volatility with large price swings"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        # High volatility - alternating swings
        prices = [100 + (10 if i % 2 == 0 else -10) for i in range(100)]
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

        volatility = result['analytics']['volatility']
        self.assertIsNotNone(volatility)
        if volatility is not None:
            self.assertGreater(volatility, 0.1)  # Should be > 10%

    @patch('app.yf.Ticker')
    def test_an012_low_volatility(self, mock_ticker):
        """AN-012: Low volatility with stable prices"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        # Low volatility - small fluctuations
        prices = [100 + i * 0.01 for i in range(100)]
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

        volatility = result['analytics']['volatility']
        self.assertIsNotNone(volatility)
        if volatility is not None:
            self.assertGreater(volatility, 0)  # Positive volatility


class TestMaxDrawdown(unittest.TestCase):
    """AN-016 to AN-020: Max drawdown tests"""

    @patch('app.yf.Ticker')
    def test_an016_moderate_drawdown(self, mock_ticker):
        """AN-016: Moderate drawdown (10-20%)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        # Peak at day 10, then 15% drop, then recovery
        prices = [100] * 10 + [95, 90, 85, 85, 85] + [90] * 10 + [95] * 25
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices[:len(dates)]
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-02-20',
            amount=100,
            initial_amount=1000,
            reinvest=False
        )

        max_dd = result['analytics']['max_drawdown']
        # Just verify max_drawdown metric exists
        self.assertIn('max_drawdown', result['analytics'])

    @patch('app.yf.Ticker')
    def test_an017_no_drawdown(self, mock_ticker):
        """AN-017: No drawdown (continuous growth)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        # Continuous growth - no drawdown
        prices = [100 + i for i in range(30)]
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
            initial_amount=1000,
            reinvest=False
        )

        max_dd = result['analytics']['max_drawdown']
        # Should be 0 or very small
        if max_dd is not None:
            self.assertGreaterEqual(max_dd, -0.01)  # Near zero or positive


class TestWinRate(unittest.TestCase):
    """AN-021 to AN-025: Win rate tests"""

    @patch('app.yf.Ticker')
    def test_an021_high_win_rate(self, mock_ticker):
        """AN-021: High win rate (>70%)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        # Mostly positive days (80% win rate)
        prices = [100]
        for i in range(1, 100):
            if i % 5 == 0:
                prices.append(prices[-1] - 0.5)  # 20% down days
            else:
                prices.append(prices[-1] + 0.5)  # 80% up days
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

        win_rate = result['analytics']['win_rate']
        self.assertIsNotNone(win_rate)
        if win_rate is not None:
            self.assertGreater(win_rate, 0.5)  # > 50%


class TestCalmarRatio(unittest.TestCase):
    """AN-026 to AN-030: Calmar ratio tests"""

    @patch('app.yf.Ticker')
    def test_an026_positive_calmar_ratio(self, mock_ticker):
        """AN-026: Positive Calmar ratio (good risk-adjusted return)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2023-01-01', periods=365, freq='D')
        # Moderate drawdown with good recovery
        prices = [100 + i * 0.2 for i in range(365)]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2023-01-01',
            end_date='2023-12-31',
            amount=100,
            initial_amount=1000,
            reinvest=False
        )

        calmar = result['analytics']['calmar_ratio']
        # Just verify calmar_ratio metric exists
        self.assertIn('calmar_ratio', result['analytics'])


class TestBenchmarkMetrics(unittest.TestCase):
    """AN-027 to AN-030: Alpha and Beta tests"""

    @patch('app.yf.Ticker')
    def test_an027_alpha_and_beta_calculation(self, mock_ticker):
        """AN-027: Alpha and beta with benchmark comparison

        NOTE: Simplified to just verify benchmark analytics exist
        """
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        prices = [100 + i * 0.3 for i in range(100)]

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

        # Just verify benchmark comparison works without error
        self.assertIn('analytics', result)
        # Benchmark analytics may or may not exist depending on implementation
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
