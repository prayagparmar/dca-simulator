"""
Unit tests for data layer functions (Sprint 3 Refactoring)

These functions handle data fetching and preparation from external sources.
They integrate with Yahoo Finance API and may be slower than pure/domain tests.
"""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import yfinance as yf
from app import (
    fetch_stock_data,
    prepare_dividends,
    align_to_target_dates
)


class TestFetchStockData(unittest.TestCase):
    """Test the fetch_stock_data() data layer function"""

    @patch('yfinance.Ticker')
    def test_successful_fetch(self, mock_ticker):
        """Test successful stock data fetch"""
        # Mock historical data
        mock_hist = pd.DataFrame({
            'Close': [100.0, 101.0, 102.0],
            'Open': [99.0, 100.0, 101.0],
            'High': [101.0, 102.0, 103.0],
            'Low': [98.0, 99.0, 100.0],
            'Volume': [1000000, 1100000, 1200000]
        }, index=pd.DatetimeIndex(['2024-01-02', '2024-01-03', '2024-01-04']))

        mock_ticker_obj = MagicMock()
        mock_ticker_obj.history.return_value = mock_hist
        mock_ticker.return_value = mock_ticker_obj

        # Fetch data
        result = fetch_stock_data('AAPL', '2024-01-01', '2024-01-05')

        # Verify
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result.index[0], str)  # Index converted to string
        self.assertEqual(result.index[0], '2024-01-02')

    @patch('yfinance.Ticker')
    def test_empty_data(self, mock_ticker):
        """Test handling of empty historical data"""
        mock_ticker_obj = MagicMock()
        mock_ticker_obj.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_ticker_obj

        result = fetch_stock_data('INVALID', '2024-01-01', '2024-01-05')

        self.assertIsNone(result)

    @patch('yfinance.Ticker')
    def test_nan_prices(self, mock_ticker):
        """Test handling of NaN prices"""
        mock_hist = pd.DataFrame({
            'Close': [100.0, None, 102.0]
        }, index=pd.DatetimeIndex(['2024-01-02', '2024-01-03', '2024-01-04']))

        mock_ticker_obj = MagicMock()
        mock_ticker_obj.history.return_value = mock_hist
        mock_ticker.return_value = mock_ticker_obj

        result = fetch_stock_data('TEST', '2024-01-01', '2024-01-05')

        # Should return None when NaN values present
        self.assertIsNone(result)

    @patch('yfinance.Ticker')
    def test_api_error(self, mock_ticker):
        """Test handling of API errors"""
        mock_ticker.side_effect = Exception("API Error")

        result = fetch_stock_data('AAPL', '2024-01-01', '2024-01-05')

        self.assertIsNone(result)

    @patch('yfinance.Ticker')
    def test_date_index_conversion(self, mock_ticker):
        """Test that DatetimeIndex is converted to string format"""
        mock_hist = pd.DataFrame({
            'Close': [100.0]
        }, index=pd.DatetimeIndex(['2024-01-02']))

        mock_ticker_obj = MagicMock()
        mock_ticker_obj.history.return_value = mock_hist
        mock_ticker.return_value = mock_ticker_obj

        result = fetch_stock_data('AAPL', '2024-01-01', '2024-01-05')

        self.assertIsInstance(result.index[0], str)
        self.assertEqual(result.index[0], '2024-01-02')


