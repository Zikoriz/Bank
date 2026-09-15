import unittest

from day1.exceptions import InsufficientFundsError, InvalidOperationError
from day2.account import InvestmentAccount, SavingsAccount


class SavingsAccountErrorTypeTests(unittest.TestCase):
    """REQ-H6: which error a rejected withdrawal raises must reflect why."""

    def test_withdrawing_more_than_balance_with_no_minimum_is_insufficient_funds(self):
        account = SavingsAccount("Roman", balance=1_000, min_balance=0)
        with self.assertRaises(InsufficientFundsError):
            account.withdraw(1_500)

    def test_withdrawing_within_balance_but_breaching_minimum_is_invalid_operation(self):
        account = SavingsAccount("Roman", balance=5_000, min_balance=3_000)
        with self.assertRaises(InvalidOperationError):
            account.withdraw(3_000)
        self.assertEqual(account.balance, 5_000)

    def test_interest_rate_above_one_is_rejected(self):
        with self.assertRaises(ValueError):
            SavingsAccount("Roman", balance=1_000, monthly_interest_rate=1.5)


class InvestmentAccountCashTests(unittest.TestCase):
    """REQ-C2/REQ-L2: portfolio never exceeds balance; only free cash can be withdrawn."""

    def test_constructor_rejects_a_portfolio_larger_than_balance_with_value_error(self):
        with self.assertRaises(ValueError):
            InvestmentAccount("Roman", balance=5_000, portfolio={"stocks": 6_000})

    def test_withdraw_is_limited_to_available_non_invested_cash(self):
        account = InvestmentAccount(
            "Roman", balance=11_000, portfolio={"stocks": 5_000, "bonds": 3_000, "etf": 2_000}
        )
        self.assertEqual(account.allocated, 10_000)
        self.assertEqual(account.available, 1_000)
        account.withdraw(1_000)
        self.assertEqual(account.balance, 10_000)
        self.assertEqual(account.portfolio, {"stocks": 5_000, "bonds": 3_000, "etf": 2_000})

    def test_withdraw_beyond_available_cash_is_rejected(self):
        account = InvestmentAccount(
            "Roman", balance=11_000, portfolio={"stocks": 5_000, "bonds": 3_000, "etf": 2_000}
        )
        with self.assertRaises(InsufficientFundsError):
            account.withdraw(1_001)
        self.assertEqual(account.balance, 11_000)
        self.assertEqual(account.portfolio, {"stocks": 5_000, "bonds": 3_000, "etf": 2_000})

    def test_portfolio_property_returns_a_copy_not_a_live_reference(self):
        account = InvestmentAccount("Roman", balance=5_000, portfolio={"stocks": 1_000})
        snapshot = account.portfolio
        snapshot["stocks"] = 999_999
        self.assertEqual(account.portfolio["stocks"], 1_000)


if __name__ == "__main__":
    unittest.main()
