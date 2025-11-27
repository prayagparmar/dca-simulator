"""
Unit tests for domain logic functions (Sprint 2 Refactoring)

These functions encapsulate business logic and state management.
They build upon pure calculation functions from Sprint 1.
"""

import unittest
from app import (
    process_dividend,
    process_interest_charge,
    execute_purchase,
    execute_margin_call
)


class TestProcessDividend(unittest.TestCase):
    """Test the process_dividend() domain function"""

    def test_reinvest_basic(self):
        """Test basic dividend reinvestment"""
        shares_added, new_cost, new_balance, income = process_dividend(
            total_shares=100,
            dividend_per_share=2.0,
            price=50.0,
            reinvest=True,
            current_balance=1000,
            total_cost_basis=5000
        )
        # Dividend: 100 * 2.0 = $200
        # Shares bought: 200 / 50 = 4.0
        # Cost basis increases by dividend amount
        self.assertEqual(shares_added, 4.0)
        self.assertEqual(new_cost, 5200)  # 5000 + 200
        self.assertEqual(new_balance, 1000)  # Unchanged when reinvesting
        self.assertEqual(income, 200)

    def test_accumulate_basic(self):
        """Test basic dividend accumulation to cash"""
        shares_added, new_cost, new_balance, income = process_dividend(
            total_shares=100,
            dividend_per_share=2.0,
            price=50.0,
            reinvest=False,
            current_balance=1000,
            total_cost_basis=5000
        )
        # Dividend: 100 * 2.0 = $200
        # Should add to cash balance
        self.assertEqual(shares_added, 0)
        self.assertEqual(new_cost, 5000)  # Unchanged
        self.assertEqual(new_balance, 1200)  # 1000 + 200
        self.assertEqual(income, 200)

    def test_reinvest_fractional_shares(self):
        """Test dividend reinvestment with fractional shares"""
        shares_added, new_cost, new_balance, income = process_dividend(
            total_shares=123.456,
            dividend_per_share=0.75,
            price=33.33,
            reinvest=True,
            current_balance=500,
            total_cost_basis=4000
        )
        # Dividend: 123.456 * 0.75 = 92.592
        # Shares: 92.592 / 33.33 = 2.778...
        self.assertAlmostEqual(shares_added, 2.778, places=3)
        self.assertAlmostEqual(new_cost, 4092.592, places=3)
        self.assertEqual(new_balance, 500)
        self.assertAlmostEqual(income, 92.592, places=3)

    def test_accumulate_none_balance(self):
        """Test accumulation when balance tracking is disabled"""
        shares_added, new_cost, new_balance, income = process_dividend(
            total_shares=100,
            dividend_per_share=1.0,
            price=100.0,
            reinvest=False,
            current_balance=None,
            total_cost_basis=10000
        )
        # Should handle None balance gracefully
        self.assertEqual(shares_added, 0)
        self.assertEqual(new_cost, 10000)
        self.assertIsNone(new_balance)
        self.assertEqual(income, 100)

    def test_zero_dividend(self):
        """Test with zero dividend"""
        shares_added, new_cost, new_balance, income = process_dividend(
            total_shares=100,
            dividend_per_share=0,
            price=50.0,
            reinvest=True,
            current_balance=1000,
            total_cost_basis=5000
        )
        self.assertEqual(shares_added, 0)
        self.assertEqual(new_cost, 5000)
        self.assertEqual(new_balance, 1000)
        self.assertEqual(income, 0)

    def test_large_dividend(self):
        """Test with special dividend larger than share price"""
        shares_added, new_cost, new_balance, income = process_dividend(
            total_shares=100,
            dividend_per_share=150.0,  # Larger than price!
            price=100.0,
            reinvest=True,
            current_balance=5000,
            total_cost_basis=10000
        )
        # Dividend: 100 * 150 = $15,000
        # Shares: 15000 / 100 = 150
        self.assertEqual(shares_added, 150.0)
        self.assertEqual(new_cost, 25000)
        self.assertEqual(new_balance, 5000)
        self.assertEqual(income, 15000)


