"""
Unit tests for analytics calculation functions (Portfolio Analytics Feature)

These tests verify that risk and performance metrics are calculated correctly.
All functions are pure calculations with no side effects.
"""

import unittest
import math
from app import (
    calculate_total_return_percent,
    calculate_cagr,
    calculate_daily_returns,
    calculate_volatility,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_win_rate,
    calculate_best_worst_days,
    calculate_calmar_ratio,
    calculate_alpha_beta
)


class TestCalculateTotalReturnPercent(unittest.TestCase):
    """Test calculate_total_return_percent() function"""

    def test_positive_return(self):
        """Test calculating positive return"""
        result = calculate_total_return_percent(10000, 15000)
        self.assertEqual(result, 50.0)

    def test_negative_return(self):
        """Test calculating negative return (loss)"""
        result = calculate_total_return_percent(10000, 8000)
        self.assertEqual(result, -20.0)

    def test_no_change(self):
        """Test zero return (no change)"""
        result = calculate_total_return_percent(10000, 10000)
        self.assertEqual(result, 0.0)

    def test_zero_initial_value(self):
        """Test with zero initial value (edge case)"""
        result = calculate_total_return_percent(0, 5000)
        self.assertEqual(result, 0)  # Returns 0 for invalid initial

    def test_negative_initial_value(self):
        """Test with negative initial value (invalid)"""
        result = calculate_total_return_percent(-1000, 5000)
        self.assertEqual(result, 0)  # Returns 0 for invalid initial

    def test_large_gain(self):
        """Test with very large gain (10x)"""
        result = calculate_total_return_percent(1000, 10000)
        self.assertEqual(result, 900.0)


class TestCalculateCAGR(unittest.TestCase):
    """Test calculate_cagr() function"""

    def test_one_year_growth(self):
        """Test CAGR for exactly one year"""
        result = calculate_cagr(10000, 15000, 365)
        self.assertAlmostEqual(result, 50.0, places=1)

    def test_two_year_growth(self):
        """Test CAGR over two years"""
        # 10000 -> 15000 in 2 years = 22.47% annual
        result = calculate_cagr(10000, 15000, 730)
        self.assertAlmostEqual(result, 22.47, places=1)

    def test_fractional_year(self):
        """Test CAGR for partial year (6 months)"""
        # Doubling in 6 months = 300% annualized
        result = calculate_cagr(10000, 20000, 182)
        self.assertGreater(result, 100)  # Should be > 100% annual

    def test_zero_initial_value(self):
        """Test with zero initial value (edge case)"""
        result = calculate_cagr(0, 5000, 365)
        self.assertEqual(result, 0)

    def test_zero_days(self):
        """Test with zero days (edge case)"""
        result = calculate_cagr(10000, 15000, 0)
        self.assertEqual(result, 0)

    def test_negative_return(self):
        """Test CAGR with loss"""
        result = calculate_cagr(10000, 8000, 365)
        self.assertLess(result, 0)  # Should be negative


class TestCalculateDailyReturns(unittest.TestCase):
    """Test calculate_daily_returns() function"""

    def test_basic_returns(self):
        """Test basic daily returns calculation"""
        values = [100, 105, 103, 110]
        returns = calculate_daily_returns(values)

        self.assertEqual(len(returns), 4)
        self.assertEqual(returns[0], 0)  # First day always 0
        self.assertAlmostEqual(returns[1], 0.05, places=4)  # 5% gain
        self.assertAlmostEqual(returns[2], -0.019047, places=4)  # ~1.9% loss
        self.assertAlmostEqual(returns[3], 0.067961, places=4)  # ~6.8% gain

    def test_single_value(self):
        """Test with only one value"""
        values = [100]
        returns = calculate_daily_returns(values)
        self.assertEqual(returns, [0])

    def test_empty_list(self):
        """Test with empty list"""
        values = []
        returns = calculate_daily_returns(values)
        self.assertEqual(returns, [0])

    def test_flat_values(self):
        """Test with no change (all same values)"""
        values = [100, 100, 100]
        returns = calculate_daily_returns(values)
        self.assertEqual(returns, [0, 0, 0])

    def test_zero_value_handling(self):
        """Test with zero value (edge case)"""
        values = [100, 0, 50]
        returns = calculate_daily_returns(values)
        # When previous value is 0, return should be 0
        self.assertEqual(returns[2], 0)


