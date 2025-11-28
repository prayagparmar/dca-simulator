"""
Test how max drawdown is calculated when equity goes negative or to zero.

User reported: -100% max drawdown but portfolio still alive.
This tests if negative equity or zero equity is causing -100% drawdown calculation.
"""

import unittest
from app import calculate_max_drawdown, calculate_daily_returns


class TestNegativeEquityDrawdown(unittest.TestCase):
    """Test max drawdown calculation with negative/zero equity"""

    def test_max_drawdown_with_zero_equity(self):
        """
        Test max drawdown when equity hits exactly $0

        Scenario: Net portfolio values (equity) go from $100 to $0
        Expected: -100% drawdown
        """
        equity_values = [100, 80, 50, 20, 0, 10, 30]  # Hits zero, then recovers

        max_dd, peak_idx, trough_idx = calculate_max_drawdown(equity_values)

        print(f"\nEquity values: {equity_values}")
        print(f"Max drawdown: {max_dd:.2%}")
        print(f"Peak index: {peak_idx}, Trough index: {trough_idx}")
        print(f"Peak value: ${equity_values[peak_idx]}, Trough value: ${equity_values[trough_idx]}")

        # If equity hits $0, drawdown should be -100%
        # Function returns percentage format: -100.0 (not decimal -1.0)
        self.assertAlmostEqual(max_dd, -100.0, places=2,
            msg="Equity hitting $0 should show -100% drawdown")

    def test_max_drawdown_with_negative_equity(self):
        """
        Test max drawdown when equity goes NEGATIVE

        Scenario: Net portfolio = Portfolio - Debt goes negative
        Example: $40K portfolio - $50K debt = -$10K equity
        """
        equity_values = [100, 80, 50, 20, -10, -5, 10]  # Goes negative!

        max_dd, peak_idx, trough_idx = calculate_max_drawdown(equity_values)

        print(f"\nEquity values (NEGATIVE!): {equity_values}")
        print(f"Max drawdown: {max_dd:.2%}")
        print(f"Peak index: {peak_idx}, Trough index: {trough_idx}")
        print(f"Peak value: ${equity_values[peak_idx]}, Trough value: ${equity_values[trough_idx]}")

        # Negative equity means MORE than -100% drawdown!
        # From $100 to -$10 is a 110% decline!
        # Function returns percentage format: -110.0 (not decimal -1.1)
        expected_dd = (-10 - 100) / 100 * 100  # -110% in percentage format
        self.assertLess(max_dd, -100.0,
            msg="Negative equity should show >100% drawdown")

    def test_daily_return_from_zero_equity(self):
        """
        Test daily return calculation when equity goes from $0 to positive

        This would cause division by zero!
        """
        equity_values = [100, 50, 0, 50, 100]  # Zero then recovers

        daily_returns = calculate_daily_returns(equity_values)

        print(f"\nEquity values with zero: {equity_values}")
        print(f"Daily returns: {daily_returns}")

        # What happens at the return from $0 to $50?
        # (50 - 0) / 0 = infinity!
        # Code should handle this edge case

    def test_worst_day_calculation(self):
        """
        Test if worst day can show -100%

        A -100% daily return means equity went from X to $0 in one day
        """
        equity_values = [100, 100, 0, 50]  # Instant crash to zero on day 2

        daily_returns = calculate_daily_returns(equity_values)

        print(f"\nEquity with instant crash: {equity_values}")
        print(f"Daily returns: {daily_returns}")

        worst_return = min(daily_returns)
        print(f"Worst day return: {worst_return:.2%}")

        # If equity goes from $100 to $0, return = -100%
        # Note: daily_returns uses decimal format (-1.0), not percentage
        # This is different from max_drawdown which uses percentage format
        self.assertAlmostEqual(worst_return, -1.0, places=2,
            msg="Crash to $0 should show -100% return")


if __name__ == '__main__':
    unittest.main(verbosity=2)
