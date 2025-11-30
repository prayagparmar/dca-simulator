"""
Comprehensive TDD Test Suite for DCA Simulator
Based on PRD specifications

Test Coverage:
1. Basic DCA Simulation
2. Dividend Management
3. Margin Trading
4. Comparison Features  
5. Average Cost Calculation
6. Edge Cases & Error Handling
"""

import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from app import calculate_dca_core
from tests.conftest import create_mock_stock_data


class TestBasicDCASimulation(unittest.TestCase):
    """Tests for Core DCA Features (PRD Section 1)"""
    
    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()
    
    def tearDown(self):
        self.mock_ticker_patcher.stop()
    
    def setup_mock_data(self, prices, dividends=None):
        """Wrapper around conftest helper"""
        self.mock_ticker.return_value = create_mock_stock_data(prices, dividends=dividends, start_date='2024-01-01')
        return pd.date_range(start='2024-01-01', periods=len(prices), freq='D').strftime('%Y-%m-%d').tolist()
    
    def test_basic_dca_no_dividends(self):
        """PRD: Basic DCA with daily investments"""
        self.setup_mock_data([100, 100, 100])
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Day 1: Buy 1 share @ $100
        # Day 2: Buy 1 share @ $100
        # Day 3: Buy 1 share @ $100
        self.assertEqual(result['summary']['total_shares'], 3.0)
        self.assertEqual(result['summary']['total_invested'], 300.0)
        self.assertEqual(result['summary']['current_value'], 300.0)
        self.assertEqual(result['summary']['roi'], 0.0)
    
    def test_initial_investment(self):
        """PRD: Lump sum initial investment on day 1"""
        self.setup_mock_data([100, 100])
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=100,
            initial_amount=1000,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Day 1: Buy ($1000 + $100) / $100 = 11 shares
        # Day 2: Buy $100 / $100 = 1 share
        self.assertEqual(result['summary']['total_shares'], 12.0)
        self.assertEqual(result['summary']['total_invested'], 1200.0)
    
    def test_account_balance_limit(self):
        """PRD: Account balance limits total investment"""
        self.setup_mock_data([100, 100, 100, 100, 100])
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=250,  # Only enough for 2.5 days
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Day 1: Buy 1 share ($100), cash = $150
        # Day 2: Buy 1 share ($100), cash = $50
        # Day 3: Invest remaining $50 (all available cash), buy 0.5 shares, cash = $0
        # Day 4-5: No cash available, skip
        # CORRECTED BEHAVIOR: Invests all available cash (bug fix removed magic number heuristic)
        self.assertAlmostEqual(result['summary']['total_shares'], 2.5, places=1)
        self.assertAlmostEqual(result['summary']['total_invested'], 250.0, places=1)
        self.assertAlmostEqual(result['summary']['account_balance'], 0.0, places=1)


class TestDividendManagement(unittest.TestCase):
    """Tests for Dividend Features (PRD Section 2)"""
    
    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()
    
    def tearDown(self):
        self.mock_ticker_patcher.stop()
    
    def setup_mock_data(self, prices, dividends=None):
        """Wrapper around conftest helper"""
        self.mock_ticker.return_value = create_mock_stock_data(prices, dividends=dividends, start_date='2024-01-01')
        return pd.date_range(start='2024-01-01', periods=len(prices), freq='D').strftime('%Y-%m-%d').tolist()
    
    def test_dividend_reinvestment_on(self):
        """PRD: Dividends reinvested immediately purchase shares"""
        self.setup_mock_data([100, 100, 100], {'2024-01-02': 5.0})
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=True,  # Reinvest ON
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Day 1: Buy 1 share
        # Day 2: Buy 1 share + dividend (1 share * $5 = $5 / $100 = 0.05 shares)
        # Day 3: Buy 1 share
        self.assertAlmostEqual(result['summary']['total_shares'], 3.05, places=2)
        self.assertEqual(result['summary']['total_dividends'], 5.0)
    
    def test_dividend_reinvestment_off(self):
        """PRD: Dividends accumulate in cash balance"""
        self.setup_mock_data([100, 100, 100], {'2024-01-02': 5.0})
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False,  # Reinvest OFF
            account_balance=250,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Day 1: Buy 1 share. Cash = $150
        # Day 2: Buy 1 share. Dividend = $5 (1 share * $5). Cash = $55
        # Day 3: Invest all $55 ($50 principal + $5 dividend), buy 0.55 shares. Cash = $0
        # CORRECTED BEHAVIOR: Invests all available cash including dividend
        self.assertAlmostEqual(result['summary']['total_shares'], 2.55, places=2)
        self.assertEqual(result['summary']['total_dividends'], 5.0)
        self.assertAlmostEqual(result['summary']['account_balance'], 0.0, places=1)


