from __future__ import annotations

import logging
from collections.abc import Iterable


class SecretRedactingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str]):
        super().__init__()
        self.secrets = [secret for secret in secrets if secret]

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(record.getMessage())
        record.args = ()
        return True

    def _redact(self, text: str) -> str:
        redacted = text
        for secret in self.secrets:
            redacted = redacted.replace(secret, "[REDACTED]")
        return redacted


def configure_logging(level: str = "INFO", secrets: Iterable[str] = ()) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    redactor = SecretRedactingFilter(secrets)
    for logger_name in ("", "youtube_daily_update"):
        logging.getLogger(logger_name).addFilter(redactor)
