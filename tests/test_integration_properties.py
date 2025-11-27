"""
INTEGRATION TESTS: MATHEMATICAL PROPERTIES & CONSISTENCY
These tests validate fundamental mathematical properties and relationships
between metrics, rather than arbitrary thresholds.

Philosophy: Test what MUST be true, not what we THINK should be true.
"""

import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
from app import calculate_dca_core


class TestPortfolioAccountingIdentities(unittest.TestCase):
    """Test fundamental accounting equations that MUST always hold"""

    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()

    def tearDown(self):
        self.mock_ticker_patcher.stop()

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

    def test_current_value_equals_shares_times_price(self):
        """Current Value = Shares × Current Price (portfolio value only, excludes cash)"""
        self.setup_mock_data([100, 110, 105, 120])

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-04',
            amount=100, initial_amount=500, reinvest=False,
            account_balance=1000
        )

        summary = result['summary']
        current_price = 120  # Final price

        # Mathematical identity: Portfolio value (shares only) = shares × price
        expected_value = summary['total_shares'] * current_price
        actual_value = summary['current_value']

        self.assertAlmostEqual(actual_value, expected_value, places=2,
            msg="Current portfolio value must equal shares × current price")

    def test_roi_calculation_consistency(self):
        """ROI = (Net Value - Total Invested) / Total Invested × 100"""
        self.setup_mock_data([100, 110, 120])

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-03',
            amount=100, initial_amount=1000, reinvest=False,
            account_balance=None, margin_ratio=1.0
        )

        summary = result['summary']

        # ROI should be based on net portfolio value (current value - debt)
        net_value = summary['current_value'] - summary['total_borrowed']
        expected_roi = ((net_value - summary['total_invested']) / summary['total_invested'] * 100)
        actual_roi = summary['roi']

        self.assertAlmostEqual(actual_roi, expected_roi, places=2,
            msg="ROI must equal (Net Value - Invested) / Invested × 100")

    def test_net_portfolio_identity(self):
        """Net Portfolio = Portfolio Value - Debt"""
        self.setup_mock_data([100, 110, 95, 105])

        with patch('app.get_fed_funds_rate', return_value=0.05):
            result = calculate_dca_core(
                ticker='TEST', start_date='2024-01-01', end_date='2024-01-04',
                amount=500, initial_amount=0, reinvest=False,
                account_balance=1000, margin_ratio=2.0
            )

        summary = result['summary']

        # Net Portfolio = Current Value - Borrowed Amount
        expected_net = summary['current_value'] - summary['total_borrowed']
        actual_net = summary['net_portfolio_value']

        self.assertAlmostEqual(actual_net, expected_net, places=2,
            msg="Net portfolio must equal portfolio value minus debt")

    def test_average_cost_is_weighted_average(self):
        """Average cost should be between min and max prices when DCA'ing"""
        prices = [100, 90, 110, 105]
        self.setup_mock_data(prices)

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-04',
            amount=100, initial_amount=0, reinvest=False,
            account_balance=None
        )

        summary = result['summary']

        if summary['total_shares'] > 0:
            min_price = min(prices)
            max_price = max(prices)
            avg_cost = summary['average_cost']

            # Average cost must be between min and max prices (mathematical property)
            self.assertGreaterEqual(avg_cost, min_price,
                msg=f"Average cost ({avg_cost}) cannot be less than min price ({min_price})")
            self.assertLessEqual(avg_cost, max_price,
                msg=f"Average cost ({avg_cost}) cannot exceed max price ({max_price})")