class TestMarginTrading(unittest.TestCase):
    """Tests for Margin Trading Features (PRD Section 3)"""
    
    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()
        self.mock_fed_patcher = patch('app.get_fed_funds_rate')
        self.mock_get_fed_rate = self.mock_fed_patcher.start()
        self.mock_get_fed_rate.return_value = 0.05  # 5% Fed Rate
    
    def tearDown(self):
        self.mock_ticker_patcher.stop()
        self.mock_fed_patcher.stop()
    
    def setup_mock_data(self, prices, dividends=None):
        """Wrapper around conftest helper"""
        self.mock_ticker.return_value = create_mock_stock_data(prices, dividends=dividends, start_date='2024-01-01')
        return pd.date_range(start='2024-01-01', periods=len(prices), freq='D').strftime('%Y-%m-%d').tolist()
    
    def test_margin_buying_power(self):
        """PRD: Margin enables borrowing when cash depletes"""
        self.setup_mock_data([100, 100])
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=150,  # Only $150 cash
            margin_ratio=2.0,  # 2x leverage
            maintenance_margin=0.25
        )
        
        # Day 1: Buy 1 share with cash ($100), cash = $50
        # Day 2: Buy 1 share: use $50 cash + $50 margin
        self.assertEqual(result['summary']['total_shares'], 2.0)
        self.assertEqual(result['summary']['total_invested'], 150.0)  # Principal only
        self.assertEqual(result['summary']['total_borrowed'], 50.0)
    
    def test_margin_call_and_liquidation(self):
        """PRD: Margin call triggers forced liquidation"""
        # Scenario: Buy with leverage, then price crashes
        self.setup_mock_data([100, 100, 60])  # -40% crash
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=0,
            initial_amount=20000,
            reinvest=False,
            account_balance=10000,  # $10k cash, will borrow $10k
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Day 1: Buy 200 shares @ $100 = $20k (use $10k cash + $10k margin)
        # Day 2: Hold
        # Day 3: Price = $60. Portfolio = $12k. Debt = $10k. Equity = $2k.
        #        Equity ratio = $2k / $12k = 16.67% < 25% → Margin Call!
        
        self.assertGreater(result['summary']['margin_calls'], 0, "Should trigger margin call")
        self.assertLess(result['summary']['total_shares'], 200, "Should liquidate shares")
        self.assertLess(result['summary']['total_borrowed'], 10000, "Should reduce debt")
    
    def test_interest_charges(self):
        """PRD: Monthly interest charged on borrowed amount"""
        # Simulate 2 months to trigger interest
        dates = pd.date_range(start='2024-01-01', end='2024-02-15', freq='D')
        prices = [100] * len(dates)
        
        mock_stock = MagicMock()
        mock_stock.history.return_value = pd.DataFrame({'Close': prices}, index=dates.strftime('%Y-%m-%d').tolist())
        mock_stock.dividends = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-02-15',
            amount=0,
            initial_amount=10000,
            reinvest=False,
            account_balance=5000,  # Borrow $5000
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Should borrow $5000 and pay interest in Feb
        # Interest = $5000 * (5% + 0.5%) / 12 = ~$22.92
        # Since we have no cash left after initial purchase, interest capitalizes into debt
        self.assertAlmostEqual(result['summary']['total_borrowed'], 5022.92, delta=1.0, msg="Interest should capitalize into debt")
        self.assertGreater(result['summary']['total_interest_paid'], 0, "Should charge interest")
        self.assertAlmostEqual(result['summary']['total_interest_paid'], 22.92, delta=1.0)


