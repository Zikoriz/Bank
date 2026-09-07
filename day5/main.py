"""Runnable Day 5 example: normal, suspicious and blocked transfers."""

from pathlib import Path

from day2.account import SavingsAccount
from day4 import Transaction
from day5 import RiskControlledProcessor


def main():
    sender = SavingsAccount("Roman", balance=250_000, currency="RUB", account_number="ROMAN")
    recipient = SavingsAccount("Alex", balance=0, currency="RUB", account_number="ALEX")
    processor = RiskControlledProcessor(
        {"ROMAN": sender, "ALEX": recipient},
        account_clients={"ROMAN": "C001"},
        audit_log=None,
    )
    # Persisting audit records is enabled by assigning a file path when creating AuditLog.
    normal = Transaction("ROMAN", "ALEX", 5_000, "RUB")
    dangerous = Transaction("ROMAN", "ALEX", 150_000, "RUB")
    for transaction in (normal, dangerous):
        processor.process(transaction)
        print(transaction.transaction_id, transaction.status.value, transaction.rejection_reason)
    print(processor.audit_reports("C001"))


if __name__ == "__main__":
    main()