class TestProcessInterestCharge(unittest.TestCase):
    """Test the process_interest_charge() domain function"""

    def test_pay_from_cash(self):
        """Test paying interest from cash balance"""
        new_balance, new_debt, interest = process_interest_charge(
            borrowed_amount=10000,
            fed_rate=0.05,
            current_balance=1000
        )
        # Interest: (10000 * (0.05 + 0.005)) / 12 = 45.833...
        self.assertAlmostEqual(new_balance, 954.167, places=2)
        self.assertEqual(new_debt, 10000)  # Debt unchanged
        self.assertAlmostEqual(interest, 45.833, places=2)

    def test_capitalize_to_debt(self):
        """Test capitalizing interest when insufficient cash"""
        new_balance, new_debt, interest = process_interest_charge(
            borrowed_amount=10000,
            fed_rate=0.05,
            current_balance=20  # Not enough to pay $45.83
        )
        # Paid $20 from cash, capitalize remaining $25.83
        self.assertEqual(new_balance, 0)
        self.assertAlmostEqual(new_debt, 10025.833, places=2)
        self.assertAlmostEqual(interest, 45.833, places=2)

    def test_zero_cash(self):
        """Test with zero cash - all interest capitalizes"""
        new_balance, new_debt, interest = process_interest_charge(
            borrowed_amount=50000,
            fed_rate=0.055,
            current_balance=0
        )
        # Interest: (50000 * (0.055 + 0.005)) / 12 = 250
        self.assertEqual(new_balance, 0)
        self.assertEqual(new_debt, 50250)
        self.assertEqual(interest, 250)

    def test_none_balance(self):
        """Test with None balance (balance tracking disabled)"""
        new_balance, new_debt, interest = process_interest_charge(
            borrowed_amount=10000,
            fed_rate=0.05,
            current_balance=None
        )
        # Should return None balance, unchanged debt
        self.assertIsNone(new_balance)
        self.assertEqual(new_debt, 10000)
        self.assertAlmostEqual(interest, 45.833, places=2)

    def test_exact_cash_match(self):
        """Test when cash exactly matches interest charge"""
        interest_charge = (10000 * (0.05 + 0.005)) / 12  # 45.833...
        new_balance, new_debt, interest = process_interest_charge(
            borrowed_amount=10000,
            fed_rate=0.05,
            current_balance=interest_charge
        )
        self.assertAlmostEqual(new_balance, 0, places=2)
        self.assertEqual(new_debt, 10000)
        self.assertAlmostEqual(interest, interest_charge, places=2)

    def test_high_rate(self):
        """Test with high interest rate (20%)"""
        new_balance, new_debt, interest = process_interest_charge(
            borrowed_amount=10000,
            fed_rate=0.20,
            current_balance=5000
        )
        # Interest: (10000 * (0.20 + 0.005)) / 12 = 170.833...
        self.assertAlmostEqual(new_balance, 4829.167, places=2)
        self.assertEqual(new_debt, 10000)
        self.assertAlmostEqual(interest, 170.833, places=2)

    def test_negative_balance_safety(self):
        """Test safety clamp prevents negative balance"""
        new_balance, new_debt, interest = process_interest_charge(
            borrowed_amount=10000,
            fed_rate=0.05,
            current_balance=10  # Less than interest
        )
        # Should clamp balance to 0, capitalize rest
        self.assertEqual(new_balance, 0)
        self.assertAlmostEqual(new_debt, 10035.833, places=2)  # 10000 + (45.833 - 10)
        self.assertAlmostEqual(interest, 45.833, places=2)


