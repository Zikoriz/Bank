from .account import BankAccount
from .exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InsufficientFundsError,
)


def main():
    # Создаём активный счёт
    active_account = BankAccount(
        owner="Roman",
        balance=1000,
        currency="USD"
    )

    # Создаём замороженный счёт
    frozen_account = BankAccount(
        owner="Alex",
        balance=500,
        status="frozen",
        currency="EUR"
    )

    print("=== Активный счёт ===")
    print(active_account)
    print(active_account.get_account_info())

    print("\n=== Замороженный счёт ===")
    print(frozen_account)
    print(frozen_account.get_account_info())

    # Пополнение
    print("\n=== Пополнение ===")
    active_account.deposit(500)
    print(active_account.get_account_info())

    # Снятие
    print("\n=== Снятие ===")
    active_account.withdraw(300)
    print(active_account.get_account_info())

    # Попытка операции над замороженным счётом
    print("\n=== Операция над замороженным счётом ===")
    try:
        frozen_account.deposit(100)
    except AccountFrozenError as error:
        print(f"Ошибка: {error}")

    # Попытка снять больше доступного баланса
    print("\n=== Недостаточно средств ===")
    try:
        active_account.withdraw(5000)
    except InsufficientFundsError as error:
        print(f"Ошибка: {error}")


if __name__ == "__main__":
    main()