import csv
import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