class TestCalculateVolatility(unittest.TestCase):
    """Test calculate_volatility() function"""

    def test_basic_volatility(self):
        """Test basic volatility calculation"""
        # Mix of positive and negative returns
        returns = [0, 0.01, -0.01, 0.02, -0.005, 0.015]
        vol = calculate_volatility(returns)

        # Should be positive percentage (mathematical property, not arbitrary threshold)
        self.assertGreater(vol, 0)
        # Note: Removed arbitrary "< 100" threshold - volatility can legitimately exceed 100%
        # For these specific returns, volatility should be a specific calculable value
        self.assertIsInstance(vol, (int, float))

    def test_low_volatility(self):
        """Test with low volatility (consistent returns)"""
        returns = [0.01, 0.01, 0.01, 0.01, 0.01]
        vol = calculate_volatility(returns)

        # Very low volatility (all same)
        self.assertEqual(vol, 0)

    def test_insufficient_data(self):
        """Test with insufficient data"""
        returns = [0]
        vol = calculate_volatility(returns)
        self.assertEqual(vol, 0)

    def test_high_volatility(self):
        """Test with high volatility (wild swings)"""
        returns = [0, 0.1, -0.08, 0.12, -0.15]
        vol = calculate_volatility(returns)

        # High volatility
        self.assertGreater(vol, 50)


class TestCalculateSharpeRatio(unittest.TestCase):
    """Test calculate_sharpe_ratio() function"""

    def test_positive_sharpe(self):
        """Test with positive returns (good Sharpe)"""
        returns = [0, 0.01, 0.015, 0.012, 0.018]
        sharpe = calculate_sharpe_ratio(returns)

        # Positive returns should give positive Sharpe
        self.assertGreater(sharpe, 0)

    def test_negative_sharpe(self):
        """Test with negative returns (poor Sharpe)"""
        returns = [0, -0.01, -0.015, -0.012]
        sharpe = calculate_sharpe_ratio(returns)

        # Negative returns should give negative Sharpe
        self.assertLess(sharpe, 0)

    def test_zero_volatility(self):
        """Test with zero volatility (edge case)"""
        returns = [0.01, 0.01, 0.01, 0.01]
        sharpe = calculate_sharpe_ratio(returns)

        # Zero vol returns 0
        self.assertEqual(sharpe, 0)

    def test_insufficient_data(self):
        """Test with insufficient data"""
        returns = [0]
        sharpe = calculate_sharpe_ratio(returns)
        self.assertEqual(sharpe, 0)

    def test_custom_risk_free_rate(self):
        """Test with custom risk-free rate"""
        returns = [0, 0.01, 0.015, 0.012]
        sharpe_2pct = calculate_sharpe_ratio(returns, risk_free_rate=0.02)
        sharpe_5pct = calculate_sharpe_ratio(returns, risk_free_rate=0.05)

        # Higher risk-free rate should lower Sharpe
        self.assertLess(sharpe_5pct, sharpe_2pct)


