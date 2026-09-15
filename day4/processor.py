"""Transaction execution, fee calculation, currency conversion and auditing."""

from decimal import ROUND_HALF_UP, Decimal

from day1.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
)

from .transaction import Transaction, TransactionStatus, to_money

# Accounts (day1/day2) still store balances as float. Every amount is
# quantized to whole cents with a documented rounding policy before it
# crosses that boundary, so e.g. Decimal("0.1") + Decimal("0.2") settles as
# a clean 0.30 instead of a binary-float artifact (REQ-H2).
MONEY_QUANTUM = Decimal("0.01")
MONEY_ROUNDING = ROUND_HALF_UP


class TransactionProcessor:
    def __init__(
        self,
        accounts=None,
        exchange_rates=None,
        external_fee_rate="0.01",
    ):
        self.accounts = accounts if accounts is not None else {}
        self.exchange_rates = {
            (source.upper(), target.upper()): to_money(rate, "exchange rate")
            for (source, target), rate in (exchange_rates or {}).items()
        }
        self.external_fee_rate = to_money(external_fee_rate, "external fee rate")
        if self.external_fee_rate < 0:
            raise ValueError("external fee rate cannot be negative")
        self.error_log = []

    @classmethod
    def from_bank(cls, bank, **kwargs):
        return cls(accounts=bank.accounts, **kwargs)

    def calculate_fee(self, transaction):
        if not isinstance(transaction, Transaction):
            raise TypeError("transaction must be an instance of Transaction")
        return transaction.amount * self.external_fee_rate if transaction.is_external else Decimal("0")

    def process(self, transaction):
        if transaction.status not in {TransactionStatus.PENDING, TransactionStatus.SCHEDULED}:
            raise ValueError("Transaction is not ready for processing")
        while True:
            transaction.attempts += 1
            transaction.set_status(TransactionStatus.PROCESSING)
            try:
                self._process_once(transaction)
            except (
                AccountFrozenError,
                AccountClosedError,
                InsufficientFundsError,
                InvalidOperationError,
                PermissionError,
                ValueError,
                TypeError,
            ) as error:
                self._reject(transaction, str(error))
                return transaction
            except Exception as error:  # operational faults may be transient
                self._record_error(transaction, error)
                if transaction.attempts <= transaction.max_retries:
                    transaction.set_status(TransactionStatus.PENDING)
                    continue
                self._reject(transaction, str(error))
                return transaction
            # REQ-M6: a cancellation that raced in during processing wins.
            if transaction.status != TransactionStatus.CANCELLED:
                transaction.set_status(TransactionStatus.COMPLETED)
            return transaction

    def process_queue(self, queue, now=None):
        results = []
        while (transaction := queue.get_next(now)) is not None:
            results.append(self.process(transaction))
        return results

    def _process_once(self, transaction):
        # REQ-M2: reject before any account is touched.
        if transaction.sender == transaction.recipient:
            raise InvalidOperationError(
                "Sender and recipient accounts must differ"
            )

        sender = self._account(transaction.sender)
        self._validate_account(sender, "Sender")

        recipient = self.accounts.get(transaction.recipient)
        # REQ-M1 (M1-A): only a real (internal) transfer requires the
        # recipient to exist in this ledger. An external transfer may target
        # a recipient outside it; crediting that "outside world" is a no-op
        # here, and the audit layer above records an ``external_settled``
        # event when it sees a completed external transfer with no
        # matching account.
        if recipient is None and not transaction.is_external:
            raise ValueError(f"Account not found: {transaction.recipient}")

        if recipient is not None:
            self._validate_account(recipient, "Recipient")

        if sender.currency != transaction.currency:
            raise ValueError("Transaction currency must match sender account currency")

        transaction.fee = self.calculate_fee(transaction)
        credited = (
            self._convert(transaction.amount, sender.currency, recipient.currency)
            if recipient is not None else transaction.amount
        )

        debited = False
        try:
            self._debit(sender, transaction.total_debit)
            debited = True
            if recipient is not None:
                self._credit(recipient, credited)
        except Exception:
            if debited:
                self._credit(sender, transaction.total_debit)
            raise
        transaction.converted_amount = credited
        transaction.destination_currency = (
            recipient.currency if recipient is not None else transaction.currency
        )

    def _account(self, account_number):
        account = self.accounts.get(account_number)
        if account is None:
            raise ValueError(f"Account not found: {account_number}")
        return account

    @staticmethod
    def _validate_account(account, role):
        if account.status == "frozen":
            raise AccountFrozenError(f"{role} account is frozen")
        if account.status == "closed":
            raise AccountClosedError(f"{role} account is closed")

    @staticmethod
    def _quantize(amount):
        """Round to whole cents (ROUND_HALF_UP) before crossing into a
        float-based account balance (REQ-H2)."""
        return amount.quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)

    @classmethod
    def _debit(cls, account, amount):
        """Withdraw through the account's domain rules."""
        account.withdraw(float(cls._quantize(amount)))

    @classmethod
    def _credit(cls, account, amount):
        """Deposit through the account's domain rules."""
        account.deposit(float(cls._quantize(amount)))

    def _convert(self, amount, source_currency, target_currency):
        if source_currency == target_currency:
            return amount
        try:
            rate = self.exchange_rates[(source_currency, target_currency)]
        except KeyError as error:
            raise ValueError(f"Exchange rate not found: {source_currency}/{target_currency}") from error
        if rate <= 0:
            raise ValueError("Exchange rate must be greater than zero")
        return amount * rate

    def _record_error(self, transaction, error):
        self.error_log.append({
            "transaction_id": transaction.transaction_id,
            "attempt": transaction.attempts,
            "error": str(error),
            "timestamp": transaction.updated_at,
        })

    def _reject(self, transaction, reason):
        self._record_error(transaction, RuntimeError(reason))
        transaction.set_status(TransactionStatus.REJECTED, reason)
