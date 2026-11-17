"""Cache/reviews use the existing business transaction, including certificates."""
from campus247.infrastructure.repositories.sqlite_service_operations import OperationsTransaction
from campus247.application.knowledge.operations import digest
from campus247.application.document_request.certificates import CertificateError


class StaffWorkspaceRepository:
    def read(self, tx, key):
        value = OperationsTransaction(tx.connection).item("staff_workspace", key)
        if value is not None:
            checksum = value.pop("checksum", None)
            if value.get("id") != key or checksum != digest(value):
                raise CertificateError(503, "STAFF_CACHE_CORRUPT", "Cache chưa xác minh được; giữ dữ liệu và nháp để đối chiếu")
        return value

    def write(self, tx, value):
        value = {**value, "checksum": digest(value)}
        operations = OperationsTransaction(tx.connection)
        if operations.item("staff_workspace", value["id"]) is None:
            operations.insert("staff_workspace", value)
        else:
            operations.update("staff_workspace", value)

    def replay(self, tx, key):
        value = OperationsTransaction(tx.connection).item("staff_review_receipt", key)
        if value is not None:
            checksum = value.pop("checksum", None)
            if value.get("id") != key or checksum != digest(value):
                raise CertificateError(503, "STAFF_RECEIPT_CORRUPT", "Receipt chưa xác minh được; giữ dữ liệu để đối chiếu")
        return value

    def receipt(self, tx, value):
        OperationsTransaction(tx.connection).insert("staff_review_receipt", {**value, "checksum": digest(value)})
