from datetime import datetime

from day3.bank import Bank
from day3.client import Client
from day1.exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InvalidOperationError,
)


def test_clients_and_accounts(bank):
    print("\n=== CLIENTS ===")

    client_1 = Client(
        full_name="Roman Ivanov",
        client_id="C001",
        age=19,
        contacts={
            "phone": "+37100000000",
            "email": "roman@example.com"
        },
        password="12345"
    )

    client_2 = Client(
        full_name="Alex Petrov",
        client_id="C002",
        age=30,
        contacts={
            "phone": "+37111111111",
            "email": "alex@example.com"
        },
        password="54321"
    )

    bank.add_client(client_1)
    bank.add_client(client_2)

    print(bank.clients)

    print("\n=== ACCOUNTS ===")

    savings_account = bank.open_account(
        client_id="C001",
        account_type="savings",
        balance=10000,
        currency="USD",
        min_balance=3000,
        monthly_interest_rate=0.01
    )

    premium_account = bank.open_account(
        client_id="C001",
        account_type="premium",
        balance=5000,
        currency="EUR",
        withdraw_limit=10000,
        overdraft_limit=5000,
        monthly_fee=100
    )

    investment_account = bank.open_account(
        client_id="C002",
        account_type="investment",
        balance=7000,
        currency="USD",
        portfolio={
            "stocks": 5000,
            "bonds": 3000,
            "etf": 2000
        }
    )

    print(savings_account)
    print(premium_account)
    print(investment_account)

    print("\n=== CLIENT ACCOUNT NUMBERS ===")
    print(f"{client_1.full_name}: {client_1.account_numbers}")
    print(f"{client_2.full_name}: {client_2.account_numbers}")

    return (
        client_1,
        client_2,
        savings_account,
        premium_account,
        investment_account
    )


def test_freeze_and_unfreeze(bank, account):
    print("\n=== FREEZE ACCOUNT ===")

    bank.freeze_account(account.account_number)

    print(account)

    try:
        account.withdraw(100)
    except AccountFrozenError as error:
        print(f"Ошибка: {error}")

    print("\n=== UNFREEZE ACCOUNT ===")

    bank.unfreeze_account(account.account_number)

    print(account)

    account.withdraw(1000)

    print("После снятия 1000:")
    print(account)


def test_close_account(bank, client, account):
    print("\n=== CLOSE ACCOUNT ===")

    print("До закрытия:")
    print(f"Счета клиента: {client.account_numbers}")

    bank.close_account(account.account_number)

    print("После закрытия:")
    print(account)
    print(f"Счета клиента: {client.account_numbers}")

    try:
        bank.unfreeze_account(account.account_number)
    except AccountClosedError as error:
        print(f"Ошибка: {error}")


def test_invalid_account(bank):
    print("\n=== INVALID ACCOUNT ===")

    try:
        bank.freeze_account("UNKNOWN123")
    except ValueError as error:
        print(f"Ошибка: {error}")


def test_duplicate_account_number(bank):
    print("\n=== DUPLICATE ACCOUNT NUMBER ===")

    account_number = "DUPLICATE1"

    try:
        bank.open_account(
            client_id="C001",
            account_type="savings",
            balance=5000,
            currency="USD",
            account_number=account_number,
            min_balance=1000,
            monthly_interest_rate=0.01
        )

        bank.open_account(
            client_id="C002",
            account_type="savings",
            balance=3000,
            currency="USD",
            account_number=account_number,
            min_balance=1000,
            monthly_interest_rate=0.01
        )

    except ValueError as error:
        print(f"Ошибка: {error}")


def test_authentication(bank, client_1, client_2):
    print("\n=== AUTHENTICATION ===")

    try:
        result = bank.authenticate_client(
            client_1.client_id,
            "12345"
        )
        print(f"Успешный вход: {result}")
    except ValueError as error:
        print(f"Ошибка: {error}")

    print("\n=== FAILED AUTHENTICATION ===")

    for attempt in range(1, 4):
        try:
            bank.authenticate_client(
                client_2.client_id,
                "wrong"
            )
        except ValueError as error:
            print(f"Попытка {attempt}: {error}")

    print(f"Статус клиента: {client_2.status}")

    try:
        bank.authenticate_client(
            client_2.client_id,
            "54321"
        )
    except ValueError as error:
        print(f"После блокировки: {error}")

    print("\n=== SUSPICIOUS ACTIONS ===")
    print(bank.suspicious_actions)


def test_night_restriction(bank):
    print("\n=== NIGHT RESTRICTION ===")

    night_time = datetime(2026, 8, 30, 2, 30)

    try:
        bank._check_operation_time(night_time)
        print("Операция разрешена")
    except PermissionError as error:
        print(f"Ошибка: {error}")


def test_search_and_statistics(bank, client_1, savings_account):
    print("\n=== SEARCH ACCOUNTS ===")

    print("\nСчета Roman:")
    for account in bank.search_accounts(client_id="C001"):
        print(account)

    print("\nSavings счета:")
    for account in bank.search_accounts(account_type="savings"):
        print(account)

    print("\nPremium счета:")
    for account in bank.search_accounts(account_type="premium"):
        print(account)

    print("\nInvestment счета:")
    for account in bank.search_accounts(account_type="investment"):
        print(account)

    print("\nАктивные счета:")
    for account in bank.search_accounts(status="active"):
        print(account)

    print("\nПоиск по номеру:")
    for account in bank.search_accounts(
        account_number=savings_account.account_number
    ):
        print(account)

    print("\n=== TOTAL BALANCE ===")
    print(f"Общий баланс по валютам: {bank.get_total_balance()}")

    print("\n=== CLIENTS RANKING ===")
    for client in bank.get_clients_ranking():
        print(client)


def test_client_age_validation():
    print("\n=== CLIENT AGE VALIDATION ===")

    try:
        Client(
            full_name="Test User",
            client_id="C003",
            age=17,
            contacts={},
            password="12345"
        )
    except ValueError as error:
        print(f"Ошибка: {error}")


def main():
    bank = Bank()

    (
        client_1,
        client_2,
        savings_account,
        premium_account,
        investment_account
    ) = test_clients_and_accounts(bank)

    test_freeze_and_unfreeze(
        bank,
        savings_account
    )

    test_close_account(
        bank,
        client_1,
        premium_account
    )

    test_invalid_account(bank)

    test_duplicate_account_number(bank)

    test_authentication(
        bank,
        client_1,
        client_2
    )

    test_night_restriction(bank)

    test_search_and_statistics(
        bank,
        client_1,
        savings_account
    )

    test_client_age_validation()


if __name__ == "__main__":
    main()