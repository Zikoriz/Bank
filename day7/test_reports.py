import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from day1.exceptions import InvalidOperationError
from day3.bank import Bank
from day3.client import Client
from day6.main import run_demo
from day7 import ReportBuilder


class ReportBuilderTests(unittest.TestCase):
    def setUp(self):
        source = run_demo(verbose=False)
        self.builder = ReportBuilder(source["bank"], source["transactions"], source["risk_analyzer"])

    def test_reports_are_structured_and_text_is_readable(self):
        client = self.builder.client_report("C001")
        bank = self.builder.bank_report()
        risk = self.builder.risk_report()
        self.assertEqual(client["client"]["client_id"], "C001")
        self.assertEqual(bank["summary"]["transaction_count"], 40)
        self.assertEqual(risk["summary"]["suspicious"], 16)
        self.assertIn("CLIENT REPORT", self.builder.text_report(client))
        with self.assertRaises(ValueError):
            self.builder.client_report("UNKNOWN")

    def test_json_csv_and_charts_are_saved(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report = self.builder.bank_report()
            json_path = self.builder.export_to_json(report, directory / "bank.json")
            csv_path = self.builder.export_to_csv(report, directory / "bank.csv")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["report_type"], "bank")
            with csv_path.open(encoding="utf-8-sig", newline="") as file:
                self.assertEqual(len(list(csv.DictReader(file))), 40)
            try:
                charts = self.builder.create_bank_charts()
            except RuntimeError as error:
                self.skipTest(str(error))
            saved = self.builder.save_charts(directory / "charts", charts)
            self.assertEqual(len(saved), 2)
            self.assertTrue(all(path.exists() and path.stat().st_size > 0 for path in saved))

    def test_balance_chart_endpoints_match_a_manual_recomputation(self):
        """REQ-M5: the chart applies the same deltas as the processor
        (``amount + fee`` on the sender, ``converted_amount`` on the
        recipient). Check the first (opening) point against the client's
        actual opening balance (known independently from
        ``day6.main.build_bank``, not derived from the chart itself), and
        the last point against both a manual forward replay and the
        account's real current balance -- not only "the end is pinned to
        current", which would pass even if the per-transaction deltas were
        wrong.
        """
        report = self.builder.client_report("C001")
        accounts = report["client"]["accounts"]
        figure = self.builder._balance_chart(accounts, "regression check")
        axis = figure.axes[0]
        line = next(l for l in axis.get_lines() if l.get_label() == "RUB")
        points = list(line.get_ydata())

        tracked = {account["account_number"] for account in accounts}
        completed = [
            transaction for transaction in self.builder.transactions
            if transaction.status.value == "completed"
            and (transaction.sender in tracked or transaction.recipient in tracked)
        ]
        completed.sort(key=lambda transaction: transaction.created_at)

        # Independently known from day6.main.build_bank(): C001 opens
        # ACC001 with 90_000 and ACC008 with 25_000.
        known_opening = Decimal("115000")
        running = known_opening
        for transaction in completed:
            if transaction.sender in tracked:
                running -= transaction.amount + transaction.fee
            if transaction.recipient in tracked:
                running += (
                    transaction.converted_amount
                    if transaction.converted_amount is not None else transaction.amount
                )

        self.assertAlmostEqual(points[0], float(known_opening), places=6)
        self.assertAlmostEqual(points[-1], float(running), places=6)
        self.assertAlmostEqual(
            points[-1], float(sum(account["balance"] for account in accounts)), places=6
        )


class ClosedAccountReportingTests(unittest.TestCase):
    """REQ-C3: one rule for Bank and ReportBuilder aggregates."""

    def setUp(self):
        self.bank = Bank()
        self.bank.add_client(Client("Roman", "C1", 30, {}, "password"))
        self.account = self.bank.open_account(
            "C1", "savings", balance=1_000, currency="RUB", account_number="ACC1"
        )
        self.other_account = self.bank.open_account(
            "C1", "savings", balance=500, currency="RUB", account_number="ACC2"
        )

    def test_closing_a_nonzero_balance_account_is_rejected(self):
        with self.assertRaises(InvalidOperationError):
            self.bank.close_account("ACC1")
        self.assertEqual(self.bank.get_total_balance(), {"RUB": 1_500})

    def test_closed_zero_balance_account_is_excluded_from_both_aggregates(self):
        self.account.withdraw(1_000)
        self.bank.close_account("ACC1")

        builder = ReportBuilder(self.bank)
        bank_report = builder.bank_report()
        client_report = builder.client_report("C1")

        self.assertEqual(self.bank.get_total_balance(), {"RUB": 500})
        self.assertEqual(
            self.bank.get_total_balance(), bank_report["summary"]["balances_by_currency"]
        )
        self.assertEqual(
            self.bank.get_total_balance(), client_report["client"]["balances_by_currency"]
        )
        # The closed account's balance is not hidden, just excluded from sums.
        self.assertEqual(len(bank_report["accounts"]), 2)


if __name__ == "__main__":
    unittest.main()
