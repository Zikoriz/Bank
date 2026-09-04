"""Priority queue supporting scheduled and cancelled transactions."""

import heapq
import itertools
from datetime import datetime

from .transaction import Transaction, TransactionStatus


class TransactionQueue:
    def __init__(self):
        self._items = []
        self._sequence = itertools.count()
        self._transactions = {}

    def add(self, transaction, priority=None, scheduled_at=None):
        if not isinstance(transaction, Transaction):
            raise TypeError("transaction must be an instance of Transaction")
        if transaction.transaction_id in self._transactions:
            raise ValueError("Transaction already added")
        if transaction.status != TransactionStatus.PENDING:
            raise ValueError("Only pending transactions can be queued")
        if priority is not None:
            transaction.priority = priority
        if not isinstance(transaction.priority, int):
            raise TypeError("priority must be an integer")
        if scheduled_at is not None:
            if not isinstance(scheduled_at, datetime):
                raise TypeError("scheduled_at must be datetime")
            transaction.scheduled_at = scheduled_at
        if transaction.scheduled_at is not None and transaction.scheduled_at > datetime.now():
            transaction.set_status(TransactionStatus.SCHEDULED)
        self._transactions[transaction.transaction_id] = transaction
        self._push(transaction)
        return transaction.transaction_id

    def _push(self, transaction):
        execute_at = transaction.scheduled_at or datetime.min
        heapq.heappush(
            self._items,
            (execute_at, -transaction.priority, next(self._sequence), transaction.transaction_id),
        )

    def postpone(self, transaction_id, scheduled_at):
        if not isinstance(scheduled_at, datetime):
            raise TypeError("scheduled_at must be datetime")
        transaction = self._get_active(transaction_id)
        transaction.scheduled_at = scheduled_at
        transaction.set_status(TransactionStatus.SCHEDULED)
        self._push(transaction)

    def cancel(self, transaction_id, reason="Cancelled by user"):
        transaction = self._get_active(transaction_id)
        transaction.set_status(TransactionStatus.CANCELLED, reason)

    def get_next(self, now=None):
        """Return the next due transaction or ``None`` without losing future jobs."""
        now = now or datetime.now()
        while self._items:
            execute_at, _priority, _order, transaction_id = self._items[0]
            transaction = self._transactions[transaction_id]
            if transaction.status == TransactionStatus.CANCELLED:
                heapq.heappop(self._items)
                continue
            if transaction.scheduled_at != (None if execute_at == datetime.min else execute_at):
                heapq.heappop(self._items)  # stale item after postponement
                continue
            if execute_at > now:
                return None
            heapq.heappop(self._items)
            if transaction.status == TransactionStatus.SCHEDULED:
                transaction.set_status(TransactionStatus.PENDING)
            return transaction
        return None

    def _get_active(self, transaction_id):
        transaction = self._transactions.get(transaction_id)
        if transaction is None:
            raise ValueError("Transaction not found")
        if transaction.status in {
            TransactionStatus.CANCELLED,
            TransactionStatus.COMPLETED,
            TransactionStatus.REJECTED,
        }:
            raise ValueError("Transaction can no longer be changed")
        return transaction

    def __len__(self):
        return sum(
            transaction.status in {TransactionStatus.PENDING, TransactionStatus.SCHEDULED}
            for transaction in self._transactions.values()
        )
