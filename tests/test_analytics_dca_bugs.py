"""
Integration tests for analytics bugs with DCA contributions

These tests expose bugs where DCA contributions contaminate daily returns,
causing Sharpe Ratio and Alpha to be wildly inflated.

Bug Reports:
1. Sharpe shows 5.82 when should be negative (-0.30) for negative CAGR
2. Alpha shows +41.53% when should be ~+3.25%
"""

import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from app import calculate_dca_core, calculate_alpha_from_cagr
from tests.conftest import create_mock_stock_data


class TestAnalyticsDCABugs(unittest.TestCase):
    """Tests that expose analytics calculation bugs with DCA"""

    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()

    def tearDown(self):
        self.mock_ticker_patcher.stop()

    def setup_mock_data(self, prices, dividends=None):
        """Wrapper around conftest helper for backward compatibility"""
        self.mock_ticker.return_value = create_mock_stock_data(prices, dividends=dividends, start_date='2024-01-01')
        return pd.date_range(start='2024-01-01', periods=len(prices), freq='D').strftime('%Y-%m-%d').tolist()

    def test_sharpe_ratio_negative_with_dca_contributions(self):
        """
        Bug #1: Sharpe shows 5.82 when should be negative

        Scenario: 260 trading days (~1 year) with overall negative performance
        - Daily $1000 DCA investment
        - Stock price declines from $100 to ~$92 (8% loss)
        - CAGR: ~-8.33%
        - Expected Sharpe: Negative (losing money)
        - Actual (buggy): 5.82 (inflated by DCA contribution "returns")
        """
        # Create declining prices: 100 → 92 over 260 days
        prices = [100 - (i * 0.03) for i in range(260)]
        self.setup_mock_data(prices)

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-12-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            account_balance=300000
        )

        analytics = result['analytics']
        summary = result['summary']

        # Verify we're in a losing scenario
        self.assertLess(analytics['cagr'], 0,
            "CAGR should be negative (losing money)")

        # THE BUG: Sharpe should be NEGATIVE when losing money
        # Currently shows 5.82 due to DCA contributions inflating returns
        self.assertLess(analytics['sharpe_ratio'], 0,
            f"Sharpe Ratio must be negative when CAGR is negative. "
            f"Got Sharpe={analytics['sharpe_ratio']}, CAGR={analytics['cagr']}%")

        # More specific: Should be around -0.30
        # Sharpe = (CAGR - RiskFree) / Volatility
        # ≈ (-8.33% - 4%) / 41.58% ≈ -0.30
        self.assertGreater(analytics['sharpe_ratio'], -1.0,
            "Sharpe should be around -0.30, not extremely negative")

    def test_alpha_reasonable_magnitude_with_dca(self):
        """
        Bug #2: Alpha shows +41.53% when should be ~+3.25%

        Scenario: Both portfolio and benchmark lose money, but portfolio loses less
        - Portfolio: Loses 6.41% (CAGR ~-8.33%)
        - Benchmark: Loses 11.5%
        - Beta: 0.84
        - Expected Alpha: -6.41% - (0.84 × -11.5%) ≈ +3.25%
        - Actual (buggy): +41.53% (inflated 12.8×!)
        """
        # Portfolio loses ~6% over the period
        portfolio_prices = [100 - (i * 0.023) for i in range(260)]
        self.setup_mock_data(portfolio_prices)

        portfolio_result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-12-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            account_balance=300000
        )

        # Benchmark loses ~11% over the period
        benchmark_prices = [100 - (i * 0.043) for i in range(260)]
        self.setup_mock_data(benchmark_prices)

        benchmark_result = calculate_dca_core(
            ticker='BENCH',
            start_date='2024-01-01',
            end_date='2024-12-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            account_balance=300000,
            target_dates=portfolio_result['dates']
        )

        # Assume Beta = 0.84 (portfolio is less volatile than benchmark)
        beta = 0.84

        # Calculate alpha using the new CAGR-based method
        portfolio_cagr = portfolio_result['analytics']['cagr'] / 100  # Convert to decimal
        benchmark_cagr = benchmark_result['analytics']['cagr'] / 100

        alpha = calculate_alpha_from_cagr(portfolio_cagr, benchmark_cagr, beta)

        # Alpha should be positive (portfolio lost LESS than expected)
        self.assertGreater(alpha, 0,
            "Alpha should be positive when portfolio loses less than benchmark")

        # THE BUG: Alpha should be ~3-5%, NOT 41.53%
        self.assertLess(alpha, 10,
            f"Alpha should be ~3-5%, not {alpha:.2f}%. "
            f"Port CAGR={portfolio_cagr*100:.2f}%, Bench CAGR={benchmark_cagr*100:.2f}%")

        # More specific check: should be around 3.25%
        self.assertAlmostEqual(alpha, 3.25, delta=2.5,
            msg=f"Expected alpha ~3.25%, got {alpha:.2f}%")

    def test_sharpe_matches_manual_calculation(self):
        """
        Verify Sharpe calculated from CAGR matches manual calculation

        This ensures the formula is correct:
        Sharpe = (CAGR - Risk-Free Rate) / Volatility
        """
        # Create scenario with known characteristics
        # Declining market: 15% loss over 1 year
        prices = [100 * (0.85 ** (i / 260)) for i in range(260)]
        self.setup_mock_data(prices)

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-12-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            account_balance=300000
        )

        analytics = result['analytics']

        # Manual calculation
        cagr = analytics['cagr'] / 100  # Convert to decimal
        risk_free = 0.02  # 2%
        volatility = analytics['volatility'] / 100  # Convert to decimal

        if volatility > 0:
            expected_sharpe = (cagr - risk_free) / volatility
            actual_sharpe = analytics['sharpe_ratio']

            self.assertAlmostEqual(actual_sharpe, expected_sharpe, places=2,
                msg=f"Sharpe mismatch: Expected {expected_sharpe:.2f}, got {actual_sharpe:.2f}")

    def test_positive_cagr_yields_positive_sharpe(self):
        """
        When CAGR is positive and > risk-free rate, Sharpe should be positive

        This is a sanity check for the opposite scenario
        """
        # Growing market: 20% gain over 1 year
        prices = [100 * (1.20 ** (i / 260)) for i in range(260)]
        self.setup_mock_data(prices)

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-12-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            account_balance=300000
        )

        analytics = result['analytics']

        # With positive CAGR > risk-free, Sharpe should be positive
        if analytics['cagr'] > 4.0:  # Greater than risk-free rate (2-4%)
            self.assertGreater(analytics['sharpe_ratio'], 0,
                f"Sharpe should be positive when CAGR ({analytics['cagr']}%) > risk-free rate")

    def test_alpha_outperformance_detection(self):
        """
        Verify alpha correctly detects outperformance vs benchmark

        Portfolio: +10% CAGR
        Benchmark: +5% CAGR
        Beta: 1.0
        Expected Alpha: 10% - (1.0 × 5%) = +5%
        """
        # Portfolio: +10% growth
        portfolio_prices = [100 * (1.10 ** (i / 260)) for i in range(260)]
        self.setup_mock_data(portfolio_prices)

        portfolio_result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-12-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            account_balance=300000
        )

        # Benchmark: +5% growth
        benchmark_prices = [100 * (1.05 ** (i / 260)) for i in range(260)]
        self.setup_mock_data(benchmark_prices)

        benchmark_result = calculate_dca_core(
            ticker='BENCH',
            start_date='2024-01-01',
            end_date='2024-12-31',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            account_balance=300000,
            target_dates=portfolio_result['dates']
        )

        # With Beta = 1.0, alpha should be ~5%
        beta = 1.0
        portfolio_cagr = portfolio_result['analytics']['cagr'] / 100
        benchmark_cagr = benchmark_result['analytics']['cagr'] / 100

        alpha = calculate_alpha_from_cagr(portfolio_cagr, benchmark_cagr, beta)

        # Alpha should be around +5% (theoretical)
        # With DCA, actual CAGR differs from price growth due to averaging effects
        # Accept range 3-7% to account for DCA timing
        self.assertAlmostEqual(alpha, 5.0, delta=2.0,
            msg=f"Expected alpha ~5% (±2%), got {alpha:.2f}%")


if __name__ == '__main__':
    unittest.main(verbosity=2)
