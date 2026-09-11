"""Build exportable reports and charts from the banking domain objects.

The builder deliberately only reads the bank, transactions and risk analyser.
It can therefore be used both with the Day 6 demo and with a real application
without changing the transfer-processing code.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class ReportBuilder:
    """Create client, bank and risk reports in text, JSON, CSV and PNG form.

    Parameters are intentionally permissive: ``transactions`` may be any
    iterable of Day 4 ``Transaction`` objects and ``risk_analyzer`` may be a
    Day 5 ``RiskAnalyzer``.  Supplying neither still allows account-only bank
    reports to be generated.
    """

    def __init__(self, bank, transactions: Iterable[Any] = (), risk_analyzer=None):
        self.bank = bank
        self.transactions = list(transactions)
        self.risk_analyzer = risk_analyzer
        self.charts: dict[str, Any] = {}

    # -- structured reports -------------------------------------------------

    def client_report(self, client_id: str) -> dict[str, Any]:
        """Return a structured report for one client.

        A transaction is included when the client's account is either sender
        or recipient; this makes incoming transfers visible as well.
        """
        client = self._client(client_id)
        account_numbers = set(client.account_numbers)
        accounts = [self._account_data(self.bank.accounts[number])
                    for number in client.account_numbers if number in self.bank.accounts]
        transactions = [transaction for transaction in self.transactions
                        if transaction.sender in account_numbers or transaction.recipient in account_numbers]
        sent = [transaction for transaction in transactions if transaction.sender in account_numbers]
        received = [transaction for transaction in transactions if transaction.recipient in account_numbers]

        return {
            "report_type": "client",
            "generated_at": datetime.now(),
            "client": {
                "client_id": client.client_id,
                "full_name": client.full_name,
                "status": client.status,
                "accounts": accounts,
                "balances_by_currency": self._balances_by_currency(accounts),
            },
            "transactions": [self._transaction_data(item) for item in transactions],
            "summary": {
                "transactions": len(transactions),
                "sent_transactions": len(sent),
                "received_transactions": len(received),
                "sent_amounts_by_currency": self._amounts_by_currency(sent),
                "received_amounts_by_currency": self._amounts_by_currency(received),
                "statuses": self._status_counts(transactions),
            },
            "risk": self._client_risk(client_id),
        }

    def bank_report(self) -> dict[str, Any]:
        """Return an aggregate report over all clients and accounts."""
        accounts = [self._account_data(account) for account in self.bank.accounts.values()]
        clients = []
        for client in self.bank.clients.values():
            client_accounts = [account for account in accounts
                               if account["account_number"] in client.account_numbers]
            clients.append({
                "client_id": client.client_id,
                "full_name": client.full_name,
                "status": client.status,
                "account_count": len(client_accounts),
                "balances_by_currency": self._balances_by_currency(client_accounts),
            })
        return {
            "report_type": "bank",
            "generated_at": datetime.now(),
            "summary": {
                "clients": len(clients),
                "accounts": len(accounts),
                "balances_by_currency": self._balances_by_currency(accounts),
                "transaction_count": len(self.transactions),
                "statuses": self._status_counts(self.transactions),
                "transaction_amounts_by_currency": self._amounts_by_currency(self.transactions),
            },
            "clients": clients,
            "accounts": accounts,
            "transactions": [self._transaction_data(item) for item in self.transactions],
        }

    def risk_report(self, client_id: str | None = None) -> dict[str, Any]:
        """Return all suspicious-risk decisions, optionally for one client."""
        reports = self._risk_reports(client_id)
        level_counts = Counter(self._value(report.level) for report in reports)
        reason_counts = Counter(reason for report in reports for reason in report.reasons)
        return {
            "report_type": "risk",
            "generated_at": datetime.now(),
            "client_id": client_id,
            "summary": {
                "assessments": len(reports),
                "suspicious": sum(self._value(report.level) != "low" for report in reports),
                "by_level": dict(sorted(level_counts.items())),
                "by_reason": dict(sorted(reason_counts.items())),
            },
            "risk_assessments": [self._risk_data(report) for report in reports],
        }

    # Readable aliases make the public API discoverable in coursework.
    generate_client_report = client_report
    generate_bank_report = bank_report
    generate_risk_report = risk_report

    def text_report(self, report: dict[str, Any]) -> str:
        """Render a compact, human-readable representation of any report."""
        report_type = report["report_type"]
        lines = [f"{report_type.upper()} REPORT", f"Generated: {self._format(report['generated_at'])}"]
        if report_type == "client":
            client = report["client"]
            lines.extend((
                f"Client: {client['full_name']} ({client['client_id']})",
                f"Accounts: {len(client['accounts'])}",
                f"Balances: {self._format_money_map(client['balances_by_currency'])}",
                f"Transactions: {report['summary']['transactions']} ({self._format_counts(report['summary']['statuses'])})",
                f"Risk level: {report['risk']['risk_level']}",
            ))
        elif report_type == "bank":
            summary = report["summary"]
            lines.extend((
                f"Clients: {summary['clients']}; accounts: {summary['accounts']}",
                f"Balances: {self._format_money_map(summary['balances_by_currency'])}",
                f"Transactions: {summary['transaction_count']} ({self._format_counts(summary['statuses'])})",
            ))
        elif report_type == "risk":
            summary = report["summary"]
            lines.extend((
                f"Assessments: {summary['assessments']}; suspicious: {summary['suspicious']}",
                f"Levels: {self._format_counts(summary['by_level'])}",
                f"Reasons: {self._format_counts(summary['by_reason']) or 'none'}",
            ))
        else:
            raise ValueError(f"Unknown report type: {report_type}")
        return "\n".join(lines)

    generate_text_report = text_report

    # -- exports ------------------------------------------------------------

    def export_to_json(self, report: dict[str, Any], path: str | Path) -> Path:
        """Save a report as UTF-8 JSON and return its path."""
        destination = self._prepare_destination(path)
        with destination.open("w", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=2, default=self._json_default)
        return destination

    def export_to_csv(self, report: dict[str, Any], path: str | Path) -> Path:
        """Save the primary rows of a report as an Excel-friendly UTF-8 CSV."""
        destination = self._prepare_destination(path)
        rows = self._csv_rows(report)
        fieldnames = list(dict.fromkeys(key for row in rows for key in row)) or ["report_type"]
        with destination.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return destination

    # -- charts -------------------------------------------------------------

    def create_client_charts(self, client_id: str) -> dict[str, Any]:
        """Create a balance pie chart and balance-movement line chart."""
        report = self.client_report(client_id)
        client = report["client"]
        charts = {
            f"client_{client_id}_balances": self._pie_chart(
                client["balances_by_currency"], f"Balances: {client['full_name']}"),
            f"client_{client_id}_balance_history": self._balance_chart(
                client["accounts"], f"Balance movement: {client['full_name']}"),
        }
        self.charts.update(charts)
        return charts

    def create_charts(self, report_type: str, client_id: str | None = None) -> dict[str, Any]:
        """Create the standard chart set for ``client``, ``bank`` or ``risk``."""
        if report_type == "client":
            if client_id is None:
                raise ValueError("client_id is required for a client chart")
            return self.create_client_charts(client_id)
        if report_type == "bank":
            return self.create_bank_charts()
        if report_type == "risk":
            return self.create_risk_charts(client_id)
        raise ValueError("report_type must be 'client', 'bank' or 'risk'")

    def create_bank_charts(self) -> dict[str, Any]:
        """Create a client-balance bar chart and a bank balance-history chart."""
        rows = []
        for client in self.bank.clients.values():
            total = sum((self._decimal(self.bank.accounts[number].balance)
                         for number in client.account_numbers if number in self.bank.accounts), Decimal("0"))
            rows.append((client.full_name, total))
        charts = {
            "bank_client_balances": self._bar_chart(rows, "Client balances"),
            "bank_balance_history": self._balance_chart(
                [self._account_data(account) for account in self.bank.accounts.values()],
                "Bank balance movement"),
        }
        self.charts.update(charts)
        return charts

    def create_risk_charts(self, client_id: str | None = None) -> dict[str, Any]:
        """Create pie and bar charts for risk levels and triggering rules."""
        report = self.risk_report(client_id)
        charts = {
            "risk_levels": self._pie_chart(report["summary"]["by_level"], "Risk assessments by level"),
            "risk_reasons": self._bar_chart(list(report["summary"]["by_reason"].items()), "Risk triggers"),
        }
        self.charts.update(charts)
        return charts

    def save_charts(self, directory: str | Path, charts: dict[str, Any] | None = None) -> list[Path]:
        """Save chart figures to ``directory`` as PNG files and return paths."""
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        selected = self.charts if charts is None else charts
        saved = []
        for name, figure in selected.items():
            path = destination / f"{name}.png"
            figure.savefig(path, dpi=150, bbox_inches="tight")
            saved.append(path)
        return saved

    # -- conversion helpers -------------------------------------------------

    def _client(self, client_id):
        try:
            return self.bank.clients[client_id]
        except KeyError as error:
            raise ValueError("Client not found") from error

    @staticmethod
    def _account_data(account):
        return {"account_number": account.account_number, "owner": account.owner,
                "balance": account.balance, "currency": account.currency, "status": account.status}

    @staticmethod
    def _transaction_data(transaction):
        return {
            "transaction_id": transaction.transaction_id, "sender": transaction.sender,
            "recipient": transaction.recipient, "amount": transaction.amount,
            "fee": transaction.fee, "currency": transaction.currency,
            "status": ReportBuilder._value(transaction.status),
            "created_at": transaction.created_at, "processed_at": transaction.processed_at,
            "rejection_reason": transaction.rejection_reason,
        }

    def _client_risk(self, client_id):
        if self.risk_analyzer is None:
            return {"client_id": client_id, "transactions": 0,
                    "risk_counts": {"low": 0, "medium": 0, "high": 0}, "risk_level": "low"}
        return self.risk_analyzer.client_risk_profile(client_id)

    def _risk_reports(self, client_id=None):
        if self.risk_analyzer is None:
            return []
        return [report for report in self.risk_analyzer.reports
                if client_id is None or report.client_id == client_id]

    @staticmethod
    def _risk_data(report):
        return {"transaction_id": report.transaction_id, "client_id": report.client_id,
                "level": ReportBuilder._value(report.level), "reasons": list(report.reasons),
                "analyzed_at": report.analyzed_at}

    @staticmethod
    def _balances_by_currency(accounts):
        totals = defaultdict(lambda: Decimal("0"))
        for account in accounts:
            totals[account["currency"]] += ReportBuilder._decimal(account["balance"])
        return dict(sorted(totals.items()))

    @staticmethod
    def _amounts_by_currency(transactions):
        totals = defaultdict(lambda: Decimal("0"))
        for transaction in transactions:
            totals[transaction.currency] += ReportBuilder._decimal(transaction.amount)
        return dict(sorted(totals.items()))

    @staticmethod
    def _status_counts(transactions):
        return dict(sorted(Counter(ReportBuilder._value(item.status) for item in transactions).items()))

    def _csv_rows(self, report):
        kind = report["report_type"]
        if kind == "client":
            return [self._flat({"report_type": kind, "client_id": report["client"]["client_id"]}, row)
                    for row in report["transactions"]]
        if kind == "bank":
            return [self._flat({"report_type": kind}, row) for row in report["transactions"]]
        if kind == "risk":
            return [self._flat({"report_type": kind}, row) for row in report["risk_assessments"]]
        raise ValueError(f"Unknown report type: {kind}")

    @staticmethod
    def _flat(prefix, row):
        return {**prefix, **{key: ReportBuilder._csv_value(value) for key, value in row.items()}}

    @staticmethod
    def _csv_value(value):
        if isinstance(value, (list, tuple)):
            return "; ".join(str(item) for item in value)
        if isinstance(value, (dict, Decimal, datetime, date, Enum)):
            return ReportBuilder._json_default(value)
        return value

    @staticmethod
    def _prepare_destination(path):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    @staticmethod
    def _json_default(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        raise TypeError(f"{type(value).__name__} is not JSON serializable")

    @staticmethod
    def _decimal(value):
        return value if isinstance(value, Decimal) else Decimal(str(value))

    @staticmethod
    def _value(value):
        return value.value if isinstance(value, Enum) else value

    @staticmethod
    def _format(value):
        return value.isoformat(sep=" ", timespec="seconds") if isinstance(value, datetime) else str(value)

    @staticmethod
    def _format_counts(values):
        return ", ".join(f"{key}: {value}" for key, value in values.items())

    @staticmethod
    def _format_money_map(values):
        return ", ".join(f"{amount} {currency}" for currency, amount in values.items()) or "0"

    @staticmethod
    def _plt():
        """Load matplotlib only when a chart is requested."""
        try:
            # Some restricted environments do not permit a user-profile cache.
            # A dedicated temporary cache keeps chart generation quiet and
            # works in CI without changing the caller's configuration.
            config_dir = Path(tempfile.gettempdir()) / "pet-llm-matplotlib"
            config_dir.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("MPLCONFIGDIR", str(config_dir))
            import matplotlib
            matplotlib.use("Agg", force=True)
            import matplotlib.pyplot as plt
        except ImportError as error:
            raise RuntimeError("Charts require matplotlib. Install it with: pip install matplotlib") from error
        return plt

    def _pie_chart(self, values, title):
        plt = self._plt()
        figure, axis = plt.subplots(figsize=(7, 4.5))
        labels, numbers = zip(*((str(key), float(value)) for key, value in values.items() if value), strict=False) if values else ((), ())
        if numbers:
            axis.pie(numbers, labels=labels, autopct="%1.1f%%", startangle=90)
        else:
            axis.text(0.5, 0.5, "No data", ha="center", va="center")
        axis.set_title(title)
        axis.axis("equal")
        return figure

    def create_pie_chart(self, values: dict[str, Any], title: str = "Distribution"):
        """Create one reusable pie chart from named numeric values."""
        return self._pie_chart(values, title)

    def _bar_chart(self, values, title):
        plt = self._plt()
        figure, axis = plt.subplots(figsize=(8, 4.5))
        labels = [str(label) for label, _value in values]
        numbers = [float(value) for _label, value in values]
        if numbers:
            axis.bar(labels, numbers)
            axis.tick_params(axis="x", rotation=35)
        else:
            axis.text(0.5, 0.5, "No data", ha="center", va="center")
        axis.set_title(title)
        axis.set_ylabel("Amount")
        figure.tight_layout()
        return figure

    def create_bar_chart(self, values: dict[str, Any], title: str = "Comparison"):
        """Create one reusable bar chart from named numeric values."""
        return self._bar_chart(list(values.items()), title)

    def _balance_chart(self, accounts, title):
        """Reconstruct balance movement from completed transactions.

        The transaction model stores final account balances but not snapshots.
        Reversing completed transfer deltas yields a deterministic opening
        balance, then each chronological transfer contributes one point.
        """
        plt = self._plt()
        tracked = {account["account_number"]: self._decimal(account["balance"]) for account in accounts}
        deltas = defaultdict(lambda: Decimal("0"))
        completed = [item for item in self.transactions
                     if self._value(item.status) == "completed" and
                     (item.sender in tracked or item.recipient in tracked)]
        for transaction in completed:
            if transaction.sender in tracked:
                deltas[transaction.sender] -= self._decimal(transaction.amount) + self._decimal(transaction.fee)
            if transaction.recipient in tracked:
                deltas[transaction.recipient] += self._decimal(
                    transaction.converted_amount if transaction.converted_amount is not None else transaction.amount)
        current = sum(tracked.values(), Decimal("0"))
        opening = current - sum(deltas.values(), Decimal("0"))
        points = [("Opening", float(opening))]
        running = opening
        for transaction in sorted(completed, key=lambda item: item.created_at):
            delta = Decimal("0")
            if transaction.sender in tracked:
                delta -= self._decimal(transaction.amount) + self._decimal(transaction.fee)
            if transaction.recipient in tracked:
                delta += self._decimal(transaction.converted_amount if transaction.converted_amount is not None else transaction.amount)
            running += delta
            points.append((transaction.created_at, float(running)))
        figure, axis = plt.subplots(figsize=(8, 4.5))
        axis.plot(range(len(points)), [value for _label, value in points], marker="o")
        axis.set_title(title)
        axis.set_xlabel("Operations")
        axis.set_ylabel("Balance")
        axis.set_xticks(range(len(points)))
        axis.set_xticklabels(["Opening" if index == 0 else str(index) for index, _point in enumerate(points)], rotation=0)
        axis.grid(True, alpha=0.3)
        figure.tight_layout()
        return figure

    def create_balance_chart(self, client_id: str | None = None):
        """Create a balance movement line chart for a client or the whole bank."""
        if client_id is None:
            accounts = [self._account_data(account) for account in self.bank.accounts.values()]
            return self._balance_chart(accounts, "Bank balance movement")
        client = self._client(client_id)
        accounts = [self._account_data(self.bank.accounts[number])
                    for number in client.account_numbers if number in self.bank.accounts]
        return self._balance_chart(accounts, f"Balance movement: {client.full_name}")