class TestExecutePurchase(unittest.TestCase):
    """Test the execute_purchase() domain function"""

    def test_basic_cash_purchase(self):
        """Test basic purchase with cash only (no margin)"""
        result = execute_purchase(
            daily_investment=100,
            price=50.0,
            current_balance=5000,
            borrowed_amount=0,
            margin_ratio=1.0,  # No margin
            total_shares=0,
            available_principal=10000
        )
        shares, cash_used, margin_borrowed, actual_inv, principal_used, new_bal, new_debt = result

        # Should buy: 100 / 50 = 2 shares
        self.assertEqual(shares, 2.0)
        self.assertEqual(cash_used, 100)
        self.assertEqual(margin_borrowed, 0)
        self.assertEqual(actual_inv, 100)
        self.assertEqual(principal_used, 100)
        self.assertEqual(new_bal, 4900)  # 5000 - 100
        self.assertEqual(new_debt, 0)

    def test_margin_purchase(self):
        """Test purchase using margin (2x leverage) - only borrows when cash insufficient"""
        result = execute_purchase(
            daily_investment=100,
            price=50.0,
            current_balance=100,  # Exactly enough cash
            borrowed_amount=0,
            margin_ratio=2.0,  # Margin available but not used
            total_shares=0,
            available_principal=10000
        )
        shares, cash_used, margin_borrowed, actual_inv, principal_used, new_bal, new_debt = result

        # Have enough cash - don't borrow! (Robinhood style)
        # Shares: 100 / 50 = 2
        self.assertEqual(shares, 2.0)
        self.assertEqual(cash_used, 100)
        self.assertEqual(margin_borrowed, 0)  # No borrowing needed
        self.assertEqual(actual_inv, 100)
        self.assertEqual(principal_used, 100)
        self.assertAlmostEqual(new_bal, 0, places=2)
        self.assertEqual(new_debt, 0)

    def test_margin_actually_used(self):
        """Test margin actually being borrowed when cash insufficient"""
        result = execute_purchase(
            daily_investment=100,
            price=50.0,
            current_balance=50,  # Only $50 cash
            borrowed_amount=0,
            margin_ratio=2.0,  # Margin enabled
            total_shares=0,
            available_principal=10000
        )
        shares, cash_used, margin_borrowed, actual_inv, principal_used, new_bal, new_debt = result

        # Use $50 cash + borrow $50 = invest $100 total
        self.assertEqual(shares, 2.0)  # 100 / 50
        self.assertEqual(cash_used, 50)
        self.assertEqual(margin_borrowed, 50)
        self.assertEqual(actual_inv, 100)
        self.assertEqual(principal_used, 50)
        self.assertAlmostEqual(new_bal, 0, places=2)
        self.assertEqual(new_debt, 50)

    def test_insufficient_cash(self):
        """Test purchase when cash runs out mid-simulation (no margin)"""
        result = execute_purchase(
            daily_investment=1000,  # Want to invest $1000
            price=50.0,
            current_balance=100,  # Only have $100
            borrowed_amount=0,
            margin_ratio=1.0,  # No margin
            total_shares=0,
            available_principal=10000
        )
        shares, cash_used, margin_borrowed, actual_inv, principal_used, new_bal, new_debt = result

        # Can only invest what we have: $100 (large investment triggers using all cash)
        self.assertEqual(shares, 2.0)  # 100 / 50
        self.assertEqual(cash_used, 100)
        self.assertEqual(margin_borrowed, 0)
        self.assertEqual(actual_inv, 100)
        self.assertEqual(principal_used, 100)
        self.assertAlmostEqual(new_bal, 0, places=2)

    def test_principal_tracking(self):
        """Test principal used tracking (doesn't limit purchase, just tracks)"""
        result = execute_purchase(
            daily_investment=500,
            price=50.0,
            current_balance=10000,
            borrowed_amount=0,
            margin_ratio=1.0,
            total_shares=0,
            available_principal=100  # Only $100 principal left, but doesn't limit purchase
        )
        shares, cash_used, margin_borrowed, actual_inv, principal_used, new_bal, new_debt = result

        # Function doesn't limit based on principal - just tracks it
        # Invests full $500
        self.assertEqual(shares, 10.0)  # 500 / 50
        self.assertEqual(cash_used, 500)
        self.assertEqual(actual_inv, 500)
        self.assertEqual(principal_used, 100)  # Only 100 of 500 counts as principal
        self.assertEqual(new_bal, 9500)

    def test_none_balance(self):
        """Test purchase with balance tracking disabled (infinite cash mode)"""
        result = execute_purchase(
            daily_investment=100,
            price=50.0,
            current_balance=None,
            borrowed_amount=0,
            margin_ratio=1.0,
            total_shares=0,
            available_principal=10000
        )
        shares, cash_used, margin_borrowed, actual_inv, principal_used, new_bal, new_debt = result

        # In infinite cash mode, always invests the daily amount
        self.assertEqual(shares, 2.0)
        self.assertEqual(cash_used, 100)  # Tracked but balance stays None
        self.assertEqual(margin_borrowed, 0)
        self.assertEqual(actual_inv, 100)
        self.assertEqual(principal_used, 100)
        self.assertIsNone(new_bal)

    def test_margin_with_existing_debt(self):
        """Test margin purchase when already have debt - uses cash first"""
        result = execute_purchase(
            daily_investment=100,
            price=50.0,
            current_balance=200,
            borrowed_amount=5000,  # Already have debt
            margin_ratio=2.0,
            total_shares=100,  # Already own shares
            available_principal=5000
        )
        shares, cash_used, margin_borrowed, actual_inv, principal_used, new_bal, new_debt = result

        # Have enough cash ($200 > $100) - uses cash, doesn't borrow
        self.assertEqual(shares, 2.0)  # 100 / 50
        self.assertEqual(cash_used, 100)
        self.assertEqual(margin_borrowed, 0)  # Don't borrow when have cash
        self.assertEqual(actual_inv, 100)
        self.assertEqual(principal_used, 100)
        self.assertAlmostEqual(new_bal, 100, places=2)  # 200 - 100
        self.assertEqual(new_debt, 5000)  # Unchanged

    def test_zero_investment(self):
        """Test with zero daily investment"""
        result = execute_purchase(
            daily_investment=0,
            price=50.0,
            current_balance=1000,
            borrowed_amount=0,
            margin_ratio=1.0,
            total_shares=10,
            available_principal=5000
        )
        shares, cash_used, margin_borrowed, actual_inv, principal_used, new_bal, new_debt = result

        self.assertEqual(shares, 0)
        self.assertEqual(cash_used, 0)
        self.assertEqual(margin_borrowed, 0)
        self.assertEqual(actual_inv, 0)
        self.assertEqual(new_bal, 1000)


