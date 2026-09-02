from day2.account import SavingsAccount, PremiumAccount, InvestmentAccount
from day1.exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InvalidOperationError,
    InsufficientFundsError,
)


def test_savings_account():
    print("\n=== SAVINGS ACCOUNT ===")

    account = SavingsAccount(
        owner="Roman",
        balance=10000,
        currency="USD",
        min_balance=3000,
        monthly_interest_rate=0.01,
    )

    print(account)

    print("\nПополнение:")
    account.deposit(1000)
    print(account)

    print("\nСнятие:")
    account.withdraw(5000)
    print(account)

    print("\nНачисление процентов:")
    account.apply_monthly_interest()
    print(account)

    print("\nПопытка нарушить min_balance:")
    try:
        account.withdraw(4000)
    except InvalidOperationError as error:
        print(f"Ошибка: {error}")

    print("\nИнформация:")
    print(account.get_account_info())


def test_premium_account():
    print("\n=== PREMIUM ACCOUNT ===")

    account = PremiumAccount(
        owner="Alex",
        balance=1000,
        currency="EUR",
        withdraw_limit=10000,
        overdraft_limit=5000,
        monthly_fee=100,
    )

    print(account)

    print("\nОперация в пределах овердрафта:")
    account.withdraw(4000)
    print(account)

    print("\nОперация снятия с комиссией:")
    account.withdraw(400)
    print(account)

    print("\nПопытка превысить лимит снятия:")
    try:
        account.withdraw(10001)
    except InvalidOperationError as error:
        print(f"Ошибка: {error}")

    print("\nПопытка превысить овердрафт:")
    try:
        account.withdraw(4000)
    except InsufficientFundsError as error:
        print(f"Ошибка: {error}")

    print("\nИнформация:")
    print(account.get_account_info())


def test_investment_account():
    print("\n=== INVESTMENT ACCOUNT ===")

    account = InvestmentAccount(
        owner="Roman",
        balance=5000,
        currency="USD",
        portfolio={
            "stocks": 5000,
            "bonds": 3000,
            "etf": 2000,
        },
    )

    print(account)

    print("\nПрогноз роста:")
    growth = account.project_yearly_growth()

    for asset, data in growth.items():
        print(
            f"{asset}: "
            f"{data['current']} -> "
            f"{data['projected']} "
            f"(рост: {data['growth']})"
        )

    print("\nСнятие:")
    account.withdraw(1000)
    print(account)

    print("\nИнформация:")
    print(account.get_account_info())


def test_frozen_accounts():
    print("\n=== FROZEN ACCOUNT TEST ===")

    account = PremiumAccount(
        owner="Roman",
        balance=1000,
        status="frozen",
        currency="RUB",
    )

    print(account)

    try:
        account.withdraw(100)
    except AccountFrozenError as error:
        print(f"Ошибка: {error}")


def test_closed_accounts():
    print("\n=== CLOSED ACCOUNT TEST ===")

    account = PremiumAccount(
        owner="Roman",
        balance=1000,
        status="closed",
        currency="RUB",
    )

    print(account)

    try:
        account.withdraw(100)
    except AccountClosedError as error:
        print(f"Ошибка: {error}")


def main():
    test_savings_account()
    test_premium_account()
    test_investment_account()
    test_frozen_accounts()
    test_closed_accounts()


if __name__ == "__main__":
    main()