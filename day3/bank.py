from datetime import datetime

from day1.exceptions import AccountClosedError
from day3.client import Client
from day2.account import (
    SavingsAccount,
    PremiumAccount,
    InvestmentAccount,
)


class Bank:
    def __init__(self):
        self.clients = {}
        self.accounts = {}
        self.suspicious_actions = []

    def _check_operation_time(self, current_time=None):
        if current_time is None:
            current_time = datetime.now()

        if 0 <= current_time.hour < 5:
            raise PermissionError(
                "Operations are prohibited from 00:00 to 05:00"
            )

    def add_client(self, client):
        if not isinstance(client, Client):
            raise TypeError("Client must be an instance of Client")

        if client.client_id in self.clients:
            raise ValueError("Client already exists")

        self.clients[client.client_id] = client

    def open_account(
        self,
        client_id,
        account_type,
        balance=0,
        currency="RUB",
        **kwargs
    ):
        self._check_operation_time()

        if client_id not in self.clients:
            raise ValueError("Client not found")

        client = self.clients[client_id]

        if client.status != "active":
            raise ValueError("Client is not active")

        account_classes = {
            "savings": SavingsAccount,
            "premium": PremiumAccount,
            "investment": InvestmentAccount,
        }

        if account_type not in account_classes:
            raise ValueError("Invalid account type")

        account_number = kwargs.get("account_number")

        if account_number is not None:
            if account_number in self.accounts:
                raise ValueError("Account number already exists")

        account_class = account_classes[account_type]

        account = account_class(
            owner=client.full_name,
            balance=balance,
            currency=currency,
            operation_time_checker=self._check_operation_time,
            **kwargs
        )

        if account.account_number in self.accounts:
            raise ValueError("Account number already exists")

        self.accounts[account.account_number] = account
        client.add_account(account.account_number)

        return account

    def close_account(self, account_number):
        self._check_operation_time()

        if account_number not in self.accounts:
            raise ValueError("Account not found")

        account = self.accounts[account_number]

        if account.status == "closed":
            raise AccountClosedError("Account is already closed")

        account.status = "closed"

    def freeze_account(self, account_number):
        self._check_operation_time()

        if account_number not in self.accounts:
            raise ValueError("Account not found")

        account = self.accounts[account_number]

        if account.status == "closed":
            raise AccountClosedError(
                "Cannot freeze a closed account"
            )

        account.status = "frozen"

    def unfreeze_account(self, account_number):
        self._check_operation_time()

        if account_number not in self.accounts:
            raise ValueError("Account not found")

        account = self.accounts[account_number]

        if account.status == "closed":
            raise AccountClosedError(
                "Cannot unfreeze a closed account"
            )

        account.status = "active"

    def authenticate_client(self, client_id, password):
        if client_id not in self.clients:
            raise ValueError("Client not found")

        client = self.clients[client_id]

        if client.status == "blocked":
            raise ValueError("Client is blocked")

        if password == client.password:
            client.failed_attempts = 0
            return True

        client.failed_attempts += 1

        if client.failed_attempts >= 3:
            client.status = "blocked"

            self.suspicious_actions.append({
                "client_id": client_id,
                "action": "multiple_failed_login_attempts",
                "message": "Client blocked after 3 failed attempts"
            })

            raise ValueError(
                "Client blocked after 3 failed attempts"
            )

        raise ValueError("Invalid password")

    def search_accounts(
        self,
        client_id=None,
        account_type=None,
        status=None,
        account_number=None
    ):
        results = []

        account_types = {
            "savings": SavingsAccount,
            "premium": PremiumAccount,
            "investment": InvestmentAccount,
        }

        if account_type is not None:
            account_type = account_type.lower()

            if account_type not in account_types:
                raise ValueError("Invalid account type")

        if status is not None:
            status = status.lower()

        if client_id is not None:
            client = self.clients.get(client_id)

            if client is None:
                raise ValueError("Client not found")

        for number, account in self.accounts.items():
            if account_number is not None:
                if number != account_number:
                    continue

            if client_id is not None:
                if number not in client.account_numbers:
                    continue

            if account_type is not None:
                if not isinstance(account, account_types[account_type]):
                    continue

            if status is not None:
                if account.status != status:
                    continue

            results.append(account)

        return results

    def get_total_balance(self):
        total_balance = {}

        for account in self.accounts.values():
            if account.status == "closed":
                continue

            currency = account.currency

            total_balance[currency] = (
                total_balance.get(currency, 0) + account.balance
            )

        return total_balance

    def get_clients_ranking(self):
        ranking = {}

        for client in self.clients.values():
            for account_number in client.account_numbers:
                account = self.accounts.get(account_number)

                if account is None:
                    continue

                if account.status == "closed":
                    continue

                currency = account.currency

                if currency not in ranking:
                    ranking[currency] = []

                client_entry = None

                for item in ranking[currency]:
                    if item["client_id"] == client.client_id:
                        client_entry = item
                        break

                if client_entry is None:
                    ranking[currency].append({
                        "client_id": client.client_id,
                        "full_name": client.full_name,
                        "balance": account.balance,
                    })
                else:
                    client_entry["balance"] += account.balance

        for currency in ranking:
            ranking[currency].sort(
                key=lambda client: client["balance"],
                reverse=True
            )

        return ranking