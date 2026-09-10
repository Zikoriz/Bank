import unittest

from day4 import TransactionStatus
from day6.main import run_demo


class Day6DemoTests(unittest.TestCase):
    def test_end_to_end_demo_contains_all_required_outcomes(self):
        report = run_demo(verbose=False)

        self.assertEqual(len(report["bank"].clients), 7)
        self.assertEqual(len(report["bank"].accounts), 12)
        self.assertEqual(len(report["transactions"]), 40)
        self.assertEqual(report["statistics"], {"completed": 31, "rejected": 9})
        self.assertEqual(len(report["suspicious"]), 16)
        self.assertEqual(len(report["top_clients"]), 3)
        self.assertEqual(len(report["audit_log"].filter(event_type="transaction_queued")), 40)
        self.assertTrue(any(item.status == TransactionStatus.REJECTED for item in report["transactions"]))


if __name__ == "__main__":
    unittest.main()
