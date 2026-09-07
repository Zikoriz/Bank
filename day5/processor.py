"""Transaction processor that audits every decision and blocks high risk."""

from day4.processor import TransactionProcessor
from day4.transaction import TransactionStatus

from .audit_log import AuditLog, Severity
from .risk_analyzer import RiskAnalyzer, RiskLevel


class RiskControlledProcessor(TransactionProcessor):
    def __init__(self, *args, audit_log=None, risk_analyzer=None, account_clients=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.audit_log = audit_log or AuditLog()
        self.risk_analyzer = risk_analyzer or RiskAnalyzer()
        self.account_clients = account_clients if account_clients is not None else {}

    def process(self, transaction):
        if transaction.status not in {TransactionStatus.PENDING, TransactionStatus.SCHEDULED}:
            raise ValueError("Transaction is not ready for processing")
        client_id = self.account_clients.get(transaction.sender)
        report = self.risk_analyzer.analyze(transaction, client_id)
        self.audit_log.log("risk_assessment", Severity.WARNING if report.is_suspicious else Severity.INFO,
                           "Transaction risk assessed", transaction_id=transaction.transaction_id,
                           client_id=client_id, risk_level=report.level.value, reasons=list(report.reasons))
        if report.level == RiskLevel.HIGH:
            reason = "Blocked by risk control: " + ", ".join(report.reasons)
            transaction.set_status(TransactionStatus.REJECTED, reason)
            self.audit_log.log("transaction_blocked", Severity.CRITICAL, reason,
                               transaction_id=transaction.transaction_id, client_id=client_id)
            return transaction
        result = super().process(transaction)
        severity = Severity.INFO if result.status == TransactionStatus.COMPLETED else Severity.ERROR
        self.audit_log.log("transaction_processed", severity,
                           "Transaction completed" if severity == Severity.INFO else result.rejection_reason,
                           transaction_id=result.transaction_id, client_id=client_id,
                           status=result.status.value)
        return result

    def audit_reports(self, client_id=None):
        return {"suspicious_transactions": self.risk_analyzer.suspicious_transactions(client_id),
                "client_risk_profile": self.risk_analyzer.client_risk_profile(client_id) if client_id else None,
                "error_statistics": self.audit_log.error_statistics()}
