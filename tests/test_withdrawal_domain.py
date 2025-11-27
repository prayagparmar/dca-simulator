"""
Test suite for withdrawal domain logic functions.

Tests the execute_monthly_withdrawal() function which orchestrates the
complete withdrawal process including selling shares, repaying debt,
and updating portfolio state.
"""

import unittest
import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import execute_monthly_withdrawal


class TestWithdrawalDomain(unittest.TestCase):
    """Test domain logic for withdrawal execution."""

    def test_basic_withdrawal_no_debt(self):
        """Test basic withdrawal with sufficient cash and no debt."""
        withdrawal_amount = 5000
        total_shares = 100
        price = 150
        borrowed_amount = 0
        current_balance = 10000
        total_cost_basis = 10000

        new_shares, new_balance, new_borrowed, new_cost_basis, shares_sold, debt_repaid, withdrawn = \
            execute_monthly_withdrawal(
                withdrawal_amount, total_shares, price, borrowed_amount,
                current_balance, total_cost_basis
            )

        self.assertEqual(new_shares, 100)  # No shares sold
        self.assertEqual(new_balance, 5000)  # 10000 - 5000
        self.assertEqual(new_borrowed, 0)
        self.assertEqual(new_cost_basis, 10000)  # Unchanged
        self.assertEqual(shares_sold, 0)
        self.assertEqual(debt_repaid, 0)
        self.assertEqual(withdrawn, 5000)

    def test_withdrawal_requires_selling_shares(self):
        """Test withdrawal when cash insufficient, must sell shares."""
        withdrawal_amount = 5000
        total_shares = 100
        price = 100
        borrowed_amount = 0
        current_balance = 2000
        total_cost_basis = 10000

        new_shares, new_balance, new_borrowed, new_cost_basis, shares_sold, debt_repaid, withdrawn = \
            execute_monthly_withdrawal(
                withdrawal_amount, total_shares, price, borrowed_amount,
                current_balance, total_cost_basis
            )

        # Need $3000 more, sell 30 shares at $100
        self.assertEqual(shares_sold, 30)
        self.assertEqual(new_shares, 70)
        # Cost basis reduced proportionally: 10000 * (30/100) = 3000
        self.assertEqual(new_cost_basis, 7000)
        # Balance: 2000 + 3000 (sales) - 5000 (withdrawal) = 0
        self.assertEqual(new_balance, 0)
        self.assertEqual(withdrawn, 5000)

    def test_withdrawal_with_debt_repayment(self):
        """Test that debt is repaid before withdrawal."""
        withdrawal_amount = 5000
        total_shares = 100
        price = 100
        borrowed_amount = 3000
        current_balance = 10000
        total_cost_basis = 13000

        new_shares, new_balance, new_borrowed, new_cost_basis, shares_sold, debt_repaid, withdrawn = \
            execute_monthly_withdrawal(
                withdrawal_amount, total_shares, price, borrowed_amount,
                current_balance, total_cost_basis
            )

        self.assertEqual(new_shares, 100)  # No shares sold (enough cash)
        self.assertEqual(debt_repaid, 3000)
        self.assertEqual(new_borrowed, 0)
        # Balance: 10000 - 3000 (debt) - 5000 (withdrawal) = 2000
        self.assertEqual(new_balance, 2000)
        self.assertEqual(withdrawn, 5000)

    def test_withdrawal_sells_shares_for_debt_and_withdrawal(self):
        """Test selling shares to cover both debt and withdrawal."""
        withdrawal_amount = 5000
        total_shares = 100
        price = 100
        borrowed_amount = 3000
        current_balance = 1000
        total_cost_basis = 11000

        new_shares, new_balance, new_borrowed, new_cost_basis, shares_sold, debt_repaid, withdrawn = \
            execute_monthly_withdrawal(
                withdrawal_amount, total_shares, price, borrowed_amount,
                current_balance, total_cost_basis
            )

        # Total needed: 8000 (3000 debt + 5000 withdrawal)
        # Have: 1000
        # Need to sell: 70 shares for $7000
        self.assertEqual(shares_sold, 70)
        self.assertEqual(new_shares, 30)
        # Cost basis: 11000 * (30/100) = 3300
        self.assertAlmostEqual(new_cost_basis, 3300, places=2)
        self.assertEqual(debt_repaid, 3000)
        self.assertEqual(new_borrowed, 0)
        # Balance: 1000 + 7000 - 3000 - 5000 = 0
        self.assertEqual(new_balance, 0)
        self.assertEqual(withdrawn, 5000)

    def test_partial_liquidation(self):
        """Test withdrawal that requires selling most shares."""
        withdrawal_amount = 8000
        total_shares = 100
        price = 100
        borrowed_amount = 0
        current_balance = 500
        total_cost_basis = 10000

        new_shares, new_balance, new_borrowed, new_cost_basis, shares_sold, debt_repaid, withdrawn = \
            execute_monthly_withdrawal(
                withdrawal_amount, total_shares, price, borrowed_amount,
                current_balance, total_cost_basis
            )

        # Need $7500 more, sell 75 shares
        self.assertEqual(shares_sold, 75)
        self.assertEqual(new_shares, 25)
        # Cost basis: 10000 * (25/100) = 2500
        self.assertEqual(new_cost_basis, 2500)
        # Balance: 500 + 7500 - 8000 = 0
        self.assertEqual(new_balance, 0)
        self.assertEqual(withdrawn, 8000)

    def test_complete_liquidation_insufficient_funds(self):
        """Test attempting withdrawal larger than portfolio value."""
        withdrawal_amount = 15000
        total_shares = 100
        price = 100
        borrowed_amount = 0
        current_balance = 1000
        total_cost_basis = 10000

        new_shares, new_balance, new_borrowed, new_cost_basis, shares_sold, debt_repaid, withdrawn = \
            execute_monthly_withdrawal(
                withdrawal_amount, total_shares, price, borrowed_amount,
                current_balance, total_cost_basis
            )

        # Sell all shares (100 shares = $10000)
        self.assertEqual(shares_sold, 100)
        self.assertEqual(new_shares, 0)
        self.assertEqual(new_cost_basis, 0)
        # Total available: 1000 + 10000 = 11000
        # Can only withdraw 11000, not 15000
        self.assertEqual(withdrawn, 11000)
        self.assertEqual(new_balance, 0)

    def test_cost_basis_proportional_reduction(self):
        """Test that cost basis is reduced proportionally to shares sold."""
        withdrawal_amount = 5000
        total_shares = 100
        price = 100
        borrowed_amount = 0
        current_balance = 0
        total_cost_basis = 8000  # Average cost $80/share

        new_shares, new_balance, new_borrowed, new_cost_basis, shares_sold, debt_repaid, withdrawn = \
            execute_monthly_withdrawal(
                withdrawal_amount, total_shares, price, borrowed_amount,
                current_balance, total_cost_basis
            )

        # Sell 50 shares
        self.assertEqual(shares_sold, 50)
        # Cost basis should be reduced by 50%
        self.assertEqual(new_cost_basis, 4000)

    def test_zero_withdrawal_amount(self):
        """Test with zero withdrawal amount."""
        withdrawal_amount = 0
        total_shares = 100
        price = 100
        borrowed_amount = 3000
        current_balance = 5000
        total_cost_basis = 13000

        new_shares, new_balance, new_borrowed, new_cost_basis, shares_sold, debt_repaid, withdrawn = \
            execute_monthly_withdrawal(
                withdrawal_amount, total_shares, price, borrowed_amount,
                current_balance, total_cost_basis
            )

        # Should still repay debt even with zero withdrawal
        self.assertEqual(debt_repaid, 3000)
        self.assertEqual(new_borrowed, 0)
        self.assertEqual(withdrawn, 0)
        # Balance: 5000 - 3000 = 2000
        self.assertEqual(new_balance, 2000)
        self.assertEqual(shares_sold, 0)

    def test_debt_larger_than_withdrawal(self):
        """Test when debt is much larger than withdrawal amount."""
        withdrawal_amount = 1000
        total_shares = 100
        price = 100
        borrowed_amount = 8000
        current_balance = 500
        total_cost_basis = 18000

        new_shares, new_balance, new_borrowed, new_cost_basis, shares_sold, debt_repaid, withdrawn = \
            execute_monthly_withdrawal(
                withdrawal_amount, total_shares, price, borrowed_amount,
                current_balance, total_cost_basis
            )

        # Total needed: 9000 (8000 debt + 1000 withdrawal)
        # Have: 500
        # Need to sell: 85 shares for $8500
        self.assertEqual(shares_sold, 85)
        self.assertEqual(debt_repaid, 8000)
        self.assertEqual(withdrawn, 1000)


if __name__ == '__main__':
    unittest.main()
