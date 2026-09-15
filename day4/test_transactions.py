from datetime import datetime, timedelta
import unittest

from day1.exceptions import AccountFrozenError
from day2.account import PremiumAccount, SavingsAccount
from day4 import Transaction, TransactionProcessor, TransactionQueue, TransactionStatus, TransactionType


class TransactionSystemTests(unittest.TestCase):
    def setUp(self):
        self.sender = SavingsAccount("Roman", balance=1_000, currency="USD", account_number="SENDER01")
        self.recipient = SavingsAccount("Alex", balance=100, currency="EUR", account_number="RECIP01")
        self.processor = TransactionProcessor(
            {"SENDER01": self.sender, "RECIP01": self.recipient},
            exchange_rates={("USD", "EUR"): "0.9"},
        )

    def test_external_transfer_charges_fee_and_converts_currency(self):
        transaction = Transaction(
            "SENDER01", "RECIP01", 100, "USD", TransactionType.EXTERNAL_TRANSFER
        )
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.COMPLETED)
        self.assertEqual(transaction.fee, 1)
        self.assertEqual(transaction.converted_amount, 90)
        self.assertEqual(self.sender.balance, 899)
        self.assertEqual(self.recipient.balance, 190)

    def test_regular_account_cannot_go_below_zero(self):
        transaction = Transaction("SENDER01", "RECIP01", 1_001, "USD")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.REJECTED)
        self.assertEqual(self.sender.balance, 1_000)

    def test_premium_account_can_use_overdraft(self):
        premium = PremiumAccount(
            "Roman", balance=100, currency="USD", account_number="PREMIUM01",
            overdraft_limit=500, monthly_fee=100,
        )
        self.processor.accounts["PREMIUM01"] = premium
        transaction = Transaction("PREMIUM01", "RECIP01", 300, "USD")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.COMPLETED)
        # REQ-C1: the monthly fee is a separate charge, never folded into a
        # transfer debit -- only the transferred 300 leaves the account.
        self.assertEqual(premium.balance, -200)
        self.assertEqual(premium.monthly_fee, 100)

    def test_monthly_fee_is_independent_of_transfers(self):
        premium = PremiumAccount(
            "Roman", balance=100, currency="USD", account_number="PREMIUM01",
            overdraft_limit=500, monthly_fee=100,
        )
        premium.apply_monthly_fee()
        self.assertEqual(premium.balance, 0)

    def test_self_transfer_is_rejected_before_any_debit(self):
        transaction = Transaction("SENDER01", "SENDER01", 100, "USD")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.REJECTED)
        self.assertEqual(self.sender.balance, 1_000)

    def test_rollback_on_credit_failure_leaves_sender_balance_untouched(self):
        transaction = Transaction("SENDER01", "RECIP01", 100, "USD")

        def failing_deposit(_amount):
            raise RuntimeError("simulated deposit failure")

        self.recipient.deposit = failing_deposit
        with self.assertRaises(RuntimeError):
            self.processor._process_once(transaction)
        self.assertEqual(self.sender.balance, 1_000)

    def test_deposit_and_withdraw_reject_bool_and_non_finite_amounts(self):
        with self.assertRaises(Exception):
            self.sender.deposit(True)
        with self.assertRaises(Exception):
            self.sender.withdraw(float("nan"))
        with self.assertRaises(Exception):
            self.sender.withdraw(float("inf"))
        self.assertEqual(self.sender.balance, 1_000)

    def test_external_transfer_settles_with_no_matching_recipient_account(self):
        """M1-A: an external transfer's recipient need not exist in this
        ledger; crediting the "outside world" is a no-op debit-only settle."""
        transaction = Transaction(
            "SENDER01", "OUTSIDE-BANK-IBAN", 100, "USD", TransactionType.EXTERNAL_TRANSFER
        )
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.COMPLETED)
        self.assertEqual(transaction.fee, 1)
        self.assertEqual(self.sender.balance, 899)
        self.assertEqual(self.recipient.balance, 100)

    def test_regular_transfer_still_requires_an_existing_recipient(self):
        transaction = Transaction("SENDER01", "UNKNOWN-ACCOUNT", 100, "USD")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.REJECTED)
        self.assertEqual(self.sender.balance, 1_000)

    def test_transfer_amount_not_representable_in_binary_float_settles_cleanly(self):
        sender = SavingsAccount("Roman", balance=10.10, currency="USD", account_number="SENDER02")
        recipient = SavingsAccount("Alex", balance=0, currency="USD", account_number="RECIP02")
        processor = TransactionProcessor({"SENDER02": sender, "RECIP02": recipient})
        transaction = Transaction("SENDER02", "RECIP02", "0.1", "USD")
        processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.COMPLETED)
        self.assertEqual(sender.balance, 10.0)
        self.assertEqual(recipient.balance, 0.1)

    def test_savings_minimum_balance_is_enforced(self):
        self.sender.min_balance = 950
        transaction = Transaction("SENDER01", "RECIP01", 100, "USD")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.REJECTED)
        self.assertEqual(self.sender.balance, 1_000)

    def test_premium_withdraw_limit_is_enforced(self):
        premium = PremiumAccount(
            "Roman", balance=10_000, currency="USD", account_number="PREMIUM01",
            withdraw_limit=100, monthly_fee=0,
        )
        self.processor.accounts["PREMIUM01"] = premium
        transaction = Transaction("PREMIUM01", "RECIP01", 101, "USD")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.REJECTED)
        self.assertEqual(premium.balance, 10_000)

    def test_operation_time_restriction_is_enforced(self):
        def prohibit_operations():
            raise PermissionError("Operations are prohibited from 00:00 to 05:00")

        self.sender._operation_time_checker = prohibit_operations
        transaction = Transaction("SENDER01", "RECIP01", 100, "USD")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.REJECTED)
        self.assertEqual(self.sender.balance, 1_000)
        self.assertEqual(self.recipient.balance, 100)

    def test_frozen_account_is_rejected(self):
        self.sender.status = "frozen"
        transaction = Transaction("SENDER01", "RECIP01", 100, "USD")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.REJECTED)
        self.assertIn("frozen", transaction.rejection_reason)

    def test_queue_honours_priority_delay_and_cancellation(self):
        queue = TransactionQueue()
        low = Transaction("SENDER01", "RECIP01", 10, "USD")
        high = Transaction("SENDER01", "RECIP01", 20, "USD")
        delayed = Transaction("SENDER01", "RECIP01", 30, "USD")
        cancelled = Transaction("SENDER01", "RECIP01", 40, "USD")
        queue.add(low, priority=1)
        queue.add(high, priority=5)
        queue.add(delayed, scheduled_at=datetime.now() + timedelta(days=1))
        queue.add(cancelled)
        queue.cancel(cancelled.transaction_id)
        self.assertIs(queue.get_next(), high)
        self.assertIs(queue.get_next(), low)
        self.assertIsNone(queue.get_next())
        self.assertEqual(cancelled.status, TransactionStatus.CANCELLED)

    def test_cancel_is_rejected_once_processing_or_terminal(self):
        queue = TransactionQueue()
        transaction = Transaction("SENDER01", "RECIP01", 10, "USD")
        queue.add(transaction)
        transaction.set_status(TransactionStatus.PROCESSING)
        with self.assertRaises(ValueError):
            queue.cancel(transaction.transaction_id)
        transaction.set_status(TransactionStatus.COMPLETED)
        with self.assertRaises(ValueError):
            queue.cancel(transaction.transaction_id)

    def test_processor_does_not_overwrite_a_cancelled_transaction(self):
        """A cancellation that lands between the debit/credit step and the
        final status update must win over an automatic COMPLETED (REQ-M6)."""
        transaction = Transaction("SENDER01", "RECIP01", 10, "USD")
        original_process_once = self.processor._process_once

        def process_once_then_cancel(txn):
            original_process_once(txn)
            txn.status = TransactionStatus.CANCELLED

        self.processor._process_once = process_once_then_cancel
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
