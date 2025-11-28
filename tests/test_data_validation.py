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


class TestExtendedDataValidation(unittest.TestCase):
    """DV-021 to DV-040: Extended data validation tests"""

    @patch('app.yf.Ticker')
    def test_dv021_invalid_frequency(self, mock_ticker):
        """DV-021: Invalid frequency value (not DAILY/WEEKLY/MONTHLY)

        NOTE: App may not validate frequency at calculate_dca_core level.
        Invalid frequency might default to DAILY or cause error.
        """
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100] * 5
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        # Test with invalid frequency
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,
            initial_amount=0,
            reinvest=False,
            frequency='INVALID'  # Invalid frequency
        )

        # Should either reject or default to a valid frequency
        self.assertTrue(result is None or 'summary' in result)

    @patch('app.yf.Ticker')
    def test_dv022_very_large_initial_amount(self, mock_ticker):
        """DV-022: Very large initial amount (billions)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [100, 101, 102]
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
            initial_amount=1000000000000,  # $1 trillion
            reinvest=False
        )

        self.assertIsNotNone(result)
        # Should handle large numbers
        self.assertGreater(result['summary']['total_invested'], 1000000000000)

    @patch('app.yf.Ticker')
    def test_dv023_negative_initial_amount(self, mock_ticker):
        """DV-023: Negative initial investment"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [100] * 3
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
            initial_amount=-1000,  # Negative (invalid)
            reinvest=False
        )

        # Should handle gracefully
        self.assertTrue(result is None or result['summary']['total_shares'] >= 0)

    @patch('app.yf.Ticker')
    def test_dv024_fractional_penny_amount(self, mock_ticker):
        """DV-024: Fractional penny amount ($0.001)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        prices = [1] * 10
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-10',
            amount=0.001,  # Sub-penny
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        # Should handle fractional pennies
        self.assertGreater(result['summary']['total_shares'], 0)

    @patch('app.yf.Ticker')
    def test_dv025_margin_ratio_exactly_one(self, mock_ticker):
        """DV-025: Margin ratio exactly 1.0 (boundary)"""
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
            margin_ratio=1.0  # Exactly 1.0 - no margin
        )

        self.assertIsNotNone(result)
        # No borrowing should occur
        self.assertEqual(result['summary'].get('total_borrowed', 0.0), 0.0)

    @patch('app.yf.Ticker')
    def test_dv026_margin_ratio_below_one(self, mock_ticker):
        """DV-026: Margin ratio below 1.0 (invalid)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [100] * 3
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
            reinvest=False,
            margin_ratio=0.5  # Less than 1.0 (invalid)
        )

        # Should handle gracefully or reject
        self.assertTrue(result is None or 'summary' in result)

    @patch('app.yf.Ticker')
    def test_dv027_maintenance_margin_above_one(self, mock_ticker):
        """DV-027: Maintenance margin above 1.0 (100%)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [100, 95, 90]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=0,
            initial_amount=10000,
            reinvest=False,
            account_balance=5000,
            margin_ratio=2.0,
            maintenance_margin=1.5  # > 100% (invalid)
        )

        # Should handle gracefully
        self.assertTrue(result is None or 'summary' in result)

    @patch('app.yf.Ticker')
    def test_dv028_negative_maintenance_margin(self, mock_ticker):
        """DV-028: Negative maintenance margin"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        prices = [100] * 3
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
            reinvest=False,
            margin_ratio=2.0,
            maintenance_margin=-0.25  # Negative (invalid)
        )

        # Should handle gracefully
        self.assertTrue(result is None or 'summary' in result)

    @patch('app.yf.Ticker')
    def test_dv029_withdrawal_threshold_zero(self, mock_ticker):
        """DV-029: Withdrawal threshold of $0"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100, 105, 110, 115, 120]
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
            initial_amount=1000,
            reinvest=False,
            withdrawal_threshold=0,  # $0 threshold - always withdraw
            monthly_withdrawal_amount=50
        )

        # Should trigger withdrawal immediately
        self.assertIsNotNone(result)
        self.assertIn('summary', result)

    @patch('app.yf.Ticker')
    def test_dv030_withdrawal_amount_negative(self, mock_ticker):
        """DV-030: Negative monthly withdrawal amount"""
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
            initial_amount=10000,
            reinvest=False,
            withdrawal_threshold=5000,
            monthly_withdrawal_amount=-100  # Negative (invalid)
        )

        # Should handle gracefully
        self.assertTrue(result is None or 'summary' in result)

    @patch('app.yf.Ticker')
    def test_dv031_withdrawal_exceeds_portfolio(self, mock_ticker):
        """DV-031: Withdrawal amount exceeds portfolio value"""
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
            initial_amount=1000,
            reinvest=False,
            withdrawal_threshold=500,
            monthly_withdrawal_amount=50000  # Huge withdrawal
        )

        # Should handle gracefully (liquidate all or cap withdrawal)
        self.assertIsNotNone(result)
        self.assertIn('summary', result)

    @patch('app.yf.Ticker')
    def test_dv032_same_start_end_date(self, mock_ticker):
        """DV-032: Start date equals end date (single day)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-15', periods=1, freq='D')
        prices = [100]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-15',
            end_date='2024-01-15',  # Same date
            amount=100,
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        # Single day investment
        self.assertEqual(result['summary']['total_invested'], 100.0)

    @patch('app.yf.Ticker')
    def test_dv033_reinvest_with_no_dividends(self, mock_ticker):
        """DV-033: Reinvest enabled but no dividends paid"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        prices = [100 + i for i in range(10)]
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)  # No dividends
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-10',
            amount=100,
            initial_amount=0,
            reinvest=True  # Reinvest enabled
        )

        self.assertIsNotNone(result)
        # Should work normally even without dividends
        self.assertEqual(result['summary']['total_invested'], 1000.0)

    @patch('app.yf.Ticker')
    def test_dv034_zero_price_stock(self, mock_ticker):
        """DV-034: Stock with $0 price (delisted/bankrupt)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100, 50, 10, 1, 0]  # Goes to zero
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

        # Should handle gracefully (avoid division by zero)
        self.assertTrue(result is None or 'summary' in result)

    @patch('app.yf.Ticker')
    def test_dv035_extremely_high_price(self, mock_ticker):
        """DV-035: Extremely high stock price (Berkshire Hathaway scenario)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [500000, 505000, 510000, 515000, 520000]  # $500k+
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,  # Small amount vs high price
            initial_amount=0,
            reinvest=False
        )

        self.assertIsNotNone(result)
        # Should accumulate tiny fractional shares
        self.assertGreater(result['summary']['total_shares'], 0)
        self.assertLess(result['summary']['total_shares'], 0.01)

    @patch('app.yf.Ticker')
    def test_dv036_weekly_frequency_single_week(self, mock_ticker):
        """DV-036: Weekly frequency with only one week of data"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=7, freq='D')
        prices = [100] * 7
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-07',
            amount=100,
            initial_amount=0,
            reinvest=False,
            frequency='WEEKLY'
        )

        self.assertIsNotNone(result)
        # Should make 1-2 investments depending on alignment
        self.assertLessEqual(result['summary']['total_invested'], 200)

    @patch('app.yf.Ticker')
    def test_dv037_monthly_frequency_single_month(self, mock_ticker):
        """DV-037: Monthly frequency with only one month of data"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=31, freq='D')
        prices = [100] * 31
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-31',
            amount=100,
            initial_amount=0,
            reinvest=False,
            frequency='MONTHLY'
        )

        self.assertIsNotNone(result)
        # Should make 1-2 investments
        self.assertLessEqual(result['summary']['total_invested'], 200)

    @patch('app.yf.Ticker')
    def test_dv038_account_balance_exactly_one_investment(self, mock_ticker):
        """DV-038: Account balance exactly covers one investment"""
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
            account_balance=100  # Exactly one investment
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_invested'], 100.0)
        self.assertAlmostEqual(result['summary']['account_balance'], 0.0, places=2)

    @patch('app.yf.Ticker')
    def test_dv039_margin_and_withdrawal_together(self, mock_ticker):
        """DV-039: Margin trading + withdrawal mode enabled simultaneously"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        prices = [100 + i for i in range(30)]  # Growing portfolio
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
            initial_amount=5000,
            reinvest=False,
            margin_ratio=2.0,  # Margin enabled
            withdrawal_threshold=3000,  # Withdrawal enabled
            monthly_withdrawal_amount=500,
            account_balance=2000
        )

        # Should handle complex interaction
        self.assertIsNotNone(result)
        self.assertIn('summary', result)

    @patch('app.yf.Ticker')
    def test_dv040_all_features_enabled(self, mock_ticker):
        """DV-040: All features enabled simultaneously (stress test)"""
        mock_stock = MagicMock()
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        prices = [100 + (i % 10) for i in range(100)]  # Oscillating
        # Add some dividends
        div_dates = pd.date_range('2024-01-15', periods=3, freq='30D')
        div_values = [2.0] * 3
        mock_stock.history.return_value = pd.DataFrame({
            'Close': prices
        }, index=dates)
        mock_stock.dividends = pd.Series(div_values, index=div_dates)
        mock_ticker.return_value = mock_stock

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-04-10',
            amount=100,
            initial_amount=5000,
            reinvest=True,  # Reinvest enabled
            account_balance=10000,  # Limited balance
            margin_ratio=1.5,  # Margin enabled
            maintenance_margin=0.25,
            withdrawal_threshold=8000,  # Withdrawal enabled
            monthly_withdrawal_amount=200,
            frequency='WEEKLY'  # Non-daily frequency
        )

        # Should handle all features together
        self.assertIsNotNone(result)
        self.assertIn('summary', result)
        # Verify key metrics exist
        self.assertIn('total_invested', result['summary'])
        self.assertIn('total_shares', result['summary'])
        self.assertIn('current_value', result['summary'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