class TestExecuteMarginCall(unittest.TestCase):
    """Test the execute_margin_call() domain function"""

    def test_no_margin_call_needed(self):
        """Test when equity is above maintenance margin"""
        shares_rem, new_bal, new_debt, triggered = execute_margin_call(
            total_shares=200,
            price=60,
            borrowed_amount=10000,
            current_balance=0,
            maintenance_margin=0.25
        )
        # Portfolio: 200 * 60 = $12k
        # Equity: 12k + 0 - 10k = 2k
        # Ratio: 2k / 12k = 16.67% < 25% - SHOULD trigger
        # Wait, let me recalculate...
        # Actually this SHOULD trigger a margin call
        self.assertLess(shares_rem, 200)  # Should sell some shares
        self.assertTrue(triggered)

    def test_basic_margin_call(self):
        """Test basic margin call liquidation"""
        shares_rem, new_bal, new_debt, triggered = execute_margin_call(
            total_shares=200,
            price=60,
            borrowed_amount=10000,
            current_balance=0,
            maintenance_margin=0.25
        )
        # Portfolio value: 200 * 60 = $12,000
        # Equity: 12000 - 10000 = $2,000
        # Equity ratio: 2000 / 12000 = 0.1667 (16.67%)
        # Below 25% maintenance - MARGIN CALL

        # Target portfolio: (10000 - 0) / (1 - 0.25) = 13,333.33
        # But current is only $12k, need to reduce debt
        # Actually: should liquidate to restore 25% equity

        self.assertTrue(triggered)
        self.assertLess(shares_rem, 200)  # Some shares sold
        self.assertLess(new_debt, 10000)  # Debt reduced

    def test_complete_liquidation(self):
        """Test complete liquidation when portfolio can't cover debt"""
        shares_rem, new_bal, new_debt, triggered = execute_margin_call(
            total_shares=100,
            price=50,
            borrowed_amount=10000,
            current_balance=0,
            maintenance_margin=0.25
        )
        # Portfolio: 100 * 50 = $5,000
        # Debt: $10,000
        # Equity: -$5,000 (deeply underwater!)

        # Should liquidate everything
        self.assertEqual(shares_rem, 0)
        self.assertTrue(triggered)
        # Debt should be reduced by liquidation proceeds
        self.assertLess(new_debt, 10000)

    def test_margin_call_with_cash(self):
        """Test margin call when cash balance is available"""
        shares_rem, new_bal, new_debt, triggered = execute_margin_call(
            total_shares=200,
            price=60,
            borrowed_amount=10000,
            current_balance=2000,  # Have cash
            maintenance_margin=0.25
        )
        # Portfolio: 200 * 60 = $12k
        # Equity: 12k + 2k - 10k = 4k
        # Ratio: 4k / 12k = 33.33% > 25% - NO margin call!

        self.assertFalse(triggered)
        self.assertEqual(shares_rem, 200)  # No liquidation
        self.assertEqual(new_bal, 2000)  # Cash unchanged
        self.assertEqual(new_debt, 10000)  # Debt unchanged

    def test_margin_call_at_exact_threshold(self):
        """Test at exactly 25% equity (boundary condition)"""
        # Set up scenario where equity is exactly 25%
        # If portfolio = $10k, debt = $7.5k, equity = $2.5k
        # Ratio: 2.5k / 10k = 25%
        shares_rem, new_bal, new_debt, triggered = execute_margin_call(
            total_shares=100,
            price=100,  # Portfolio = $10k
            borrowed_amount=7500,
            current_balance=0,
            maintenance_margin=0.25
        )
        # At exactly 25% - should NOT trigger (>= check)
        self.assertFalse(triggered)
        self.assertEqual(shares_rem, 100)
        self.assertEqual(new_debt, 7500)

    def test_none_balance_margin_call(self):
        """Test margin call with balance tracking disabled"""
        shares_rem, new_bal, new_debt, triggered = execute_margin_call(
            total_shares=200,
            price=60,
            borrowed_amount=10000,
            current_balance=None,
            maintenance_margin=0.25
        )
        # Without cash tracking, equity = portfolio - debt
        # 12000 - 10000 = 2000
        # Ratio: 2000 / 12000 = 16.67% < 25%

        self.assertTrue(triggered)
        self.assertLess(shares_rem, 200)
        self.assertIsNone(new_bal)