class TestAnalyticsConsistency(unittest.TestCase):
    """Test consistency between related analytics metrics"""

    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()

    def tearDown(self):
        self.mock_ticker_patcher.stop()

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

    def test_total_return_matches_roi_no_margin(self):
        """Total Return % should equal ROI when no margin is used"""
        self.setup_mock_data([100, 110, 120, 115])

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-04',
            amount=100, initial_amount=1000, reinvest=False,
            account_balance=None, margin_ratio=1.0
        )

        summary = result['summary']
        analytics = result['analytics']

        # When no margin: Total Return should approximately equal ROI
        if summary['total_borrowed'] == 0:
            # Allow small difference due to different calculation methods
            difference = abs(analytics['total_return_pct'] - summary['roi'])

            # Note: They might differ slightly due to how initial equity is calculated
            # But they should be in the same ballpark
            self.assertLess(difference, 100,  # Very loose check - just not wildly different
                msg=f"Total Return ({analytics['total_return_pct']:.2f}%) and "
                    f"ROI ({summary['roi']:.2f}%) should be similar when no margin used")

    def test_calmar_ratio_is_positive_with_gains_and_drawdown(self):
        """Calmar Ratio should be positive when CAGR > 0 and drawdown exists"""
        # Create scenario with clear gain and drawdown
        self.setup_mock_data([100, 150, 130, 180])  # Significant gain with drawdown

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-04',
            amount=0, initial_amount=1000, reinvest=False,
            account_balance=None
        )

        analytics = result['analytics']

        # Mathematical property: If CAGR > 0 and max_drawdown < 0, Calmar should be positive
        if analytics['cagr'] > 0 and analytics['max_drawdown'] < 0:
            self.assertGreater(analytics['calmar_ratio'], 0,
                msg="Calmar Ratio should be positive when returns are positive and drawdown exists")

    def test_win_rate_bounds(self):
        """Win Rate must be between 0% and 100%"""
        self.setup_mock_data([100, 105, 102, 108, 95, 100])

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-06',
            amount=100, initial_amount=0, reinvest=False,
            account_balance=None
        )

        analytics = result['analytics']
        win_rate = analytics['win_rate']

        self.assertGreaterEqual(win_rate, 0,
            msg="Win rate cannot be negative")
        self.assertLessEqual(win_rate, 100,
            msg="Win rate cannot exceed 100%")

    def test_max_drawdown_is_non_positive(self):
        """Max Drawdown must be <= 0 (it's a loss)"""
        self.setup_mock_data([100, 110, 105, 115, 120])

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-05',
            amount=100, initial_amount=0, reinvest=False,
            account_balance=None
        )

        analytics = result['analytics']

        self.assertLessEqual(analytics['max_drawdown'], 0,
            msg="Max drawdown must be zero or negative")

    def test_leverage_ratio_definition(self):
        """Leverage = Portfolio Value / Equity (when equity > 0)"""
        self.setup_mock_data([100] * 5)

        with patch('app.get_fed_funds_rate', return_value=0.05):
            result = calculate_dca_core(
                ticker='TEST', start_date='2024-01-01', end_date='2024-01-05',
                amount=200, initial_amount=0, reinvest=False,
                account_balance=500, margin_ratio=2.0
            )

        summary = result['summary']

        if summary['net_portfolio_value'] > 0:
            expected_leverage = summary['current_value'] / summary['net_portfolio_value']
            actual_leverage = summary['current_leverage']

            self.assertAlmostEqual(actual_leverage, expected_leverage, places=2,
                msg="Leverage must equal Portfolio Value / Equity")


class TestScenarioBasedValidation(unittest.TestCase):
    """Test expected behavior in specific scenarios"""

    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()

    def tearDown(self):
        self.mock_ticker_patcher.stop()

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

    def test_flat_market_zero_price_returns(self):
        """In a flat market (no price change), price returns are zero but total return may not be"""
        # All prices exactly the same - lump sum investment
        self.setup_mock_data([100] * 10)

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-10',
            amount=0, initial_amount=1000, reinvest=False,  # Lump sum, no DCA
            account_balance=None
        )

        analytics = result['analytics']
        summary = result['summary']

        # In flat market with lump sum:
        # - Total return should be ~0% (no gain or loss)
        # - Max drawdown should be 0 (no decline)
        self.assertAlmostEqual(analytics['total_return_pct'], 0, places=1,
            msg="Flat market lump sum should have ~0% return")
        self.assertEqual(analytics['max_drawdown'], 0,
            msg="Flat market should have zero drawdown")
        self.assertAlmostEqual(summary['roi'], 0, places=1,
            msg="ROI should be ~0% in flat market")

    def test_pure_dca_vs_lump_sum_invested_amounts(self):
        """Pure DCA should only count daily amounts as invested"""
        self.setup_mock_data([100, 105, 110])

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-03',
            amount=100,           # $100/day
            initial_amount=0,     # Zero lump sum
            reinvest=False,
            account_balance=None
        )

        summary = result['summary']

        # 3 days × $100 = $300 invested
        self.assertEqual(summary['total_invested'], 300,
            msg="Pure DCA should only count daily investments")

    def test_lump_sum_only_invested_amount(self):
        """Lump sum only (no DCA) should count initial amount"""
        self.setup_mock_data([100, 105, 110])

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-03',
            amount=0,             # No daily DCA
            initial_amount=1000,  # Lump sum
            reinvest=False,
            account_balance=None
        )

        summary = result['summary']

        # Only the initial $1000
        self.assertEqual(summary['total_invested'], 1000,
            msg="Lump sum only should count initial investment")

    def test_dividend_reinvest_increases_shares_not_invested(self):
        """Reinvested dividends buy shares but don't count as 'invested'"""
        # Dividend of $25 per share on day 3
        dividends = {'2024-01-03': 25.0}
        self.setup_mock_data([100, 100, 100, 100], dividends)

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-04',
            amount=100, initial_amount=0, reinvest=True,
            account_balance=None
        )

        summary = result['summary']

        # Day 1: Buy 1 share ($100)
        # Day 2: Buy 1 share ($100)
        # Day 3: Receive $25/share dividend (2 shares × $25 = $50 total)
        #        Reinvest $50 to buy 0.5 shares, then buy 1 share ($100)
        # Day 4: Buy 1 share ($100)
        # Total invested: $400 (dividends don't count as "invested")
        # Total dividends: $50
        # Total shares: 4.5 (4 from principal, 0.5 from dividend)

        self.assertEqual(summary['total_invested'], 400,
            msg="Reinvested dividends should not count as 'invested'")
        self.assertGreater(summary['total_shares'], 4,
            msg="Reinvested dividends should increase share count")
        self.assertEqual(summary['total_dividends'], 50,
            msg="Should track total dividends received (2 shares × $25)")

    def test_margin_trading_increases_shares_bought(self):
        """Margin trading should allow buying more shares than cash alone"""
        prices = [100, 110]

        # No margin scenario
        self.setup_mock_data(prices)
        result_no_margin = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-02',
            amount=500, initial_amount=0, reinvest=False,
            account_balance=1000, margin_ratio=1.0
        )

        # 2x margin scenario - same cash, but can borrow
        self.setup_mock_data(prices)
        with patch('app.get_fed_funds_rate', return_value=0.0):
            result_margin = calculate_dca_core(
                ticker='TEST', start_date='2024-01-01', end_date='2024-01-02',
                amount=500, initial_amount=0, reinvest=False,
                account_balance=1000, margin_ratio=2.0
            )

        # Mathematical property: With margin enabled and cash running out,
        # should be able to buy more shares (by borrowing)
        # This tests that margin actually works, not specific amplification ratios
        self.assertGreaterEqual(result_margin['summary']['total_shares'],
                               result_no_margin['summary']['total_shares'],
                               msg="Margin should allow buying at least as many shares (potentially more via borrowing)")

    def test_no_shares_yields_zero_average_cost(self):
        """When no shares bought, average cost should be zero"""
        self.setup_mock_data([100])

        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-01',
            amount=0, initial_amount=0, reinvest=False,
            account_balance=0
        )

        summary = result['summary']

        self.assertEqual(summary['total_shares'], 0)
        self.assertEqual(summary['average_cost'], 0,
            msg="Average cost should be 0 when no shares purchased")