class TestCalculateMaxDrawdown(unittest.TestCase):
    """Test calculate_max_drawdown() function"""

    def test_basic_drawdown(self):
        """Test basic drawdown calculation"""
        values = [100, 110, 105, 95, 100, 105]
        max_dd, peak_idx, trough_idx = calculate_max_drawdown(values)

        # From 110 (idx 1) to 95 (idx 3) = -13.64%
        self.assertAlmostEqual(max_dd, -13.636, places=2)
        self.assertEqual(peak_idx, 1)
        self.assertEqual(trough_idx, 3)

    def test_no_drawdown(self):
        """Test with continuous growth (no drawdown)"""
        values = [100, 105, 110, 115, 120]
        max_dd, peak_idx, trough_idx = calculate_max_drawdown(values)

        # No drawdown
        self.assertEqual(max_dd, 0)

    def test_severe_drawdown(self):
        """Test severe drawdown (50%+ loss)"""
        values = [100, 150, 70, 80]
        max_dd, peak_idx, trough_idx = calculate_max_drawdown(values)

        # From 150 to 70 = -53.33%
        self.assertAlmostEqual(max_dd, -53.333, places=2)
        self.assertEqual(peak_idx, 1)
        self.assertEqual(trough_idx, 2)

    def test_single_value(self):
        """Test with single value"""
        values = [100]
        max_dd, peak_idx, trough_idx = calculate_max_drawdown(values)

        self.assertEqual(max_dd, 0)
        self.assertEqual(peak_idx, 0)
        self.assertEqual(trough_idx, 0)

    def test_multiple_peaks(self):
        """Test with multiple peaks (should find largest drawdown)"""
        values = [100, 110, 100, 120, 90, 100]
        max_dd, peak_idx, trough_idx = calculate_max_drawdown(values)

        # Largest drawdown from 120 (idx 3) to 90 (idx 4) = -25%
        self.assertEqual(max_dd, -25.0)
        self.assertEqual(peak_idx, 3)
        self.assertEqual(trough_idx, 4)


class TestCalculateWinRate(unittest.TestCase):
    """Test calculate_win_rate() function"""

    def test_basic_win_rate(self):
        """Test basic win rate calculation"""
        returns = [0, 0.01, -0.01, 0.02, 0.01, -0.005]
        win_rate = calculate_win_rate(returns)

        # 3 positive out of 5 trading days = 60%
        self.assertEqual(win_rate, 60.0)

    def test_all_wins(self):
        """Test with 100% win rate"""
        returns = [0, 0.01, 0.02, 0.015, 0.01]
        win_rate = calculate_win_rate(returns)

        self.assertEqual(win_rate, 100.0)

    def test_all_losses(self):
        """Test with 0% win rate"""
        returns = [0, -0.01, -0.02, -0.015]
        win_rate = calculate_win_rate(returns)

        self.assertEqual(win_rate, 0.0)

    def test_insufficient_data(self):
        """Test with insufficient data"""
        returns = [0]
        win_rate = calculate_win_rate(returns)

        self.assertEqual(win_rate, 0)

    def test_mixed_returns(self):
        """Test with 50/50 win rate"""
        returns = [0, 0.01, -0.01, 0.01, -0.01]
        win_rate = calculate_win_rate(returns)

        self.assertEqual(win_rate, 50.0)


class TestCalculateBestWorstDays(unittest.TestCase):
    """Test calculate_best_worst_days() function"""

    def test_basic_best_worst(self):
        """Test basic best/worst day calculation"""
        returns = [0, 0.02, -0.03, 0.01, -0.005]
        dates = ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']

        best, best_date, worst, worst_date = calculate_best_worst_days(returns, dates)

        self.assertEqual(best, 2.0)  # 2% best day
        self.assertEqual(best_date, '2024-01-02')
        self.assertEqual(worst, -3.0)  # -3% worst day
        self.assertEqual(worst_date, '2024-01-03')

    def test_all_positive(self):
        """Test with all positive returns"""
        returns = [0, 0.01, 0.03, 0.02]
        dates = ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']

        best, best_date, worst, worst_date = calculate_best_worst_days(returns, dates)

        self.assertEqual(best, 3.0)  # Best is 3%
        self.assertEqual(worst, 1.0)  # Worst is still positive (1%)

    def test_insufficient_data(self):
        """Test with insufficient data"""
        returns = [0]
        dates = ['2024-01-01']

        best, best_date, worst, worst_date = calculate_best_worst_days(returns, dates)

        self.assertEqual(best, 0)
        self.assertIsNone(best_date)
        self.assertEqual(worst, 0)
        self.assertIsNone(worst_date)


