import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from app import calculate_dca_core

class TestConsistencyAndAvgCost(unittest.TestCase):
    def setUp(self):
        # Create mock price data
        self.dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        self.prices = [100.0] * 10 # Constant price for simplicity
        self.mock_hist = pd.DataFrame({'Close': self.prices}, index=self.dates)
        
        # Mock Dividends (High enough to matter)
        self.mock_dividends = pd.Series([0.0] * 10, index=self.dates)
        # Add a big dividend on day 5
        self.mock_dividends.iloc[4] = 5.0 # $5/share

    @patch('app.yf.Ticker')
    def test_investment_consistency_reinvest_off(self, mock_ticker_class):
        """
        Verify that total_invested is capped at initial principal even if dividends are used to buy more.
        """
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self.mock_hist
        mock_ticker.dividends = self.mock_dividends
        mock_ticker_class.return_value = mock_ticker

        # Setup: $1000 initial, $100 daily. 
        # Total Principal = $1000.
        # We run for 10 days. Total needed = $100 * 10 = $1000.
        # But let's say we start with only $500.
        # Day 1-5: Invest $100/day. Principal used = $500.
        # Day 5: Big Dividend received.
        # Day 6-10: Continue investing using Dividend cash.
        # Total Invested should be $500 (Principal), NOT $1000 (Principal + Divs).
        
        initial_balance = 500
        daily_amount = 100
        
        # We need prices to be low enough or dividend high enough.
        # Price $100. 
        # Day 1: Buy 1 share. Cash $400. Invested $100. Shares 1.
        # Day 2: Buy 1 share. Cash $300. Invested $200. Shares 2.
        # Day 3: Buy 1 share. Cash $200. Invested $300. Shares 3.
        # Day 4: Buy 1 share. Cash $100. Invested $400. Shares 4.
        # Day 5: Buy 1 share. Cash $0. Invested $500. Shares 5.
        # Day 5 Div: 5 shares * $50 = $250 dividend (Huge dividend for test).
        # Cash becomes $250.
        # Day 6: Buy 1 share ($100). Cash $150. Invested should still be $500?
        # Day 7: Buy 1 share ($100). Cash $50. Invested should still be $500?
        # Day 8: Buy 0 (Cash $50 < $100).
        
        # Adjust mock dividends to be huge
        self.mock_dividends.iloc[4] = 50.0 # $50/share dividend
        mock_ticker.dividends = self.mock_dividends

        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-10',
            amount=daily_amount,
            initial_amount=0, # No lump sum
            reinvest=False, # Dividends go to cash
            account_balance=initial_balance,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        summary = result['summary']
        
        # Assertions
        self.assertEqual(summary['total_invested'], 500.0, 
                         f"Total Invested should be capped at principal ($500). Got {summary['total_invested']}")
        
        # Verify we actually bought more than 5 shares (meaning we used dividend cash)
        # 5 shares from principal + 2 shares from dividend cash = 7 shares
        self.assertGreater(summary['total_shares'], 5.0, 
                           "Should have bought more shares using dividend cash")

    @patch('app.yf.Ticker')
    def test_average_cost_calculation(self, mock_ticker_class):
        """
        Verify average cost calculation.
        """
        # Scenario:
        # Day 1: Buy 1 share @ $100. Invested $100.
        # Day 2: Buy 1 share @ $200. Invested $200. Total $300. Shares 2. Avg Cost $150.
        
        dates = pd.date_range(start='2024-01-01', periods=2, freq='D')
        prices = [100.0, 200.0]
        mock_hist = pd.DataFrame({'Close': prices}, index=dates)
        mock_dividends = pd.Series([0.0] * 2, index=dates)
        
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_hist
        mock_ticker.dividends = mock_dividends
        mock_ticker_class.return_value = mock_ticker
        
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-02',
            amount=1000, # Enough to buy
            initial_amount=0,
            reinvest=False,
            account_balance=10000,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )
        
        summary = result['summary']
        
        # Day 1: $1000 / $100 = 10 shares. Invested $1000.
        # Day 2: $1000 / $200 = 5 shares. Invested $1000.
        # Total Shares = 15. Total Invested = $2000.
        # Avg Cost = 2000 / 15 = 133.33
        
        expected_avg_cost = 2000.0 / 15.0
        self.assertAlmostEqual(summary['average_cost'], expected_avg_cost, places=2)
        self.assertEqual(summary['total_invested'], 2000.0)

if __name__ == '__main__':
    unittest.main()
