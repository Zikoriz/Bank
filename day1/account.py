from .exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InvalidOperationError,
    InsufficientFundsError,
)

from abc import ABC, abstractmethod
import math
import uuid


class AbstractAccount(ABC):
    def __init__(self, account_number, owner, balance, status):
        self.account_number = account_number
        self.owner = owner
        self._balance = balance
        self.status = status

    @abstractmethod
    def deposit(self, amount):
        pass

    @abstractmethod
    def withdraw(self, amount):
        pass

    @abstractmethod
    def get_account_info(self):
        pass


class BankAccount(AbstractAccount):
    ALLOWED_CURRENCIES = {"RUB", "USD", "EUR", "KZT", "CNY"}
    ALLOWED_STATUSES = {"active", "frozen", "closed"}

    # Allowed status transitions (REQ-M3): active <-> frozen, active -> closed.
    # frozen -> closed is forbidden here; unfreeze first, then close.
    _STATUS_TRANSITIONS = {
        "active": {"frozen", "closed"},
        "frozen": {"active"},
        "closed": set(),
    }

    def __init__(
        self,
        owner,
        balance=0,
        status="active",
        currency="RUB",
        account_number=None,
        operation_time_checker=None,
        client_status_checker=None,
    ):
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("Owner must be a non-empty string")

        if not isinstance(balance, (int, float)) or isinstance(balance, bool):
            raise TypeError("Balance must be a number")

        if balance < 0:
            raise ValueError("Balance cannot be negative")

        if status not in self.ALLOWED_STATUSES:
            raise ValueError("Invalid account status")

        if currency not in self.ALLOWED_CURRENCIES:
            raise ValueError("Invalid currency")

        if account_number is None:
            account_number = str(uuid.uuid4())

        if not isinstance(account_number, str):
            raise TypeError("Account number must be a string")

        if not account_number.strip():
            raise ValueError("Account number cannot be empty")

        if len(account_number) < 4:
            raise ValueError(
                "Account number must contain at least 4 characters"
            )

        super().__init__(
            account_number=account_number,
            owner=owner,
            balance=balance,
            status=status
        )

        self.currency = currency
        self._operation_time_checker = operation_time_checker
        self._client_status_checker = client_status_checker

    @property
    def balance(self):
        return self._balance

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if value not in self.ALLOWED_STATUSES:
            raise ValueError("Invalid account status")

        current = getattr(self, "_status", None)

        if current is None:
            self._status = value
            return

        if value == current:
            raise InvalidOperationError(f"Account is already {value}")

        if value not in self._STATUS_TRANSITIONS[current]:
            raise InvalidOperationError(
                f"Cannot change account status from {current} to {value}"
            )

        self._status = value

    @staticmethod
    def _validate_amount(amount):
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise InvalidOperationError("Amount must be a number")

        if not math.isfinite(amount):
            raise InvalidOperationError("Amount must be a finite number")

        if amount <= 0:
            raise InvalidOperationError(
                "Amount must be greater than zero"
            )

    def _check_operation_time(self):
        if self._operation_time_checker is not None:
            self._operation_time_checker()

    def _check_account_status(self):
        if self.status == "frozen":
            raise AccountFrozenError("Account is frozen")

        if self.status == "closed":
            raise AccountClosedError("Account is closed")

    def _check_withdraw_allowed(self):
        """Guards that apply only to outgoing money movement (REQ-H1)."""
        self._check_operation_time()
        self._check_account_status()

        if self._client_status_checker is not None:
            self._client_status_checker()

    def deposit(self, amount):
        self._check_operation_time()
        self._check_account_status()
        self._validate_amount(amount)

        self._balance += amount

    def withdraw(self, amount):
        self._check_withdraw_allowed()
        self._validate_amount(amount)

        if amount > self._balance:
            raise InsufficientFundsError("Insufficient funds")

        self._balance -= amount

    def __str__(self):
        last_four = self.account_number[-4:]

        return (
            f"BankAccount | "
            f"Client: {self.owner} | "
            f"****{last_four} | "
            f"Status: {self.status} | "
            f"Balance: {self._balance} {self.currency}"
        )

    def get_account_info(self):
        return {
            "account_number": self.account_number,
            "owner": self.owner,
            "balance": self._balance,
            "status": self.status,
            "currency": self.currency,
        }
