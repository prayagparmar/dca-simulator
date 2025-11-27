"""
Data Validation Test Suite
Tests input validation, error handling, and edge case inputs
"""

import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from app import calculate_dca_core


class TestDataValidation(unittest.TestCase):
    """Tests for input validation and error handling"""
    
    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()
        self.mock_fed_patcher = patch('app.get_fed_funds_rate')
        self.mock_get_fed_rate = self.mock_fed_patcher.start()
        self.mock_get_fed_rate.return_value = 0.05
    
    def tearDown(self):
        self.mock_ticker_patcher.stop()
        self.mock_fed_patcher.stop()
    
    def test_empty_ticker(self):
        """Should handle empty ticker gracefully"""
        mock_stock = MagicMock()
        mock_stock.history.return_value = pd.DataFrame()
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        self.assertIsNone(result)
    
    def test_invalid_ticker_no_data(self):
        """Should return None for ticker with no data"""
        mock_stock = MagicMock()
        mock_stock.history.return_value = pd.DataFrame()
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='INVALIDTICKER123',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        self.assertIsNone(result)
    
    def test_future_start_date(self):
        """Should handle future dates (no historical data)"""
        mock_stock = MagicMock()
        mock_stock.history.return_value = pd.DataFrame()
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2030-01-01',
            end_date='2030-01-10',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        self.assertIsNone(result)
    
    def test_end_date_before_start_date(self):
        """Should handle reversed date range"""
        mock_stock = MagicMock()
        dates = ['2024-01-03', '2024-01-02', '2024-01-01']  # Reversed
        mock_stock.history.return_value = pd.DataFrame({'Close': [100, 100, 100]}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        self.mock_ticker.return_value = mock_stock
        
        # Should still work (yfinance handles date ordering)
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-03',
            end_date='2024-01-01',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Should get data or return None gracefully
        self.assertTrue(result is None or 'summary' in result)
    
    def test_zero_daily_amount(self):
        """Zero daily investment should work (lump sum only)"""
        mock_stock = MagicMock()
        dates = ['2024-01-01', '2024-01-02']
        mock_stock.history.return_value = pd.DataFrame({'Close': [100, 100]}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=0,  # Zero daily
            initial_amount=1000,  # Only initial
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_shares'], 10.0)
    
    def test_negative_amount(self):
        """Negative amounts should be handled gracefully"""
        mock_stock = MagicMock()
        dates = ['2024-01-01']
        mock_stock.history.return_value = pd.DataFrame({'Close': [100]}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-01',
            amount=-100,  # Negative (invalid)
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Should handle gracefully (likely 0 shares)
        if result:
            self.assertEqual(result['summary']['total_shares'], 0)
    
    def test_extreme_margin_ratio(self):
        """Very high margin ratio"""
        mock_stock = MagicMock()
        dates = ['2024-01-01', '2024-01-02']
        mock_stock.history.return_value = pd.DataFrame({'Close': [100, 100]}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=100,
            margin_ratio=10.0,  # 10x leverage (unrealistic but should work)
            maintenance_margin=0.25
        )
        
        self.assertIsNotNone(result)
        # Should allow significant borrowing
        self.assertGreater(result['summary']['total_borrowed'], 0)
    
    def test_zero_maintenance_margin(self):
        """0% maintenance margin (infinite leverage tolerance)"""
        mock_stock = MagicMock()
        dates = ['2024-01-01', '2024-01-02', '2024-01-03']
        mock_stock.history.return_value = pd.DataFrame({'Close': [100, 100, 50]}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=0,
            initial_amount=20000,
            reinvest=False,
            account_balance=10000,
            margin_ratio=2.0,
            maintenance_margin=0.0  # No margin call threshold
        )
        
        # Should never trigger margin call
        self.assertEqual(result['summary']['margin_calls'], 0)
    
    def test_very_small_investment(self):
        """Penny investments"""
        mock_stock = MagicMock()
        dates = ['2024-01-01', '2024-01-02']
        mock_stock.history.return_value = pd.DataFrame({'Close': [100, 100]}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=0.01,  # 1 cent per day
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        self.assertIsNotNone(result)
        # Should accumulate tiny fractions
        self.assertGreater(result['summary']['total_shares'], 0)
        self.assertLess(result['summary']['total_shares'], 0.001)


if __name__ == '__main__':
    unittest.main(verbosity=2)
