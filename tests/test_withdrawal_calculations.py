"""
Test suite for withdrawal pure calculation functions.

Tests the calculate_shares_to_sell_for_withdrawal() function which handles
the math for determining how many shares to sell to satisfy withdrawals
while prioritizing margin debt repayment.
"""

import unittest
import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import calculate_shares_to_sell_for_withdrawal


class TestWithdrawalCalculations(unittest.TestCase):
    """Test pure calculation functions for withdrawal feature."""

    def test_withdrawal_with_sufficient_cash_no_debt(self):
        """Test withdrawal when cash is sufficient and no debt exists."""
        withdrawal_amount = 5000
        margin_debt = 0
        cash_balance = 10000
        current_price = 100

        shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
            withdrawal_amount, margin_debt, cash_balance, current_price
        )

        self.assertEqual(shares_to_sell, 0)  # No shares needed
        self.assertEqual(debt_repayment, 0)  # No debt to repay
        self.assertEqual(actual_withdrawal, 5000)  # Full withdrawal

    def test_withdrawal_with_insufficient_cash_no_debt(self):
        """Test withdrawal when cash is insufficient but no debt exists."""
        withdrawal_amount = 5000
        margin_debt = 0
        cash_balance = 2000
        current_price = 100

        shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
            withdrawal_amount, margin_debt, cash_balance, current_price
        )

        # Need to sell shares to get $3000 more
        self.assertEqual(shares_to_sell, 30)  # 3000 / 100
        self.assertEqual(debt_repayment, 0)  # No debt
        self.assertEqual(actual_withdrawal, 5000)  # Full withdrawal

    def test_withdrawal_with_debt_sufficient_cash(self):
        """Test withdrawal with debt - cash covers both debt and withdrawal."""
        withdrawal_amount = 5000
        margin_debt = 3000
        cash_balance = 10000
        current_price = 100

        shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
            withdrawal_amount, margin_debt, cash_balance, current_price
        )

        self.assertEqual(shares_to_sell, 0)  # No shares needed
        self.assertEqual(debt_repayment, 3000)  # Full debt repayment
        self.assertEqual(actual_withdrawal, 5000)  # Full withdrawal

    def test_withdrawal_with_debt_insufficient_cash(self):
        """Test withdrawal with debt - need to sell shares."""
        withdrawal_amount = 5000
        margin_debt = 3000
        cash_balance = 2000
        current_price = 100

        shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
            withdrawal_amount, margin_debt, cash_balance, current_price
        )

        # Total needed: 8000 (3000 debt + 5000 withdrawal)
        # Have: 2000
        # Need from sales: 6000
        self.assertEqual(shares_to_sell, 60)  # 6000 / 100
        self.assertEqual(debt_repayment, 3000)  # Full debt repayment
        self.assertEqual(actual_withdrawal, 5000)  # Full withdrawal

    def test_debt_priority_over_withdrawal(self):
        """Test that debt is repaid before withdrawal when funds limited."""
        withdrawal_amount = 5000
        margin_debt = 8000
        cash_balance = 1000
        current_price = 100

        shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
            withdrawal_amount, margin_debt, cash_balance, current_price
        )

        # Total needed: 13000 (8000 debt + 5000 withdrawal)
        # Have: 1000
        # Need from sales: 12000
        self.assertEqual(shares_to_sell, 120)  # 12000 / 100
        self.assertEqual(debt_repayment, 8000)  # Full debt repayment first
        self.assertEqual(actual_withdrawal, 5000)  # Then full withdrawal

    def test_zero_cash_balance(self):
        """Test with zero cash balance."""
        withdrawal_amount = 5000
        margin_debt = 0
        cash_balance = 0
        current_price = 100

        shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
            withdrawal_amount, margin_debt, cash_balance, current_price
        )

        self.assertEqual(shares_to_sell, 50)  # 5000 / 100
        self.assertEqual(debt_repayment, 0)
        self.assertEqual(actual_withdrawal, 5000)

    def test_negative_cash_balance(self):
        """Test with negative cash balance (treated as zero)."""
        withdrawal_amount = 5000
        margin_debt = 0
        cash_balance = -1000
        current_price = 100

        shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
            withdrawal_amount, margin_debt, cash_balance, current_price
        )

        # Negative cash treated as 0
        self.assertEqual(shares_to_sell, 50)  # 5000 / 100
        self.assertEqual(debt_repayment, 0)
        self.assertEqual(actual_withdrawal, 5000)

    def test_fractional_shares(self):
        """Test calculation with fractional shares."""
        withdrawal_amount = 5555.55
        margin_debt = 0
        cash_balance = 0
        current_price = 123.45

        shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
            withdrawal_amount, margin_debt, cash_balance, current_price
        )

        # Should calculate fractional shares
        expected_shares = 5555.55 / 123.45
        self.assertAlmostEqual(shares_to_sell, expected_shares, places=6)
        self.assertEqual(debt_repayment, 0)
        self.assertAlmostEqual(actual_withdrawal, 5555.55, places=2)

    def test_high_price_stock(self):
        """Test with expensive stock price."""
        withdrawal_amount = 5000
        margin_debt = 0
        cash_balance = 0
        current_price = 1000

        shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
            withdrawal_amount, margin_debt, cash_balance, current_price
        )

        self.assertEqual(shares_to_sell, 5)  # 5000 / 1000
        self.assertEqual(debt_repayment, 0)
        self.assertEqual(actual_withdrawal, 5000)


if __name__ == '__main__':
    unittest.main()