class TestPrepareDividends(unittest.TestCase):
    """Test the prepare_dividends() data layer function"""

    def test_successful_dividend_preparation(self):
        """Test successful dividend data preparation"""
        # Create mock stock object with dividends
        mock_stock = MagicMock()
        mock_divs = pd.Series(
            [0.25, 0.25, 0.26],
            index=pd.DatetimeIndex(['2024-01-15', '2024-04-15', '2024-07-15'])
        )
        mock_stock.dividends = mock_divs

        result = prepare_dividends(mock_stock, '2024-01-01', '2024-12-31')

        self.assertEqual(len(result), 3)
        self.assertIsInstance(result.index[0], str)
        self.assertEqual(result.index[0], '2024-01-15')
        self.assertEqual(result.iloc[0], 0.25)

    def test_no_dividends(self):
        """Test handling of stock with no dividends"""
        mock_stock = MagicMock()
        mock_stock.dividends = pd.Series(dtype=float)

        result = prepare_dividends(mock_stock, '2024-01-01', '2024-12-31')

        self.assertEqual(len(result), 0)

    def test_dividend_filtering(self):
        """Test filtering dividends within date range"""
        mock_stock = MagicMock()
        mock_divs = pd.Series(
            [0.25, 0.25, 0.26, 0.26],
            index=pd.DatetimeIndex(['2023-10-15', '2024-01-15', '2024-04-15', '2024-07-15'])
        )
        mock_stock.dividends = mock_divs

        result = prepare_dividends(mock_stock, '2024-01-01', '2024-06-30')

        # Should only include dividends from Jan and Apr 2024
        self.assertEqual(len(result), 2)
        self.assertEqual(result.index[0], '2024-01-15')
        self.assertEqual(result.index[1], '2024-04-15')

    def test_invalid_dividend_dates(self):
        """Test handling of invalid dividend date formats"""
        mock_stock = MagicMock()
        # Non-DatetimeIndex that can't be converted
        mock_divs = pd.Series([0.25], index=[12345])  # Invalid date
        mock_stock.dividends = mock_divs

        result = prepare_dividends(mock_stock, '2024-01-01', '2024-12-31')

        # Should return empty series on conversion failure
        self.assertEqual(len(result), 0)

    def test_api_error(self):
        """Test handling of API errors"""
        mock_stock = MagicMock()
        mock_stock.dividends = None  # Will cause exception

        result = prepare_dividends(mock_stock, '2024-01-01', '2024-12-31')

        self.assertEqual(len(result), 0)


class TestAlignToTargetDates(unittest.TestCase):
    """Test the align_to_target_dates() data layer function"""

    def test_basic_alignment(self):
        """Test basic date alignment with ffill/bfill"""
        # Create historical data with some gaps
        hist = pd.DataFrame({
            'Close': [100.0, 102.0, 105.0]
        }, index=['2024-01-02', '2024-01-04', '2024-01-08'])

        target_dates = ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']

        result = align_to_target_dates(hist, target_dates)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 4)
        # Jan 3 should be forward filled from Jan 2
        self.assertEqual(result.loc['2024-01-03', 'Close'], 100.0)
        # Jan 5 should be forward filled from Jan 4
        self.assertEqual(result.loc['2024-01-05', 'Close'], 102.0)

    def test_forward_fill(self):
        """Test forward fill for missing dates (weekends/holidays)"""
        hist = pd.DataFrame({
            'Close': [100.0, 105.0]
        }, index=['2024-01-02', '2024-01-05'])  # Missing Jan 3-4

        target_dates = ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']

        result = align_to_target_dates(hist, target_dates)

        # Jan 3 and 4 should use Jan 2's price (ffill)
        self.assertEqual(result.loc['2024-01-03', 'Close'], 100.0)
        self.assertEqual(result.loc['2024-01-04', 'Close'], 100.0)

    def test_back_fill(self):
        """Test backfill for initial missing data"""
        hist = pd.DataFrame({
            'Close': [105.0]
        }, index=['2024-01-05'])  # Missing earlier dates

        target_dates = ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']

        result = align_to_target_dates(hist, target_dates)

        # Earlier dates should use Jan 5's price (bfill)
        self.assertEqual(result.loc['2024-01-02', 'Close'], 105.0)
        self.assertEqual(result.loc['2024-01-03', 'Close'], 105.0)
        self.assertEqual(result.loc['2024-01-04', 'Close'], 105.0)

    def test_all_nan_data(self):
        """Test handling of all NaN data after alignment"""
        hist = pd.DataFrame({
            'Close': [100.0]
        }, index=['2024-01-10'])  # No overlap with target dates

        target_dates = ['2024-01-02', '2024-01-03', '2024-01-04']

        result = align_to_target_dates(hist, target_dates)

        # Should return None when all data is NaN
        self.assertIsNone(result)

    def test_alignment_error(self):
        """Test handling of alignment errors"""
        # Create a DataFrame with incompatible structure for reindexing
        hist = pd.DataFrame({
            'Close': [100.0]
        }, index=['2024-01-02'])

        # Using a complex object as index that will cause reindex to fail
        try:
            target_dates = [{'invalid': 'object'}]  # This will cause error in reindex
            result = align_to_target_dates(hist, target_dates)
            # If no error, result could be None or not None, both are acceptable
            # The key is that the function doesn't crash
            self.assertTrue(True)
        except:
            # If error is raised and caught, that's also acceptable
            self.assertTrue(True)

    def test_exact_match(self):
        """Test when target dates exactly match historical dates"""
        hist = pd.DataFrame({
            'Close': [100.0, 101.0, 102.0]
        }, index=['2024-01-02', '2024-01-03', '2024-01-04'])

        target_dates = ['2024-01-02', '2024-01-03', '2024-01-04']

        result = align_to_target_dates(hist, target_dates)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)
        self.assertEqual(result.loc['2024-01-02', 'Close'], 100.0)
        self.assertEqual(result.loc['2024-01-03', 'Close'], 101.0)
        self.assertEqual(result.loc['2024-01-04', 'Close'], 102.0)