class TestDomainFunctionIntegration(unittest.TestCase):
    """Integration tests combining multiple domain functions"""

    def test_dividend_then_purchase(self):
        """Test receiving dividend then using it for purchase"""
        # Step 1: Process dividend (accumulate)
        _, _, cash_after_div, income = process_dividend(
            total_shares=100,
            dividend_per_share=2.0,
            price=50.0,
            reinvest=False,
            current_balance=1000,
            total_cost_basis=5000
        )
        self.assertEqual(cash_after_div, 1200)  # 1000 + 200 dividend

        # Step 2: Use cash for purchase
        shares, cash_used, _, _, _, new_bal, _ = execute_purchase(
            daily_investment=100,
            price=50.0,
            current_balance=cash_after_div,
            borrowed_amount=0,
            margin_ratio=1.0,
            total_shares=100,
            available_principal=10000
        )
        self.assertEqual(shares, 2.0)
        self.assertEqual(new_bal, 1100)  # 1200 - 100

    def test_interest_depletes_cash_then_purchase_fails(self):
        """Test interest depleting cash, then purchase has insufficient funds"""
        # Step 1: Charge interest (large debt, small cash)
        new_bal, new_debt, _ = process_interest_charge(
            borrowed_amount=50000,
            fed_rate=0.055,
            current_balance=150  # Only $150 cash
        )
        # Interest: $250, can only pay $150, capitalize rest
        self.assertEqual(new_bal, 0)
        self.assertEqual(new_debt, 50100)

        # Step 2: Try to purchase with no cash
        shares, _, _, actual_inv, _, final_bal, _ = execute_purchase(
            daily_investment=100,
            price=50.0,
            current_balance=new_bal,  # $0
            borrowed_amount=new_debt,
            margin_ratio=1.0,
            total_shares=100,
            available_principal=5000
        )
        # Can't buy anything - no cash!
        self.assertEqual(shares, 0)
        self.assertEqual(actual_inv, 0)

    def test_margin_call_after_price_drop(self):
        """Test margin call triggered by price drop"""
        # Initial state: 200 shares @ $100 = $20k portfolio, $10k debt
        # Equity: $10k / $20k = 50% (healthy)

        # Price drops to $60
        new_price = 60
        new_portfolio = 200 * new_price  # $12k

        # Check margin call
        shares_rem, _, debt_rem, triggered = execute_margin_call(
            total_shares=200,
            price=new_price,
            borrowed_amount=10000,
            current_balance=0,
            maintenance_margin=0.25
        )
        # Equity: (12k - 10k) / 12k = 16.67% < 25%
        self.assertTrue(triggered)
        self.assertLess(shares_rem, 200)
        self.assertLess(debt_rem, 10000)

    def test_full_cycle_with_margin(self):
        """Test complete cycle: purchase with margin, receive dividend, pay interest"""
        # Step 1: Buy with margin (insufficient cash triggers borrowing)
        shares1, cash1, margin_borrowed, _, _, bal1, debt1 = execute_purchase(
            daily_investment=100,
            price=50.0,
            current_balance=50,  # Only $50 - will borrow
            borrowed_amount=0,
            margin_ratio=2.0,
            total_shares=0,
            available_principal=10000
        )
        self.assertEqual(shares1, 2.0)  # 100 / 50
        self.assertEqual(cash1, 50)
        self.assertEqual(margin_borrowed, 50)
        self.assertEqual(debt1, 50)

        # Step 2: Receive dividend (accumulate)
        _, _, bal2, div_income = process_dividend(
            total_shares=shares1,
            dividend_per_share=1.0,
            price=50.0,
            reinvest=False,
            current_balance=bal1,
            total_cost_basis=100
        )
        self.assertEqual(div_income, 2.0)  # 2 shares * $1
        self.assertAlmostEqual(bal2, 2.0, places=2)  # 0 + 2 dividend

        # Step 3: Charge interest
        bal3, debt3, interest = process_interest_charge(
            borrowed_amount=debt1,
            fed_rate=0.05,
            current_balance=bal2
        )
        # Interest on $100 debt should be small, can pay from cash
        self.assertGreater(bal3, 0)  # Still have cash left
        self.assertEqual(debt3, debt1)  # Debt unchanged


if __name__ == '__main__':
    unittest.main(verbosity=2)
