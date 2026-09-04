"""Transaction execution, fee calculation, currency conversion and auditing."""

from decimal import Decimal

from day1.exceptions import AccountClosedError, AccountFrozenError, InsufficientFundsError
from day2.account import PremiumAccount

from .transaction import Transaction, TransactionStatus, to_money


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
            except (AccountFrozenError, AccountClosedError, InsufficientFundsError, ValueError, TypeError) as error:
                self._reject(transaction, str(error))
                return transaction
            except Exception as error:  # operational faults may be transient
                self._record_error(transaction, error)
                if transaction.attempts <= transaction.max_retries:
                    transaction.set_status(TransactionStatus.PENDING)
                    continue
                self._reject(transaction, str(error))
                return transaction
            transaction.set_status(TransactionStatus.COMPLETED)
            return transaction

    def process_queue(self, queue, now=None):
        results = []
        while (transaction := queue.get_next(now)) is not None:
            results.append(self.process(transaction))
        return results

    def _process_once(self, transaction):
        sender = self._account(transaction.sender)
        recipient = self._account(transaction.recipient)
        self._validate_account(sender, "Sender")
        self._validate_account(recipient, "Recipient")
        if sender.currency != transaction.currency:
            raise ValueError("Transaction currency must match sender account currency")

        transaction.fee = self.calculate_fee(transaction)
        self._debit(sender, transaction.total_debit)
        try:
            credited = self._convert(transaction.amount, sender.currency, recipient.currency)
            self._credit(recipient, credited)
        except Exception:
            sender._balance += float(transaction.total_debit)
            raise
        transaction.converted_amount = credited
        transaction.destination_currency = recipient.currency

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
    def _balance(account):
        return to_money(account.balance, "account balance")

    def _debit(self, account, amount):
        balance_after = self._balance(account) - amount
        if isinstance(account, PremiumAccount):
            if balance_after < -to_money(account.overdraft_limit, "overdraft limit"):
                raise InsufficientFundsError("Overdraft limit exceeded")
        elif balance_after < 0:
            raise InsufficientFundsError("Insufficient funds")
        account._balance = float(balance_after)

    @staticmethod
    def _credit(account, amount):
        account._balance = float(to_money(account.balance, "account balance") + amount)

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
