from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from day2.account import SavingsAccount
from day4 import Transaction, TransactionStatus
from day5 import AuditLog, RiskAnalyzer, RiskControlledProcessor, RiskLevel, Severity


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

    def test_regular_transaction_is_completed_and_audited(self):
        transaction = Transaction("SENDER", "RECIPIENT", 1_000, "RUB")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.analyzer.reports[-1].level, RiskLevel.LOW)
        self.assertEqual(len(self.audit_log.filter(event_type="transaction_processed")), 1)

    def test_large_amount_is_blocked_before_debit(self):
        transaction = Transaction("SENDER", "RECIPIENT", 100_000, "RUB")
        self.processor.process(transaction)
        self.assertEqual(transaction.status, TransactionStatus.REJECTED)
        self.assertIn("large_amount", transaction.rejection_reason)
        self.assertEqual(self.sender.balance, 500_000)
        self.assertEqual(self.audit_log.events[-1].severity, Severity.CRITICAL)

    def test_frequent_new_and_night_operations_are_detected(self):
        analyzer = RiskAnalyzer(frequent_count=3)
        time = datetime(2026, 1, 1, 14, 0)
        first = Transaction("SENDER", "A", 100, "RUB", created_at=time)
        second = Transaction("SENDER", "A", 100, "RUB", created_at=time + timedelta(minutes=1))
        third = Transaction("SENDER", "B", 100, "RUB", created_at=time + timedelta(minutes=2))
        night = Transaction("SENDER", "B", 100, "RUB", created_at=datetime(2026, 1, 2, 2))
        analyzer.analyze(first, "CLIENT-1")
        analyzer.analyze(second, "CLIENT-1")
        report = analyzer.analyze(third, "CLIENT-1")
        night_report = analyzer.analyze(night, "CLIENT-1")
        self.assertEqual(report.level, RiskLevel.HIGH)
        self.assertIn("frequent_transactions", report.reasons)
        self.assertIn("new_recipient", report.reasons)
        self.assertIn("night_operation", night_report.reasons)

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


if __name__ == "__main__":
    unittest.main()