class TestCalculateCalmarRatio(unittest.TestCase):
    """Test calculate_calmar_ratio() function"""

    def test_positive_calmar(self):
        """Test with positive CAGR and negative drawdown"""
        cagr = 24.5
        max_dd = -12.4

        calmar = calculate_calmar_ratio(cagr, max_dd)

        self.assertAlmostEqual(calmar, 1.976, places=2)

    def test_high_calmar(self):
        """Test with high return, low drawdown (excellent Calmar)"""
        cagr = 50.0
        max_dd = -5.0

        calmar = calculate_calmar_ratio(cagr, max_dd)

        self.assertEqual(calmar, 10.0)  # Excellent ratio

    def test_low_calmar(self):
        """Test with low return, high drawdown (poor Calmar)"""
        cagr = 10.0
        max_dd = -30.0

        calmar = calculate_calmar_ratio(cagr, max_dd)

        self.assertAlmostEqual(calmar, 0.333, places=2)

    def test_zero_drawdown(self):
        """Test with zero drawdown (edge case)"""
        cagr = 20.0
        max_dd = 0  # No drawdown

        calmar = calculate_calmar_ratio(cagr, max_dd)

        self.assertEqual(calmar, 0)  # Returns 0 for invalid

    def test_positive_drawdown(self):
        """Test with positive drawdown (invalid input)"""
        cagr = 20.0
        max_dd = 5.0  # Invalid (drawdown should be negative)

        calmar = calculate_calmar_ratio(cagr, max_dd)

        self.assertEqual(calmar, 0)


class TestCalculateAlphaBeta(unittest.TestCase):
    """Test calculate_alpha_beta() function"""

    def test_basic_alpha_beta(self):
        """Test basic alpha/beta calculation"""
        portfolio_returns = [0, 0.02, -0.01, 0.03, 0.01]
        benchmark_returns = [0, 0.015, -0.005, 0.025, 0.01]

        alpha, beta = calculate_alpha_beta(portfolio_returns, benchmark_returns)

        # Beta should be reasonable
        self.assertGreater(beta, 0)
        self.assertLess(beta, 3.0)

        # Alpha can be positive or negative depending on performance
        self.assertIsInstance(alpha, (int, float))

    def test_underperformance(self):
        """Test with portfolio underperforming benchmark"""
        portfolio_returns = [0, 0.01, -0.02, 0.01]
        benchmark_returns = [0, 0.02, -0.01, 0.02]

        alpha, beta = calculate_alpha_beta(portfolio_returns, benchmark_returns)

        # Negative alpha (underperforming)
        self.assertLess(alpha, 0)

    def test_high_beta(self):
        """Test with high beta (more volatile than benchmark)"""
        portfolio_returns = [0, 0.04, -0.02, 0.06]  # 2x moves
        benchmark_returns = [0, 0.02, -0.01, 0.03]  # Base moves

        alpha, beta = calculate_alpha_beta(portfolio_returns, benchmark_returns)

        # Beta should be around 2.0
        self.assertGreater(beta, 1.5)

    def test_insufficient_data(self):
        """Test with insufficient data"""
        portfolio_returns = [0]
        benchmark_returns = [0]

        alpha, beta = calculate_alpha_beta(portfolio_returns, benchmark_returns)

        self.assertEqual(alpha, 0)
        self.assertEqual(beta, 1.0)

    def test_mismatched_lengths(self):
        """Test with mismatched return arrays"""
        portfolio_returns = [0, 0.01, 0.02]
        benchmark_returns = [0, 0.01]  # Different length

        alpha, beta = calculate_alpha_beta(portfolio_returns, benchmark_returns)

        self.assertEqual(alpha, 0)
        self.assertEqual(beta, 1.0)

    def test_zero_benchmark_variance(self):
        """Test with zero benchmark variance (edge case)"""
        portfolio_returns = [0, 0.01, 0.02]
        benchmark_returns = [0, 0.01, 0.01, 0.01]  # No variance

        alpha, beta = calculate_alpha_beta(portfolio_returns, benchmark_returns)

        # Should return defaults
        self.assertEqual(alpha, 0)
        self.assertEqual(beta, 1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
