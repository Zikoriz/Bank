"""Rules for identifying suspicious banking transactions."""

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum

from day4.transaction import to_money


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class RiskReport:
    transaction_id: str
    client_id: str | None
    level: RiskLevel
    reasons: tuple[str, ...]
    analyzed_at: object

    @property
    def is_suspicious(self):
        return self.level != RiskLevel.LOW


class RiskAnalyzer:
    """Stateful rule engine. High-risk reports are intended to be blocked."""

    def __init__(self, large_amount="100000", frequent_count=3, frequent_window_minutes=10,
                 night_start=0, night_end=5):
        self.large_amount = to_money(large_amount, "large_amount")
        self.frequent_count = frequent_count
        self.frequent_window = timedelta(minutes=frequent_window_minutes)
        self.night_start, self.night_end = night_start, night_end
        self._transactions_by_client = defaultdict(deque)
        self._known_recipients = defaultdict(set)
        self.reports: list[RiskReport] = []

    def analyze(self, transaction, client_id=None, at=None):
        """Analyze and record one transaction; ``at`` makes testing deterministic."""
        at = at or transaction.created_at
        client_key = client_id or transaction.sender
        reasons = []
        if transaction.amount >= self.large_amount:
            reasons.append("large_amount")

        history = self._transactions_by_client[client_key]
        cutoff = at - self.frequent_window
        while history and history[0] < cutoff:
            history.popleft()
        # Current transaction makes the configured number of transfers in the window.
        if len(history) + 1 >= self.frequent_count:
            reasons.append("frequent_transactions")

        recipients = self._known_recipients[client_key]
        if recipients and transaction.recipient not in recipients:
            reasons.append("new_recipient")
        if self._is_night(at.hour):
            reasons.append("night_operation")

        # Any two signals, a large amount, or frequency at night/new recipient is high.
        level = RiskLevel.LOW
        if "large_amount" in reasons or len(reasons) >= 2:
            level = RiskLevel.HIGH
        elif reasons:
            level = RiskLevel.MEDIUM

        history.append(at)
        recipients.add(transaction.recipient)
        report = RiskReport(transaction.transaction_id, client_id, level, tuple(reasons), at)
        self.reports.append(report)
        return report

    def suspicious_transactions(self, client_id=None):
        return [report for report in self.reports if report.is_suspicious and
                (client_id is None or report.client_id == client_id)]

    def client_risk_profile(self, client_id):
        reports = [report for report in self.reports if report.client_id == client_id]
        counts = {level.value: sum(report.level == level for report in reports) for level in RiskLevel}
        highest = next((level for level in (RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW)
                        if counts[level.value]), RiskLevel.LOW)
        return {"client_id": client_id, "transactions": len(reports),
                "risk_counts": counts, "risk_level": highest.value}

    def _is_night(self, hour):
        if self.night_start <= self.night_end:
            return self.night_start <= hour < self.night_end
        return hour >= self.night_start or hour < self.night_end
