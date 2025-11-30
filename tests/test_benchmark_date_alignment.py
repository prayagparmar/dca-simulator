"""
Tests for benchmark date alignment when tickers have different data ranges.

Bug: When portfolio ticker has data from 2020 but benchmark only from 2021,
the system should start both from 2021 (latest start date), not back-fill
benchmark data with synthetic prices.
"""

import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from app import calculate_dca_core
from tests.conftest import create_mock_stock_data


class TestBenchmarkDateAlignment(unittest.TestCase):
    """Test that benchmark comparisons use the latest common start date"""

    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()

    def tearDown(self):
        self.mock_ticker_patcher.stop()

    def setup_mock_data(self, ticker, prices, start_date):
        """Helper to create mock stock data with specific start date - uses conftest"""
        mock_stock = create_mock_stock_data(prices, start_date=start_date)

        # Store this mock for the specific ticker
        if not hasattr(self, 'ticker_mocks'):
            self.ticker_mocks = {}
        self.ticker_mocks[ticker] = mock_stock

    def mock_ticker_side_effect(self, ticker):
        """Return the appropriate mock based on ticker symbol"""
        return self.ticker_mocks.get(ticker, MagicMock())

    def test_benchmark_starts_later_than_portfolio(self):
        """
        Test: find_common_date_range correctly identifies the overlap

        Scenario:
        - Portfolio ticker (NEWCO): Has data from 2024-01-01 (365 days)
        - Benchmark ticker (OLDCO): Only has data from 2024-07-01 (183 days)
        - Expected: Common range starts from 2024-07-01
        """
        from app import find_common_date_range

        # Portfolio has 365 days of data starting Jan 1
        portfolio_prices = [100 + i * 0.1 for i in range(365)]
        self.setup_mock_data('NEWCO', portfolio_prices, '2024-01-01')

        # Benchmark only has 183 days starting July 1 (newer company)
        benchmark_prices = [100 + i * 0.05 for i in range(183)]
        self.setup_mock_data('OLDCO', benchmark_prices, '2024-07-01')

        # Configure mock to return different data per ticker
        self.mock_ticker.side_effect = self.mock_ticker_side_effect

        # Find common date range
        common_start, common_end, ticker1_data, ticker2_data = find_common_date_range(
            'NEWCO', 'OLDCO', '2024-01-01', '2024-12-31'
        )

        # Verify common range starts from benchmark's start date (later of the two)
        self.assertIsNotNone(common_start)
        self.assertIsNotNone(common_end)

        # Common start should be 2024-07-01 (when benchmark data begins)
        self.assertGreaterEqual(common_start, '2024-07-01',
            "Common start date should be at least 2024-07-01 (when benchmark data starts)")

        # Common end should be 2024-12-31 or close to it
        self.assertLessEqual(common_end, '2024-12-31',
            "Common end date should be no later than requested end date")

        # Verify both datasets are returned
        self.assertIsNotNone(ticker1_data)
        self.assertIsNotNone(ticker2_data)

    def test_portfolio_starts_later_than_benchmark(self):
        """
        Test the opposite case: portfolio data starts later

        Scenario:
        - Benchmark (SPY): Has data from 2024-01-01 (365 days)
        - Portfolio (NEWCO): Only has data from 2024-07-01 (183 days)
        - Expected: Common range starts from 2024-07-01
        """
        from app import find_common_date_range

        # Benchmark has full year
        benchmark_prices = [100 + i * 0.05 for i in range(365)]
        self.setup_mock_data('SPY', benchmark_prices, '2024-01-01')

        # Portfolio only has half year
        portfolio_prices = [100 + i * 0.1 for i in range(183)]
        self.setup_mock_data('NEWCO', portfolio_prices, '2024-07-01')

        self.mock_ticker.side_effect = self.mock_ticker_side_effect

        # Find common date range (portfolio first, benchmark second)
        common_start, common_end, ticker1_data, ticker2_data = find_common_date_range(
            'NEWCO', 'SPY', '2024-01-01', '2024-12-31'
        )

        # Verify common range starts from portfolio's start date (later of the two)
        self.assertIsNotNone(common_start)
        self.assertIsNotNone(common_end)

        # Common start should be 2024-07-01 (when portfolio data begins)
        self.assertGreaterEqual(common_start, '2024-07-01',
            "Common start date should be at least 2024-07-01 (when portfolio data starts)")

        # Verify both datasets are returned
        self.assertIsNotNone(ticker1_data)
        self.assertIsNotNone(ticker2_data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
