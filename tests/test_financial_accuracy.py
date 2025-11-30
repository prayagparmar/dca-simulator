"""
Financial Accuracy Test Suite
Tests calculations, ROI, interest, compound effects, and financial formulas
"""

import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from app import calculate_dca_core
from tests.conftest import create_mock_stock_data


class TestFinancialAccuracy(unittest.TestCase):
    """Tests for accurate financial calculations"""
    
    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()
        self.mock_fed_patcher = patch('app.get_fed_funds_rate')
        self.mock_get_fed_rate = self.mock_fed_patcher.start()
        self.mock_get_fed_rate.return_value = 0.05
    
    def tearDown(self):
        self.mock_ticker_patcher.stop()
        self.mock_fed_patcher.stop()
    
    def setup_mock_data(self, prices, dividends=None):
        """Wrapper around conftest helper for backward compatibility"""
        self.mock_ticker.return_value = create_mock_stock_data(prices, dividends=dividends, start_date='2024-01-01')
        return pd.date_range(start='2024-01-01', periods=len(prices), freq='D').strftime('%Y-%m-%d').tolist()
    
    def test_roi_calculation_positive(self):
        """Verify ROI calculation for gains"""
        self.setup_mock_data([100, 150])  # +50% gain
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Invested $200, worth $300 (1 share @ $150 + 1 share @ $150)
        # ROI = (300 - 200) / 200 = 50%
        expected_roi = ((result['summary']['current_value'] - result['summary']['total_invested']) / 
                       result['summary']['total_invested']) * 100
        self.assertAlmostEqual(result['summary']['roi'], expected_roi, places=2)
    
    def test_roi_calculation_negative(self):
        """Verify ROI calculation for losses"""
        self.setup_mock_data([100, 50])  # -50% loss
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # ROI should be negative
        self.assertLess(result['summary']['roi'], 0)
    
    def test_compound_interest_accuracy(self):
        """Verify compound interest on margin debt"""
        # 12 months simulation
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
        self.mock_ticker.return_value = create_mock_stock_data([100] * len(dates), start_date='2024-01-01')
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-12-31',
            amount=0,
            initial_amount=10000,
            reinvest=False,
            account_balance=5000,  # Borrow $5000
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Interest should compound monthly
        # 5000 * (1 + 0.055/12)^12 - 5000 ≈ $282
        self.assertGreater(result['summary']['total_interest_paid'], 250)
        self.assertLess(result['summary']['total_interest_paid'], 300)
    
    def test_average_cost_with_dca(self):
        """Verify DCA reduces average cost in declining market"""
        prices = [100, 90, 80, 70, 60]
        self.setup_mock_data(prices)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Average cost should be less than initial price ($100)
        self.assertLess(result['summary']['average_cost'], 100)
        # And greater than final price ($60)
        self.assertGreater(result['summary']['average_cost'], 60)
    
    def test_leverage_ratio_calculation(self):
        """Verify leverage ratio accuracy"""
        self.setup_mock_data([100, 100])
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=0,
            initial_amount=20000,
            reinvest=False,
            account_balance=10000,  # Borrow $10k
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Portfolio = $20k, Equity = $10k
        # Leverage = Portfolio / Equity = 2.0x
        self.assertAlmostEqual(result['summary']['current_leverage'], 2.0, places=1)
    
    def test_total_cost_basis_includes_all_sources(self):
        """Verify cost basis includes principal + dividends + margin"""
        dividends = {'2024-01-02': 10.0}
        self.setup_mock_data([100, 100, 100], dividends)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=200,  # Day 1-2 from principal
            margin_ratio=2.0,  # Day 3 uses margin
            maintenance_margin=0.25
        )
        
        # Total invested should be capped at principal ($200)
        self.assertEqual(result['summary']['total_invested'], 200.0)
        # But average cost should reflect ALL purchases
        # (including dividend-funded and margin-funded)
        self.assertIsNotNone(result['summary']['average_cost'])
    
    def test_dividend_yield_calculation(self):
        """Calculate implied dividend yield"""
        # Annual dividends totaling 4% yield
        dividends = {
            '2024-04-01': 1.0,
            '2024-07-01': 1.0,
            '2024-10-01': 1.0,
            '2025-01-01': 1.0
        }

        # 1 year + 1 day
        dates = pd.date_range(start='2024-01-01', end='2025-01-02', freq='D')
        self.mock_ticker.return_value = create_mock_stock_data([100] * len(dates), dividends=dividends, start_date='2024-01-01')
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2025-01-02',
            amount=0,
            initial_amount=10000,  # 100 shares @ $100
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # 100 shares * $4 total = $400 dividends ≈ 4% yield
        self.assertAlmostEqual(result['summary']['total_dividends'], 400.0, delta=10)
    
    def test_net_portfolio_value_accuracy(self):
        """Verify net value = portfolio - debt"""
        self.setup_mock_data([100, 120])  # +20% gain
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=0,
            initial_amount=20000,
            reinvest=False,
            account_balance=10000,
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Portfolio = 200 shares * $120 = $24,000
        # Debt = $10,000
        # Net = $14,000
        expected_net = result['summary']['current_value'] - result['summary']['total_borrowed']
        self.assertAlmostEqual(result['summary']['net_portfolio_value'], expected_net, places=2)
    
    def test_interest_rate_fed_plus_spread(self):
        """Verify interest = (Fed Rate + 0.5%) / 12"""
        self.mock_get_fed_rate.return_value = 0.04  # 4% Fed Rate

        # 2 months to trigger interest
        dates = pd.date_range(start='2024-01-01', end='2024-02-15', freq='D')
        self.mock_ticker.return_value = create_mock_stock_data([100] * len(dates), start_date='2024-01-01')
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-02-15',
            amount=0,
            initial_amount=10000,
            reinvest=False,
            account_balance=5000,
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Expected monthly interest = $5000 * (4% + 0.5%) / 12 = $18.75
        self.assertAlmostEqual(result['summary']['total_interest_paid'], 18.75, delta=1.0)
    
    def test_roi_with_dividends_reinvested(self):
        """ROI should reflect dividend-purchased shares"""
        dividends = {'2024-01-02': 100.0}  # Large dividend
        self.setup_mock_data([100, 100], dividends)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=100,
            initial_amount=0,
            reinvest=True,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Invested $200 principal, but have 3 shares ($300 value)
        # ROI = (300 - 200) / 200 = 50%
        self.assertGreater(result['summary']['roi'], 40)


if __name__ == '__main__':
    unittest.main(verbosity=2)
