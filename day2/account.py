from day1.account import BankAccount
from day1.exceptions import (
    InvalidOperationError,
    InsufficientFundsError,
)


class SavingsAccount(BankAccount):
    def __init__(
        self,
        owner,
        balance=0,
        status="active",
        currency="RUB",
        account_number=None,
        min_balance=0,
        monthly_interest_rate=0,
        operation_time_checker=None,
        client_status_checker=None,
    ):
        if not isinstance(min_balance, (int, float)):
            raise TypeError("Minimum balance must be a number")

        if min_balance < 0:
            raise ValueError("Minimum balance cannot be negative")

        if not isinstance(monthly_interest_rate, (int, float)):
            raise TypeError("Interest rate must be a number")

        if monthly_interest_rate < 0:
            raise ValueError("Interest rate cannot be negative")

        if monthly_interest_rate > 1:
            raise ValueError(
                "Interest rate must be a fraction between 0 and 1"
            )

        if balance < min_balance:
            raise ValueError("Balance cannot be less than minimum balance")

        super().__init__(
            owner=owner,
            balance=balance,
            status=status,
            currency=currency,
            account_number=account_number,
            operation_time_checker=operation_time_checker,
            client_status_checker=client_status_checker,
        )

        self.min_balance = min_balance
        self.monthly_interest_rate = monthly_interest_rate

    def withdraw(self, amount):
        self._check_withdraw_allowed()
        self._validate_amount(amount)

        if amount > self._balance:
            raise InsufficientFundsError("Insufficient funds")

        if self._balance - amount < self.min_balance:
            raise InvalidOperationError(
                "Withdrawal would violate minimum balance"
            )

        self._balance -= amount

    def apply_monthly_interest(self):
        self._check_operation_time()
        self._check_account_status()

        interest = self._balance * self.monthly_interest_rate
        self._balance += interest

    def get_account_info(self):
        info = super().get_account_info()
        info.update({
            "min_balance": self.min_balance,
            "monthly_interest_rate": self.monthly_interest_rate
        })
        return info

    def __str__(self):
        last_four = self.account_number[-4:]

        return (
            f"SavingsAccount | "
            f"Client: {self.owner} | "
            f"****{last_four} | "
            f"Status: {self.status} | "
            f"Balance: {self._balance} {self.currency} | "
            f"Min balance: {self.min_balance} | "
            f"Interest rate: {self.monthly_interest_rate}"
        )


class PremiumAccount(BankAccount):
    def __init__(
        self,
        owner,
        balance=0,
        status="active",
        currency="RUB",
        account_number=None,
        withdraw_limit=10000,
        overdraft_limit=5000,
        monthly_fee=100,
        operation_time_checker=None,
        client_status_checker=None,
    ):
        if not isinstance(withdraw_limit, (int, float)):
            raise TypeError("Withdraw limit must be a number")

        if withdraw_limit <= 0:
            raise ValueError("Withdraw limit must be greater than zero")

        if not isinstance(overdraft_limit, (int, float)):
            raise TypeError("Overdraft limit must be a number")

        if overdraft_limit < 0:
            raise ValueError("Overdraft limit cannot be negative")

        if not isinstance(monthly_fee, (int, float)):
            raise TypeError("Monthly fee must be a number")

        if monthly_fee < 0:
            raise ValueError("Monthly fee cannot be negative")

        super().__init__(
            owner=owner,
            balance=balance,
            status=status,
            currency=currency,
            account_number=account_number,
            operation_time_checker=operation_time_checker,
            client_status_checker=client_status_checker,
        )

        self.withdraw_limit = withdraw_limit
        self.overdraft_limit = overdraft_limit
        self.monthly_fee = monthly_fee

    def withdraw(self, amount):
        """Withdraw exactly ``amount``.

        The monthly fee is a separate charge (REQ-C1) applied only through
        ``apply_monthly_fee``; it must never be folded into a transfer debit.
        """
        self._check_withdraw_allowed()
        self._validate_amount(amount)

        if amount > self.withdraw_limit:
            raise InvalidOperationError(
                "Withdrawal limit exceeded"
            )

        if self._balance - amount < -self.overdraft_limit:
            raise InsufficientFundsError(
                "Overdraft limit exceeded"
            )

        self._balance -= amount

    def apply_monthly_fee(self):
        """Charge the periodic account-maintenance fee.

        This is independent of any transfer/withdrawal and must be invoked
        explicitly (e.g. once per billing period), never implicitly from
        ``withdraw``.
        """
        self._check_operation_time()
        self._check_account_status()

        if self._balance - self.monthly_fee < -self.overdraft_limit:
            raise InsufficientFundsError(
                "Overdraft limit exceeded"
            )

        self._balance -= self.monthly_fee

    def get_account_info(self):
        info = super().get_account_info()
        info.update({
            "withdraw_limit": self.withdraw_limit,
            "overdraft_limit": self.overdraft_limit,
            "monthly_fee": self.monthly_fee
        })
        return info

    def __str__(self):
        last_four = self.account_number[-4:]

        return (
            f"PremiumAccount | "
            f"Client: {self.owner} | "
            f"****{last_four} | "
            f"Status: {self.status} | "
            f"Balance: {self._balance} {self.currency} | "
            f"Withdraw limit: {self.withdraw_limit} | "
            f"Overdraft: {self.overdraft_limit} | "
            f"Monthly fee: {self.monthly_fee}"
        )


