from .exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InvalidOperationError,
    InsufficientFundsError,
)

from abc import ABC, abstractmethod
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

    def __init__(
        self,
        owner,
        balance=0,
        status="active",
        currency="RUB",
        account_number=None,
        operation_time_checker=None
    ):
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("Owner must be a non-empty string")

        if not isinstance(balance, (int, float)):
            raise TypeError("Balance must be a number")

        if balance < 0:
            raise ValueError("Balance cannot be negative")

        if status not in self.ALLOWED_STATUSES:
            raise ValueError("Invalid account status")

        if currency not in self.ALLOWED_CURRENCIES:
            raise ValueError("Invalid currency")

        if account_number is None:
            account_number = str(uuid.uuid4())[:8]

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

    @property
    def balance(self):
        return self._balance

    def _check_operation_time(self):
        if self._operation_time_checker is not None:
            self._operation_time_checker()

    def _check_account_status(self):
        if self.status == "frozen":
            raise AccountFrozenError("Account is frozen")

        if self.status == "closed":
            raise AccountClosedError("Account is closed")

    def deposit(self, amount):
        self._check_operation_time()
        self._check_account_status()

        if not isinstance(amount, (int, float)):
            raise InvalidOperationError("Amount must be a number")

        if amount <= 0:
            raise InvalidOperationError(
                "Amount must be greater than zero"
            )

        self._balance += amount

    def withdraw(self, amount):
        self._check_operation_time()
        self._check_account_status()

        if not isinstance(amount, (int, float)):
            raise InvalidOperationError("Amount must be a number")

        if amount <= 0:
            raise InvalidOperationError(
                "Amount must be greater than zero"
            )

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