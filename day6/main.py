"""Run a complete, reproducible demonstration of the banking system.

Run from the project root with ``python -m day6.main``.  Use
``--audit-file audit.jsonl`` to additionally save the audit journal.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from day3.client import Client
from day4 import Transaction, TransactionQueue, TransactionStatus
from day5 import AuditLog, RiskAnalyzer, RiskControlledProcessor, SecureBank


class DemoBank(SecureBank):
    """A bank whose clock check is disabled so the example runs at any hour."""

    def _check_operation_time(self, current_time=None):
        return None


CLIENTS = (
    ("C001", "Анна Белова"), ("C002", "Борис Волков"),
    ("C003", "Вера Орлова"), ("C004", "Глеб Морозов"),
    ("C005", "Дарья Соколова"), ("C006", "Егор Лебедев"),
    ("C007", "Жанна Крылова"),
)


def build_bank():
    """Create seven clients and twelve numbered RUB accounts."""
    bank = DemoBank()
    for client_id, name in CLIENTS:
        bank.add_client(Client(name, client_id, 30, {"email": f"{client_id}@demo.bank"}, "demo-password"))

    accounts = []
    for index, (client_id, _name) in enumerate(CLIENTS, start=1):
        account = bank.open_account(
            client_id, "savings", balance=80_000 + index * 10_000,
            account_number=f"ACC{index:03d}",
        )
        accounts.append(account.account_number)
    for index, client_id in enumerate(("C001", "C002", "C003", "C004", "C005"), start=8):
        account = bank.open_account(
            client_id, "savings", balance=25_000,
            account_number=f"ACC{index:03d}",
        )
        accounts.append(account.account_number)
    return bank, accounts


def transaction_plan(accounts):
    """Return 40 requests: ordinary, suspicious and intentionally invalid."""
    created = datetime(2026, 1, 15, 12, 0)
    requests = []

    def add(sender, recipient, amount, currency="RUB", minutes=5, label="normal"):
        nonlocal created
        requests.append((Transaction(sender, recipient, amount, currency, created_at=created), label))
        created += timedelta(minutes=minutes)

    # The first successful transfer for each pair makes the recipient trusted.
    for index in range(12):
        add(accounts[index % 7], accounts[(index + 1) % 7], 1_000)
    for index in range(16):
        add(accounts[index % 7], accounts[(index + 1) % 7], 2_000 + index * 100)

    # Five high-risk transfers are blocked before any money leaves an account.
    for index in range(5):
        add(accounts[index], accounts[(index + 1) % 7], 150_000, label="high risk")

    # Rejections caused by normal banking validation, not only by risk rules.
    add("MISSING", accounts[1], 500, label="invalid account")
    add(accounts[0], accounts[1], 99_000, label="insufficient funds")
    add(accounts[1], accounts[2], 1_000, "USD", label="currency mismatch")
    add(accounts[2], accounts[3], 1_000, label="frozen recipient")

    # Medium-risk requests are still executed and remain visible in the report.
    add(accounts[3], accounts[8], 1_200, label="new recipient")
    add(accounts[4], accounts[9], 1_300, label="new recipient")
    add(accounts[5], accounts[10], 1_400, label="new recipient")
    return requests


def _client_id_by_account(bank):
    return {
        number: client.client_id
        for client in bank.clients.values()
        for number in client.account_numbers
    }


def run_demo(audit_file=None, verbose=True):
    """Execute the scenario and return its data for tests or other UI layers."""
    bank, accounts = build_bank()
    audit_log = AuditLog(audit_file)
    processor = RiskControlledProcessor(
        bank.accounts,
        audit_log=audit_log,
        risk_analyzer=RiskAnalyzer(large_amount=100_000, frequent_count=3),
        account_clients=_client_id_by_account(bank),
    )
    queue = TransactionQueue()
    planned = transaction_plan(accounts)

    labels_by_transaction_id = {}
    for transaction, label in planned:
        # A FIFO queue preserves the scenario: recipients first become trusted,
        # then deliberately risky and invalid requests are demonstrated.
        queue.add(transaction)
        labels_by_transaction_id[transaction.transaction_id] = label
        audit_log.log("transaction_queued", "info", "Transaction added to queue",
                      transaction_id=transaction.transaction_id, label=label)

    results = []
    while (transaction := queue.get_next(datetime.max)) is not None:
        label = labels_by_transaction_id[transaction.transaction_id]
        if label == "frozen recipient":
            bank.freeze_account(transaction.recipient)
        results.append(processor.process(transaction))
        if label == "frozen recipient":
            bank.unfreeze_account(transaction.recipient)

    report = make_report(bank, results, processor.risk_analyzer, audit_log)
    if verbose:
        print_report(report)
    return report


def make_report(bank, transactions, risk_analyzer, audit_log):
    statuses = Counter(transaction.status.value for transaction in transactions)
    history = defaultdict(list)
    account_clients = _client_id_by_account(bank)
    for transaction in transactions:
        client_id = account_clients.get(transaction.sender, "UNKNOWN")
        history[client_id].append(transaction)
    ranking = bank.get_clients_ranking().get("RUB", [])[:3]
    return {
        "bank": bank,
        "transactions": transactions,
        "audit_log": audit_log,
        "statistics": dict(statuses),
        "history": dict(history),
        "suspicious": risk_analyzer.suspicious_transactions(),
        "risk_analyzer": risk_analyzer,
        "top_clients": ranking,
        "total_balance": bank.get_total_balance(),
    }


def print_report(report):
    bank = report["bank"]
    transactions = report["transactions"]
    audit_log = report["audit_log"]
    client = bank.clients["C001"]
    print("=== ДЕНЬ 6: ДЕМОНСТРАЦИЯ БАНКОВСКОЙ СИСТЕМЫ ===")
    print(f"Банк: {len(bank.clients)} клиентов, {len(bank.accounts)} счетов")
    print(f"Очередь: добавлено {len(transactions)} операций; исполнено {report['statistics'].get('completed', 0)}")
    print(f"Отклонено: {report['statistics'].get('rejected', 0)}")
    print(f"Записей аудита: {len(audit_log.events)} (в очереди: {len(audit_log.filter(event_type='transaction_queued'))})")
    print("\nСчета клиента C001 (Анна Белова):")
    for account in bank.search_accounts(client_id=client.client_id):
        print(f"  {account.account_number}: {account.balance} {account.currency} ({account.status})")
    print("\nИстория C001:")
    for transaction in report["history"].get("C001", []):
        reason = f" — {transaction.rejection_reason}" if transaction.rejection_reason else ""
        print(f"  {transaction.transaction_id[:8]}: {transaction.amount} {transaction.currency}, {transaction.status.value}{reason}")
    print(f"\nПодозрительные операции: {len(report['suspicious'])}")
    for item in report["suspicious"][:5]:
        print(f"  {item.transaction_id[:8]}: {item.level.value} ({', '.join(item.reasons)})")
    print("\nТоп-3 клиентов (RUB):")
    for place, item in enumerate(report["top_clients"], start=1):
        print(f"  {place}. {item['full_name']}: {item['balance']} RUB")
    print(f"\nСтатистика транзакций: {report['statistics']}")
    print(f"Общий баланс: {report['total_balance']}")
    print(f"Ошибки аудита: {audit_log.error_statistics()}")


def main():
    parser = argparse.ArgumentParser(description="Day 6 banking system demonstration")
    parser.add_argument("--audit-file", type=Path, help="Path to JSONL audit journal")
    args = parser.parse_args()
    run_demo(args.audit_file)


if __name__ == "__main__":
    main()