class InvestmentAccount(BankAccount):
    ASSET_TYPES = {"stocks", "bonds", "etf"}

    DEFAULT_GROWTH_RATES = {
        "stocks": 0.10,
        "bonds": 0.04,
        "etf": 0.07,
    }

    def __init__(
        self,
        owner,
        balance=0,
        status="active",
        currency="RUB",
        account_number=None,
        portfolio=None,
        operation_time_checker=None,
        client_status_checker=None,
    ):
        super().__init__(
            owner=owner,
            balance=balance,
            status=status,
            currency=currency,
            account_number=account_number,
            operation_time_checker=operation_time_checker,
            client_status_checker=client_status_checker,
        )

        if portfolio is None:
            portfolio = {}

        if not isinstance(portfolio, dict):
            raise TypeError("Portfolio must be a dictionary")

        for asset, amount in portfolio.items():
            if asset not in self.ASSET_TYPES:
                raise ValueError(f"Invalid asset type: {asset}")

            if not isinstance(amount, (int, float)):
                raise TypeError(
                    f"Amount for {asset} must be a number"
                )

            if amount <= 0:
                raise ValueError(
                    f"Amount for {asset} must be greater than zero"
                )

        if sum(portfolio.values()) > balance:
            raise ValueError(
                "Portfolio total exceeds available balance"
            )

        self._portfolio = portfolio.copy()

    @property
    def portfolio(self):
        """Read-only view; use the constructor to set the initial allocation."""
        return dict(self._portfolio)

    @property
    def allocated(self):
        return sum(self._portfolio.values())

    @property
    def available(self):
        """Cash that is not tied up in the portfolio (REQ-C2 / I4)."""
        return self._balance - self.allocated

    def withdraw(self, amount):
        """Withdraw from free cash only; the invested portfolio is untouched."""
        self._check_withdraw_allowed()
        self._validate_amount(amount)

        if amount > self.available:
            raise InsufficientFundsError(
                "Insufficient available (non-invested) funds"
            )

        self._balance -= amount

    def project_yearly_growth(self, growth_rates=None):
        if growth_rates is None:
            growth_rates = self.DEFAULT_GROWTH_RATES

        if not isinstance(growth_rates, dict):
            raise TypeError("growth_rates must be a dictionary")

        for asset, rate in growth_rates.items():
            if asset not in self.ASSET_TYPES:
                raise ValueError(f"Invalid asset type: {asset}")

            if not isinstance(rate, (int, float)):
                raise TypeError(
                    f"Growth rate for {asset} must be a number"
                )

        projected_growth = {}

        for asset, amount in self._portfolio.items():
            if asset not in growth_rates:
                raise ValueError(
                    f"Missing growth rate for asset: {asset}"
                )

            rate = growth_rates[asset]
            growth = amount * rate

            projected_growth[asset] = {
                "current": amount,
                "growth": growth,
                "projected": amount + growth,
            }

        return projected_growth

    def get_account_info(self):
        info = super().get_account_info()
        info.update({
            "portfolio": self.portfolio,
            "allocated": self.allocated,
            "available": self.available,
            "projected_yearly_growth": self.project_yearly_growth()
        })
        return info

    def __str__(self):
        last_four = self.account_number[-4:]

        return (
            f"InvestmentAccount | "
            f"Client: {self.owner} | "
            f"****{last_four} | "
            f"Status: {self.status} | "
            f"Balance: {self._balance} {self.currency} | "
            f"Portfolio: {self.portfolio}"
        )
