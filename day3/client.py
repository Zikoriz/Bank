class Client:
    def __init__(self, full_name, client_id, age, contacts, password):
        if not isinstance(full_name, str) or not full_name.strip():
            raise ValueError("Full name must be a non-empty string")

        if not isinstance(age, int):
            raise TypeError("Age must be an integer")

        if age < 18:
            raise ValueError("Client must be at least 18 years old")

        if not isinstance(password, str) or not password:
            raise ValueError("Password must be a non-empty string")

        self.full_name = full_name
        self.client_id = client_id
        self.age = age
        self.contacts = contacts
        self.password = password
        self.status = "active"
        self.account_numbers = []
        self.failed_attempts = 0

    def add_account(self, account_number):
        if account_number not in self.account_numbers:
            self.account_numbers.append(account_number)

    def remove_account(self, account_number):
        if account_number in self.account_numbers:
            self.account_numbers.remove(account_number)