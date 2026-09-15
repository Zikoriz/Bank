import unittest
import uuid

from day1.exceptions import AccountClosedError, InvalidOperationError
from day3.bank import Bank
from day3.client import Client


class BankStatusTransitionTests(unittest.TestCase):
    """REQ-M3: status is a small state machine, not an arbitrary string."""

    def setUp(self):
        self.bank = Bank()
        self.bank.add_client(Client("Roman", "C1", 30, {}, "password"))
        self.account = self.bank.open_account(
            "C1", "savings", balance=1_000, currency="RUB", account_number="ACC1"
        )

    def test_active_to_frozen_to_active_round_trip_is_allowed(self):
        self.bank.freeze_account("ACC1")
        self.assertEqual(self.account.status, "frozen")
        self.bank.unfreeze_account("ACC1")
        self.assertEqual(self.account.status, "active")

    def test_unfreezing_a_non_frozen_account_raises(self):
        with self.assertRaises(InvalidOperationError):
            self.bank.unfreeze_account("ACC1")

    def test_freezing_an_already_frozen_account_raises(self):
        self.bank.freeze_account("ACC1")
        with self.assertRaises(InvalidOperationError):
            self.bank.freeze_account("ACC1")

    def test_frozen_to_closed_is_forbidden_directly(self):
        self.bank.freeze_account("ACC1")
        self.account.withdraw = lambda amount: None  # irrelevant here; balance stays 1000
        with self.assertRaises(InvalidOperationError):
            self.account.status = "closed"

    def test_closed_is_terminal(self):
        self.account.withdraw(1_000)
        self.bank.close_account("ACC1")
        with self.assertRaises(AccountClosedError):
            self.bank.freeze_account("ACC1")
        with self.assertRaises(AccountClosedError):
            self.bank.unfreeze_account("ACC1")
        with self.assertRaises(AccountClosedError):
            self.bank.close_account("ACC1")

    def test_open_account_rejects_an_explicit_status_kwarg(self):
        with self.assertRaises(ValueError):
            self.bank.open_account(
                "C1", "savings", balance=100, currency="RUB", status="closed"
            )


class AccountNumberGenerationTests(unittest.TestCase):
    def test_generated_account_number_is_a_full_uuid4(self):
        bank = Bank()
        bank.add_client(Client("Roman", "C1", 30, {}, "password"))
        account = bank.open_account("C1", "savings", balance=100, currency="RUB")
        # REQ-L1: a full uuid4, not an 8-character prefix of one.
        self.assertEqual(uuid.UUID(account.account_number).version, 4)


if __name__ == "__main__":
    unittest.main()
