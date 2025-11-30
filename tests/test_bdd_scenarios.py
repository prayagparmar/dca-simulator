import unittest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from app import calculate_dca_core
from tests.conftest import create_mock_stock_data

class TestBDDScenarios(unittest.TestCase):
    """
    BDD-style tests for DCA Simulator with Margin.
    Follows strict Given-When-Then structure to verify PRD requirements.
    """

    def setUp(self):
        # Common setup for mocks
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

    def test_scenario_buying_power_limit(self):
        """
        Scenario: User attempts to invest more than their buying power.
        """
        # GIVEN a user with $10,000 cash and 2x margin
        # Buying Power = $10,000 * 2 = $20,000
        initial_cash = 10000
        margin_ratio = 2.0
        
        # Setup market data (stable price)
        self.setup_mock_data([100] * 5)

        # WHEN they try to invest $25,000 immediately (exceeding $20k limit)
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=0,
            initial_amount=25000,  # Requesting $25k
            reinvest=False,
            account_balance=initial_cash,
            margin_ratio=margin_ratio,
            maintenance_margin=0.25
        )

        # THEN the investment should be capped at the max buying power ($20,000)
        # But 'total_invested' now tracks User Principal ($10k), not Total Position ($20k).
        total_invested = result['summary']['total_invested']
        self.assertAlmostEqual(total_invested, 10000, delta=100, 
                             msg="Total Invested should reflect User Principal ($10k)")
        
        # Verify Total Position Size (Current Value) is $20k
        current_value = result['summary']['current_value']
        self.assertAlmostEqual(current_value, 20000, delta=100,
                             msg="Current Value should reflect full buying power usage ($20k)")

        # AND the user should have borrowed exactly the max allowed ($10,000)
        total_borrowed = result['summary']['total_borrowed']
        self.assertAlmostEqual(total_borrowed, 10000, delta=100,
                             msg="Should borrow exactly up to the limit ($10k)")

    def test_scenario_interest_payment_hierarchy(self):
        """
        Scenario: Interest payment uses available cash first, then capitalizes.
        """
        # GIVEN a user with a margin loan and a small amount of cash
        # $10k invested, $5k borrowed, $100 cash remaining
        initial_cash = 5100  # $5k for investment + $100 buffer
        margin_ratio = 2.0
        
        # Setup data: 2 months to trigger interest payment
        # Month 1: Stable
        # Month 2: Stable
        dates = pd.date_range(start='2024-01-01', end='2024-02-28', freq='D').strftime('%Y-%m-%d').tolist()
        prices = [100] * len(dates)
        
        mock_stock = MagicMock()
        mock_stock.history.return_value = pd.DataFrame({'Close': prices}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        self.mock_ticker.return_value = mock_stock

        # WHEN the month changes and interest is charged
        # Interest on ~$5k at ~5.5% (5% fed + 0.5%) for 1 month
        # Approx: $5000 * 0.055 / 12 = ~$22.91
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-02-28',
            amount=0,
            initial_amount=10000, # Invest $10k ($5k cash + $5k margin)
            reinvest=False,
            account_balance=initial_cash, # $5100 ($100 extra)
            margin_ratio=margin_ratio,
            maintenance_margin=0.25
        )

        # THEN the interest should be paid from the $100 cash buffer
        interest_paid = result['summary']['total_interest_paid']
        self.assertGreater(interest_paid, 0)
        
        # AND the borrowed amount should NOT increase (no capitalization)
        # Initial borrow $4900 ($10k req - $5100 cash) -> Wait, logic uses all cash first
        # Actually: Invest $10k. Have $5100. Use $5100 cash. Borrow $4900.
        # Cash remaining = $0.
        # Wait, I need to preserve cash to test "pay from cash".
        # Let's use a daily investment that leaves cash.
        
        # RETRY SETUP:
        # Invest $5000 initial. Have $10,000 cash.
        # Borrowing = 0.
        # Wait, to test interest we need borrowing.
        # Invest $15,000. Have $10,000 cash. Borrow $5,000. Cash = 0.
        # To have cash AND debt, we need to receive a dividend or add cash? 
        # The current simulation doesn't support adding cash mid-stream.
        # BUT, dividends add to cash!
        
        # Let's inject a dividend before month end.
        dividend_date = '2024-01-15'
        mock_stock.dividends = pd.Series({dividend_date: 1.0}) # $1/share dividend
        # 150 shares (at $100) * $1 = $150 cash.
        
        # Re-run with dividend
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-02-28',
            amount=0,
            initial_amount=15000, # Invest $15k ($10k cash + $5k margin)
            reinvest=False, # Cash accumulation
            account_balance=10000,
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        # Check cash balance before interest (approx)
        # Should have received dividend ~$150
        
        # THEN interest (~$23) should be paid fully from the dividend cash
        # And borrowed amount should remain at initial $5000 (not capitalized)
        total_borrowed = result['summary']['total_borrowed']
        self.assertAlmostEqual(total_borrowed, 5000, delta=1.0, 
                             msg="Interest should be paid from dividend cash, not capitalized")

    def test_scenario_margin_call_liquidation(self):
        """
        Scenario: Market crash triggers margin call and forced liquidation.
        """
        # GIVEN a fully leveraged portfolio
        # $10k Cash, 2x Margin -> $20k Portfolio ($10k Debt)
        initial_cash = 10000
        
        # Setup Crash:
        # Day 1: $100 (Buy)
        # Day 2: $100 (Stable)
        # Day 3: $40 (Crash -60%) -> Equity drops significantly
        # Equity = $20k value becomes $8k. Debt = $10k. Equity = -$2k.
        # Wait, $40 is too low, let's go to $60.
        # Value = $12k. Debt = $10k. Equity = $2k. Ratio = 2/12 = 16% (<25%). Margin Call!
        prices = [100, 100, 60, 60, 60]
        self.setup_mock_data(prices)

        # WHEN the price crashes
        result = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-05',
            amount=0,
            initial_amount=20000,
            reinvest=False,
            account_balance=initial_cash,
            margin_ratio=2.0,
            maintenance_margin=0.25
        )

        # THEN a margin call should be recorded
        self.assertGreater(result['summary']['margin_calls'], 0, "Margin call should trigger")

        # AND shares should be sold (Forced Liquidation)
        # Initial shares: 200 ($20k / $100)
        # Final shares should be less
        total_shares = result['summary']['total_shares']
        self.assertLess(total_shares, 200, "Shares should be liquidated")

        # AND debt should be reduced
        # Initial debt $10k. Liquidation proceeds pay down debt.
        total_borrowed = result['summary']['total_borrowed']
        self.assertLess(total_borrowed, 10000, "Debt should be paid down by liquidation")

    def test_scenario_no_margin_comparison(self):
        """
        Scenario: System runs a parallel no-margin simulation.
        """
        # GIVEN a user selects margin > 1.0
        margin_ratio = 2.0
        self.setup_mock_data([100, 110, 120]) # Bull market

        # WHEN the simulation runs via the API endpoint (simulated by calling core twice)
        # Note: calculate_dca_core doesn't do the comparison, the route does.
        # But we can verify that running with 1.0 produces different results.
        
        result_margin = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=0,
            initial_amount=20000, # $10k cash + $10k margin
            reinvest=False,
            account_balance=10000,
            margin_ratio=2.0,
            maintenance_margin=0.25
        )
        
        result_no_margin = calculate_dca_core(
            ticker='TEST',
            start_date='2024-01-01',
            end_date='2024-01-03',
            amount=0,
            initial_amount=20000, # Try to invest $20k with $10k cash -> Capped at $10k
            reinvest=False,
            account_balance=10000,
            margin_ratio=1.0,
            maintenance_margin=0.25
        )

        # THEN the margin result should have higher value (in bull market)
        self.assertGreater(result_margin['summary']['current_value'], 
                          result_no_margin['summary']['current_value'])
        
        # AND the no-margin result should have capped investment at cash balance
        self.assertEqual(result_no_margin['summary']['total_invested'], 10000)

if __name__ == '__main__':
    unittest.main()
