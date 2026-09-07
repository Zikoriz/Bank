"""Bank facade that makes risk control part of transfer execution."""

from day3.bank import Bank

from .audit_log import AuditLog
from .processor import RiskControlledProcessor
from .risk_analyzer import RiskAnalyzer


class SecureBank(Bank):
    def __init__(self, audit_file=None, risk_analyzer=None, **processor_options):
        super().__init__()
        self.audit_log = AuditLog(audit_file)
        self.risk_analyzer = risk_analyzer or RiskAnalyzer()
        self.processor_options = processor_options

    def execute_transaction(self, transaction):
        account_clients = {number: client.client_id for client in self.clients.values()
                           for number in client.account_numbers}
        processor = RiskControlledProcessor(
            accounts=self.accounts, audit_log=self.audit_log, risk_analyzer=self.risk_analyzer,
            account_clients=account_clients, **self.processor_options)
        return processor.process(transaction)

    def audit_reports(self, client_id=None):
        return {"suspicious_transactions": self.risk_analyzer.suspicious_transactions(client_id),
                "client_risk_profile": self.risk_analyzer.client_risk_profile(client_id) if client_id else None,
                "error_statistics": self.audit_log.error_statistics()}
