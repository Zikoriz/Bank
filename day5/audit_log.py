"""Append-only audit journal stored in memory and optionally as JSON Lines."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    severity: Severity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    transaction_id: str | None = None
    client_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        result = asdict(self)
        result["severity"] = self.severity.value
        result["timestamp"] = self.timestamp.isoformat()
        return result


class AuditLog:
    """Keeps events in memory and, when requested, persists each event to JSONL."""

    def __init__(self, file_path=None):
        self.events: list[AuditEvent] = []
        self.file_path = Path(file_path) if file_path else None

    def log(self, event_type, severity=Severity.INFO, message="", **context):
        """Create an event. ``transaction_id`` and ``client_id`` are optional context."""
        event = AuditEvent(
            event_type=event_type,
            severity=Severity(severity),
            message=message,
            transaction_id=context.pop("transaction_id", None),
            client_id=context.pop("client_id", None),
            details=context,
        )
        self.events.append(event)
        if self.file_path:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.file_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str) + "\n")
        return event

    def filter(self, severity=None, event_type=None, transaction_id=None, client_id=None,
               start_at=None, end_at=None):
        """Return audit events matching all supplied filters."""
        severity = Severity(severity) if severity is not None else None
        return [event for event in self.events if (
            (severity is None or event.severity == severity)
            and (event_type is None or event.event_type == event_type)
            and (transaction_id is None or event.transaction_id == transaction_id)
            and (client_id is None or event.client_id == client_id)
            and (start_at is None or event.timestamp >= start_at)
            and (end_at is None or event.timestamp <= end_at)
        )]

    def error_statistics(self):
        """Count error and critical events grouped by their type."""
        result = {}
        for event in self.events:
            if event.severity in {Severity.ERROR, Severity.CRITICAL}:
                result[event.event_type] = result.get(event.event_type, 0) + 1
        return result