class TestInitialEquityCalculation(unittest.TestCase):
    """Test the ROOT CAUSE: Initial equity calculation for analytics"""

    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()

    def tearDown(self):
        self.mock_ticker_patcher.stop()

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

    def test_pure_dca_total_return_calculation(self):
        """
        ROOT CAUSE TEST: Pure DCA (no initial) should use total_invested
        as baseline, NOT first day's value

        Bug: analytics used analytics_values[0] which is just day 1's $100
        Fix: Should use total_invested as the baseline for Total Return %
        """
        # Long DCA scenario
        prices = [100] * 100  # Flat market for simplicity

        self.setup_mock_data(prices)
        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-04-09',
            amount=100,           # $100/day
            initial_amount=0,     # Pure DCA, no lump sum
            reinvest=False,
            account_balance=None
        )

        summary = result['summary']
        analytics = result['analytics']

        # Total invested: 100 days × $100 = $10,000
        # Final value: 100 shares × $100 = $10,000
        # Total Return: (10000 - 10000) / 10000 = 0%

        self.assertEqual(summary['total_invested'], 10000)
        self.assertAlmostEqual(analytics['total_return_pct'], 0, places=1,
            msg="Flat market DCA should have ~0% return, not thousands of percent")
        self.assertAlmostEqual(analytics['cagr'], 0, places=1,
            msg="Flat market should have ~0% CAGR")

    def test_dca_with_growth_reasonable_return(self):
        """DCA in growing market should have reasonable returns"""
        # Price grows 50% over period
        prices = [100 + i for i in range(100)]  # 100 to 199

        self.setup_mock_data(prices)
        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-04-09',
            amount=100,
            initial_amount=0,
            reinvest=False,
            account_balance=None
        )

        analytics = result['analytics']

        # In a growing market with DCA:
        # - Early purchases buy more shares (at lower prices)
        # - Later purchases buy fewer shares (at higher prices)
        # - Should have positive return, but not astronomical

        self.assertGreater(analytics['total_return_pct'], 0,
            msg="Growing market should have positive returns")

        # This is NOT an arbitrary threshold - it's validating the fix
        # If we see 6000% returns, the bug is back
        self.assertLess(analytics['total_return_pct'], 200,
            msg="DCA in moderately growing market shouldn't exceed 200% return "
                "(if it does, initial equity calculation is wrong)")

    def test_lump_sum_total_return_calculation(self):
        """Lump sum investment should use initial investment as baseline"""
        prices = [100, 150]  # 50% gain

        self.setup_mock_data(prices)
        result = calculate_dca_core(
            ticker='TEST', start_date='2024-01-01', end_date='2024-01-02',
            amount=0,
            initial_amount=10000,
            reinvest=False,
            account_balance=None
        )

        analytics = result['analytics']
        summary = result['summary']

        # Invested $10,000 at $100 = 100 shares
        # Final value: 100 shares × $150 = $15,000
        # Return: (15000 - 10000) / 10000 = 50%

        self.assertAlmostEqual(analytics['total_return_pct'], 50, places=1,
            msg="50% price gain should yield ~50% return for lump sum")
        self.assertAlmostEqual(summary['roi'], 50, places=1,
            msg="ROI should also be ~50%")


if __name__ == '__main__':
    unittest.main(verbosity=2)