class TestComparisonFeatures(unittest.TestCase):
    """Tests for Benchmark and No-Margin Comparisons (PRD Section 4)"""
    
    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()
    
    def tearDown(self):
        self.mock_ticker_patcher.stop()
    
    def test_benchmark_comparison(self):
        """PRD: Benchmark comparison uses same investment parameters"""
        # This test would need to call the Flask endpoint to test benchmark
        # For now, we verify the core function returns benchmark data when target_dates is provided
        
        mock_stock = MagicMock()
        dates = pd.date_range(start='2024-01-01', periods=3, freq='D').strftime('%Y-%m-%d').tolist()
        mock_stock.history.return_value = pd.DataFrame({'Close': [100, 110, 120]}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='SPY',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25,
            target_dates=dates  # Aligned to main ticker
        )
        
        self.assertIsNotNone(result)
        self.assertIn('summary', result)


class TestAverageCostCalculation(unittest.TestCase):
    """Tests for Average Cost Feature (PRD Section 5)"""
    
    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()
    
    def tearDown(self):
        self.mock_ticker_patcher.stop()
    
    def setup_mock_data(self, prices, dividends=None):
        """Wrapper around conftest helper"""
        self.mock_ticker.return_value = create_mock_stock_data(prices, dividends=dividends, start_date='2024-01-01')
        return pd.date_range(start='2024-01-01', periods=len(prices), freq='D').strftime('%Y-%m-%d').tolist()
    
    def test_average_cost_basic(self):
        """PRD: Average Cost = Total Cost Basis / Total Shares"""
        self.setup_mock_data([100, 200])
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=1000,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Day 1: Buy $1000 / $100 = 10 shares
        # Day 2: Buy $1000 / $200 = 5 shares
        # Total: 15 shares, $2000 spent
        # Avg Cost = $2000 / 15 = $133.33
        self.assertEqual(result['summary']['total_shares'], 15.0)
        self.assertEqual(result['summary']['total_invested'], 2000.0)
        self.assertAlmostEqual(result['summary']['average_cost'], 133.33, places=2)
    
    def test_average_cost_with_dividends_reinvest(self):
        """PRD: Average cost accounts for dividend-purchased shares"""
        self.setup_mock_data([100, 100], {'2024-01-02': 10.0})
        
        result_reinvest = calculate_dca_core(
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
        
        result_no_reinvest = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',  
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=210,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Both should have similar average costs (not wildly different)
        diff_pct = abs(result_reinvest['summary']['average_cost'] - result_no_reinvest['summary']['average_cost']) / result_no_reinvest['summary']['average_cost']
        self.assertLess(diff_pct, 0.1, "Average cost should be consistent regardless of reinvest setting (< 10% difference)")


class TestEdgeCasesAndErrors(unittest.TestCase):
    """Tests for Edge Cases and Error Handling"""
    
    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()
    
    def tearDown(self):
        self.mock_ticker_patcher.stop()
    
    def test_no_data_available(self):
        """Handle case when no historical data exists"""
        mock_stock = MagicMock()
        mock_stock.history.return_value = pd.DataFrame()  # Empty
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='INVALID',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        self.assertIsNone(result, "Should return None for invalid ticker")
    
    def test_zero_investment(self):
        """Handle zero investment amount"""
        mock_stock = MagicMock()
        dates = ['2024-01-01', '2024-01-02']
        mock_stock.history.return_value = pd.DataFrame({'Close': [100, 100]}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        self.mock_ticker.return_value = mock_stock
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=0,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        self.assertEqual(result['summary']['total_shares'], 0)
        self.assertEqual(result['summary']['total_invested'], 0)


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
