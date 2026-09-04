"""Модель банковской транзакции."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional
from uuid import uuid4


class TransactionType(str, Enum):
    TRANSFER = "transfer"
    EXTERNAL_TRANSFER = "external_transfer"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


def to_money(value, field_name="amount"):
    """Convert a numeric value to a non-lossy monetary Decimal."""
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise TypeError(f"{field_name} must be a number") from error
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


@dataclass
class Transaction:
    """A transfer request and its complete processing state."""

    sender: str
    recipient: str
    amount: Decimal
    currency: str
    transaction_type: TransactionType | str = TransactionType.TRANSFER
    fee: Decimal = Decimal("0")
    transaction_id: str = field(default_factory=lambda: uuid4().hex)
    status: TransactionStatus = TransactionStatus.PENDING
    rejection_reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    priority: int = 0
    attempts: int = 0
    max_retries: int = 0
    converted_amount: Optional[Decimal] = None
    destination_currency: Optional[str] = None

    def __post_init__(self):
        self.amount = to_money(self.amount)
        self.fee = to_money(self.fee, "fee")
        if self.amount <= 0:
            raise ValueError("amount must be greater than zero")
        if self.fee < 0:
            raise ValueError("fee cannot be negative")
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError("currency must be a non-empty string")
        self.currency = self.currency.upper()
        if not isinstance(self.sender, str) or not self.sender.strip():
            raise ValueError("sender must be a non-empty account number")
        if not isinstance(self.recipient, str) or not self.recipient.strip():
            raise ValueError("recipient must be a non-empty account number")
        self.transaction_type = TransactionType(self.transaction_type)
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")

    @property
    def is_external(self):
        return self.transaction_type == TransactionType.EXTERNAL_TRANSFER

    @property
    def total_debit(self):
        return self.amount + self.fee

    def set_status(self, status, reason=None):
        self.status = TransactionStatus(status)
        self.updated_at = datetime.now()
        if reason is not None:
            self.rejection_reason = reason
        if self.status in {TransactionStatus.COMPLETED, TransactionStatus.REJECTED}:
            self.processed_at = self.updated_at

