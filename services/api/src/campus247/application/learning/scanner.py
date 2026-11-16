"""The default file scanner: none is configured, so nothing is published."""
from campus247.domain.learning import LearningError


class UnavailableScanner:
    name = "unavailable"

    async def scan(self, path):
        raise LearningError(503, "SCANNER_UNAVAILABLE", "Chưa có bộ quét tệp; tài liệu chưa được công bố.")
