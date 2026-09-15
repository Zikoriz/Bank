from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from day1.exceptions import InvalidOperationError
from day2.account import SavingsAccount
from day3.client import Client
from day4 import Transaction, TransactionStatus, TransactionType
from day5 import AuditLog, RiskAnalyzer, RiskControlledProcessor, RiskLevel, SecureBank, Severity


class Day5SecurityTests(unittest.TestCase):
    def setUp(self):
        self.sender = SavingsAccount("Roman", balance=500_000, currency="RUB", account_number="SENDER")
        self.recipient = SavingsAccount("Alex", balance=0, currency="RUB", account_number="RECIPIENT")
        self.audit_log = AuditLog()
        self.analyzer = RiskAnalyzer(large_amount=100_000, frequent_count=3)
        self.processor = RiskControlledProcessor(
            {"SENDER": self.sender, "RECIPIENT": self.recipient},
            audit_log=self.audit_log, risk_analyzer=self.analyzer,
            account_clients={"SENDER": "CLIENT-1"},
        )

    def test_first_new_recipient_is_detected_then_becomes_trusted_after_completion(self):
        first = Transaction("SENDER", "RECIPIENT", 1_000, "RUB")
        second = Transaction("SENDER", "RECIPIENT", 1_000, "RUB")
        self.processor.process(first)
        self.processor.process(second)
        self.assertEqual(first.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.analyzer.reports[-2].level, RiskLevel.MEDIUM)
        self.assertIn("new_recipient", self.analyzer.reports[-2].reasons)
        self.assertTrue(self.analyzer.is_known_recipient("RECIPIENT", "CLIENT-1"))
        self.assertEqual(self.analyzer.reports[-1].level, RiskLevel.LOW)
        self.assertEqual(len(self.audit_log.filter(event_type="transaction_processed")), 2)

    def test_large_amount_is_blocked_before_debit(self):
        transaction = Transaction("SENDER", "RECIPIENT", 100_000, "RUB")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.REJECTED)
        self.assertIn("large_amount", transaction.rejection_reason)
        self.assertEqual(self.sender.balance, 500_000)
        self.assertEqual(self.audit_log.events[-1].severity, Severity.CRITICAL)

    def test_blocked_transfer_does_not_make_recipient_trusted(self):
        blocked = Transaction("SENDER", "RECIPIENT", 100_000, "RUB")
        follow_up = Transaction("SENDER", "RECIPIENT", 1_000, "RUB")
        self.processor.process(blocked)
        self.assertEqual(blocked.status, TransactionStatus.REJECTED)
        self.assertFalse(self.analyzer.is_known_recipient("RECIPIENT", "CLIENT-1"))
        self.processor.process(follow_up)
        self.assertIn("new_recipient", self.analyzer.reports[-1].reasons)
        self.assertEqual(follow_up.status, TransactionStatus.COMPLETED)
        self.assertTrue(self.analyzer.is_known_recipient("RECIPIENT", "CLIENT-1"))

    def test_frequent_new_and_night_operations_are_detected(self):
        analyzer = RiskAnalyzer(frequent_count=3)
        time = datetime(2026, 1, 1, 14, 0)
        first = Transaction("SENDER", "A", 100, "RUB", created_at=time)
        second = Transaction("SENDER", "A", 100, "RUB", created_at=time + timedelta(minutes=1))
        third = Transaction("SENDER", "B", 100, "RUB", created_at=time + timedelta(minutes=2))
        night = Transaction("SENDER", "B", 100, "RUB", created_at=datetime(2026, 1, 2, 2))
        # REQ-H4: only completed transfers count towards frequency, so each
        # one must be marked completed and recorded before the next analysis.
        analyzer.analyze(first, "CLIENT-1")
        first.set_status(TransactionStatus.COMPLETED)
        analyzer.record_successful_transaction(first, "CLIENT-1")
        analyzer.analyze(second, "CLIENT-1")
        second.set_status(TransactionStatus.COMPLETED)
        analyzer.record_successful_transaction(second, "CLIENT-1")
        report = analyzer.analyze(third, "CLIENT-1")
        night_report = analyzer.analyze(night, "CLIENT-1")
        self.assertEqual(report.level, RiskLevel.HIGH)
        self.assertIn("frequent_transactions", report.reasons)
        self.assertIn("new_recipient", report.reasons)
        self.assertIn("night_operation", night_report.reasons)

    def test_rejected_transfers_do_not_count_towards_frequency(self):
        """REQ-H4: analyze() alone (without a completed transfer) must not
        inflate the frequency window -- a run of blocked/rejected attempts
        should not make an unrelated later transfer HIGH only because of
        frequency."""
        analyzer = RiskAnalyzer(frequent_count=3)
        time = datetime(2026, 1, 1, 14, 0)
        for index in range(3):
            blocked = Transaction("SENDER", "A", 100, "RUB", created_at=time + timedelta(minutes=index))
            analyzer.analyze(blocked, "CLIENT-1")
            # Never call record_successful_transaction: these were rejected.
        fourth = Transaction("SENDER", "A", 100, "RUB", created_at=time + timedelta(minutes=5))
        report = analyzer.analyze(fourth, "CLIENT-1")
        self.assertNotIn("frequent_transactions", report.reasons)

    def test_audit_log_is_saved_to_file_and_filters_events(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            audit = AuditLog(path)
            audit.log("test", Severity.INFO, "fine", client_id="C1")
            audit.log("failure", Severity.ERROR, "failed", client_id="C1")
            self.assertTrue(path.exists())
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)
            self.assertEqual(len(audit.filter(severity="error", client_id="C1")), 1)
            self.assertEqual(audit.error_statistics(), {"failure": 1})

    def test_is_known_recipient_requires_a_key_and_never_reads_the_shared_bucket(self):
        with self.assertRaises(ValueError):
            self.analyzer.is_known_recipient("RECIPIENT")
        self.assertFalse(self.analyzer.is_known_recipient("RECIPIENT", sender="SENDER"))

    def test_external_transfer_without_matching_account_is_audited_as_settled(self):
        transaction = Transaction(
            "SENDER", "OUTSIDE-IBAN", 1_000, "RUB", TransactionType.EXTERNAL_TRANSFER
        )
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.COMPLETED)
        events = self.audit_log.filter(event_type="external_settled")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].details["recipient"], "OUTSIDE-IBAN")


