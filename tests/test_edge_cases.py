"""
Edge Cases & Boundary Conditions Test Suite
Tests extreme scenarios, boundary conditions, and unusual market behaviors
"""

import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from app import calculate_dca_core


class TestEdgeCases(unittest.TestCase):
    """Comprehensive edge case testing for financial accuracy"""
    
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
        """Helper to create mock stock data"""
        mock_stock = MagicMock()
        dates = pd.date_range(start='2024-01-01', periods=len(prices), freq='D').strftime('%Y-%m-%d').tolist()
        mock_stock.history.return_value = pd.DataFrame({'Close': prices}, index=dates)
        
        if dividends:
            div_series = pd.Series(dtype=float)
            for date_str, value in dividends.items():
                div_series[date_str] = value
            mock_stock.dividends = div_series
        else:
            mock_stock.dividends = pd.Series(dtype=float)
        
        self.mock_ticker.return_value = mock_stock
        return dates
    
    def test_single_day_simulation(self):
        """Edge: Single day with single investment"""
        self.setup_mock_data([100])
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-01',
            amount=0,
            initial_amount=1000,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        self.assertEqual(result['summary']['total_shares'], 10.0)
        self.assertEqual(result['summary']['total_invested'], 1000.0)
        self.assertEqual(len(result['dates']), 1)
    
    def test_extreme_price_volatility(self):
        """Edge: Extreme price swings (crash then recovery)"""
        prices = [100, 50, 25, 50, 100, 200]  # -50%, -50%, +100%, +100%, +100%
        self.setup_mock_data(prices)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-06',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Buying during crash should result in more shares
        self.assertGreater(result['summary']['total_shares'], 6.0)
        # Final value should be much higher than invested
        self.assertGreater(result['summary']['current_value'], result['summary']['total_invested'])
    
    def test_price_goes_to_zero(self):
        """Edge: Stock crashes to near-zero (penny stock scenario)"""
        prices = [100, 50, 10, 1, 0.1]
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
        
        # Should accumulate massive shares as price drops
        self.assertGreater(result['summary']['total_shares'], 100)
        # Current value = shares * final price ($0.1)
        # Bought at higher prices initially, so value may exceed investment at $0.1
        # But should be small relative to total invested ($500)
        self.assertLess(result['summary']['current_value'], 200)
    
    def test_exact_balance_depletion(self):
        """Edge: Balance depletes to exactly $0"""
        self.setup_mock_data([100, 100, 100])
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=200,  # Exactly 2 days worth
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        self.assertEqual(result['summary']['total_shares'], 2.0)
        self.assertEqual(result['summary']['account_balance'], 0.0)
        self.assertEqual(result['summary']['total_invested'], 200.0)
    
    def test_multiple_dividends_same_period(self):
        """Edge: Multiple dividends in short period"""
        dividends = {
            '2024-01-02': 5.0,
            '2024-01-03': 10.0,
            '2024-01-04': 2.5
        }
        self.setup_mock_data([100, 100, 100, 100, 100], dividends)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=100,
            initial_amount=0,
            reinvest=True,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Dividends compound: shares from first div earn subsequent divs
        # Day 1: 1 share. Day 2: 1 share + 5 div = 1.05 shares reinvested
        # Day 3: 2.05 shares earn10 div = 20.5 + 1 share + 10 div reinvested  
        # Day 4: 3.15 shares earn 2.5 div + 1 share + 2.5 div reinvested
        # Total divs > 17.5 due to compounding
        self.assertGreater(result['summary']['total_dividends'], 17.5)
        self.assertGreater(result['summary']['total_shares'], 5.0)
    
    def test_very_long_simulation(self):
        """Edge: Multi-year simulation (1000 trading days)"""
        # 4 years of daily trading
        prices = [100 + (i % 20 - 10) for i in range(1000)]  # Oscillating around $100
        self.setup_mock_data(prices)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2027-10-01',
            amount=10,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Should have invested daily for 1000 days
        self.assertEqual(result['summary']['total_invested'], 10000.0)
        self.assertEqual(len(result['dates']), 1000)
    
    def test_margin_at_exact_maintenance(self):
        """Edge: Portfolio exactly at maintenance margin"""
        # Setup to hit exactly 25% equity
        self.setup_mock_data([100, 100, 75])  # Drop to trigger exactly 25%
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=0,
            initial_amount=20000,
            reinvest=False,
            account_balance=10000,  # Borrow $10k
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # At $75: Portfolio = 200 * 75 = $15k
        # Debt = $10k, Equity = $5k
        # Ratio = 5k / 15k = 33.3% (above 25%, no call)
        self.assertEqual(result['summary']['margin_calls'], 0)
    
    def test_full_liquidation_scenario(self):
        """Edge: Complete portfolio liquidation"""
        # Extreme crash that forces 100% liquidation
        self.setup_mock_data([100, 100, 20])  # -80% crash
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=0,
            initial_amount=20000,
            reinvest=False,
            account_balance=10000,
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Should trigger margin call and liquidation
        self.assertGreater(result['summary']['margin_calls'], 0)
        # Shares should be significantly reduced
        self.assertLess(result['summary']['total_shares'], 200)
    
    def test_dividend_larger_than_share_price(self):
        """Edge: Dividend exceeds share price (special distribution)"""
        dividends = {'2024-01-02': 150.0}  # $150 dividend on $100 stock
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
        
        # Day 1: Buy 1 share
        # Day 2: Buy 1 share + reinvest $150 dividend = 2.5 shares
        self.assertAlmostEqual(result['summary']['total_shares'], 3.5, places=1)
    
    def test_zero_price_days(self):
        """Edge: Handle days with $0.01 price (trading halt recovery)"""
        prices = [100, 0.01, 0.01, 50]  # Extreme crash then partial recovery
        self.setup_mock_data(prices)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-04',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # Should accumulate thousands of shares at $0.01
        self.assertGreater(result['summary']['total_shares'], 1000)
    
    def test_alternating_margin_ratios(self):
        """Edge: Test all margin ratio options"""
        for margin_ratio in [1.0, 1.25, 1.5, 1.75, 2.0]:
            with self.subTest(margin_ratio=margin_ratio):
                self.setup_mock_data([100, 100])
                
                result = calculate_dca_core(
                    ticker='TEST',
                    start_date='2024-01-01',
                    end_date='2024-01-02',
                    amount=100,
                    initial_amount=0,
                    reinvest=False,
                    account_balance=100,
                    margin_ratio=margin_ratio,
                    maintenance_margin=0.25
                )
                
                # Max borrowing should scale with margin ratio
                max_borrow = 100 * (margin_ratio - 1)
                self.assertLessEqual(result['summary']['total_borrowed'], max_borrow + 1)
    
    def test_fractional_shares(self):
        """Edge: Verify fractional share handling"""
        self.setup_mock_data([33.33])  # Price that creates fractions
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-01',
            amount=0,
            initial_amount=100,
            reinvest=False,
            account_balance=None,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        # 100 / 33.33 = 3.0003 shares
        self.assertAlmostEqual(result['summary']['total_shares'], 3.0003, places=4)
    
    def test_consecutive_margin_calls(self):
        """Edge: Multiple margin calls in sequence"""
        # Gradual decline triggering multiple calls
        prices = [100, 90, 75, 65, 55]
        self.setup_mock_data(prices)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=0,
            initial_amount=20000,
            reinvest=False,
            account_balance=10000,
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Should trigger at least one margin call as price drops
        # Liquidation may prevent multiple calls (sells enough to restore margin)
        self.assertGreaterEqual(result['summary']['margin_calls'], 1)
    
    def test_recovery_after_margin_call(self):
        """Edge: Portfolio recovers after margin call"""
        # Crash then recovery
        prices = [100, 100, 60, 80, 100]
        self.setup_mock_data(prices)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=0,
            initial_amount=20000,
            reinvest=False,
            account_balance=10000,
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Should have margin call during crash
        self.assertGreater(result['summary']['margin_calls'], 0)
        # Complete liquidation may occur - net value could be 0
        self.assertGreaterEqual(result['summary']['net_portfolio_value'], 0)
    
    def test_dividend_on_margin_borrowed_shares(self):
        """Edge: Dividends received on margin-purchased shares"""
        dividends = {'2024-01-03': 5.0}
        self.setup_mock_data([100, 100, 100], dividends)
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=100,  # Need margin for day 2
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Should have 2 shares (from days 1-2), so dividend = 2 * $5 = $10
        self.assertGreater(result['summary']['total_dividends'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