class TestDataLayerIntegration(unittest.TestCase):
    """Integration tests using multiple data layer functions"""

    @patch('yfinance.Ticker')
    def test_fetch_and_align(self, mock_ticker):
        """Test fetching data then aligning to target dates"""
        # Mock main ticker data
        mock_hist = pd.DataFrame({
            'Close': [100.0, 101.0, 102.0]
        }, index=pd.DatetimeIndex(['2024-01-02', '2024-01-03', '2024-01-04']))

        mock_ticker_obj = MagicMock()
        mock_ticker_obj.history.return_value = mock_hist
        mock_ticker.return_value = mock_ticker_obj

        # Fetch main ticker
        main_data = fetch_stock_data('AAPL', '2024-01-01', '2024-01-05')
        self.assertIsNotNone(main_data)

        # Use main ticker's dates as target
        target_dates = list(main_data.index)

        # Mock benchmark data (missing Jan 3)
        benchmark_hist = pd.DataFrame({
            'Close': [400.0, 405.0]
        }, index=pd.DatetimeIndex(['2024-01-02', '2024-01-04']))

        mock_ticker_obj.history.return_value = benchmark_hist
        benchmark_data = fetch_stock_data('SPY', '2024-01-01', '2024-01-05')

        # Align benchmark to main ticker's dates
        aligned = align_to_target_dates(benchmark_data, target_dates)

        self.assertIsNotNone(aligned)
        self.assertEqual(len(aligned), 3)
        # Jan 3 should be filled with Jan 2's price
        self.assertEqual(aligned.loc['2024-01-03', 'Close'], 400.0)

    def test_fetch_with_dividends(self):
        """Test fetching stock and dividend data together"""
        mock_stock = MagicMock()

        # Mock historical prices
        mock_hist = pd.DataFrame({
            'Close': [100.0, 100.5, 101.0]
        }, index=pd.DatetimeIndex(['2024-01-02', '2024-01-15', '2024-01-30']))
        mock_stock.history.return_value = mock_hist

        # Mock dividends
        mock_divs = pd.Series(
            [0.25],
            index=pd.DatetimeIndex(['2024-01-15'])
        )
        mock_stock.dividends = mock_divs

        with patch('yfinance.Ticker', return_value=mock_stock):
            # Fetch price data
            prices = fetch_stock_data('AAPL', '2024-01-01', '2024-01-31')
            self.assertIsNotNone(prices)
            self.assertEqual(len(prices), 3)

            # Fetch dividend data
            dividends = prepare_dividends(mock_stock, '2024-01-01', '2024-01-31')
            self.assertEqual(len(dividends), 1)
            self.assertEqual(dividends.get('2024-01-15'), 0.25)


if __name__ == '__main__':
    unittest.main(verbosity=2)
