"""Small runnable example for Day 4."""

from day2.account import PremiumAccount, SavingsAccount
from day4 import Transaction, TransactionProcessor, TransactionQueue, TransactionType


def main():
    sender = PremiumAccount("Roman", balance=1000, currency="USD", account_number="SENDER01")
    recipient = SavingsAccount("Alex", balance=0, currency="EUR", account_number="RECIP01")
    queue = TransactionQueue()
    transaction = Transaction(
        sender="SENDER01",
        recipient="RECIP01",
        amount=100,
        currency="USD",
        transaction_type=TransactionType.EXTERNAL_TRANSFER,
        priority=10,
    )
    queue.add(transaction)
    processor = TransactionProcessor(
        {sender.account_number: sender, recipient.account_number: recipient},
        exchange_rates={("USD", "EUR"): "0.9"},
    )
    processor.process_queue(queue)
    print(transaction)
    print(sender.get_account_info())
    print(recipient.get_account_info())


if __name__ == "__main__":
    main()