class BlockedClientTests(unittest.TestCase):
    """REQ-H1: a blocked client's outgoing operations are rejected, but
    incoming transfers to their (still active) accounts still succeed."""

    def setUp(self):
        self.bank = SecureBank()
        self.bank.add_client(Client("Roman", "CLIENT-BLOCKED", 30, {}, "correct-password"))
        self.bank.add_client(Client("Alex", "CLIENT-OTHER", 30, {}, "correct-password"))
        self.sender = self.bank.open_account(
            "CLIENT-BLOCKED", "savings", balance=1_000, currency="RUB",
            account_number="BLOCKED-SENDER",
        )
        self.recipient = self.bank.open_account(
            "CLIENT-OTHER", "savings", balance=500, currency="RUB",
            account_number="OTHER-RECIPIENT",
        )
        for _ in range(3):
            try:
                self.bank.authenticate_client("CLIENT-BLOCKED", "wrong-password")
            except ValueError:
                pass
        self.assertEqual(self.bank.clients["CLIENT-BLOCKED"].status, "blocked")

    def test_direct_withdraw_is_rejected(self):
        with self.assertRaises(InvalidOperationError):
            self.sender.withdraw(100)
        self.assertEqual(self.sender.balance, 1_000)

    def test_outgoing_transfer_is_rejected(self):
        transaction = Transaction("BLOCKED-SENDER", "OTHER-RECIPIENT", 100, "RUB")
        result = self.bank.execute_transaction(transaction)
        self.assertEqual(result.status, TransactionStatus.REJECTED)
        self.assertEqual(self.sender.balance, 1_000)

    def test_incoming_transfer_to_a_blocked_clients_active_account_completes(self):
        transaction = Transaction("OTHER-RECIPIENT", "BLOCKED-SENDER", 50, "RUB")
        result = self.bank.execute_transaction(transaction)
        self.assertEqual(result.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.sender.balance, 1_050)


if __name__ == "__main__":
    unittest.main()
