"""Central logging setup for PawPal+ (file + console, secrets never logged)."""

import logging
import os
import re
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "pawpal.log")
_KEY_PATTERN = re.compile(r"(sk-ant-[A-Za-z0-9_\-]+|AIza[A-Za-z0-9_\-]{20,})")


class RedactingFilter(logging.Filter):
    """Mask anything that looks like an API key (Gemini or Anthropic)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _KEY_PATTERN.sub("***", str(record.getMessage()))
        record.args = ()
        return True


def setup_logging(level: int = logging.INFO, log_file: str = LOG_FILE) -> None:
    """Configure the root logger once; calling it again is a no-op."""
    root = logging.getLogger()
    if getattr(root, "_pawpal_configured", False):
        return
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = RotatingFileHandler(log_file, maxBytes=500_000, backupCount=3, encoding="utf-8")
    console = logging.StreamHandler()
    for handler in (file_handler, console):
        handler.setFormatter(fmt)
        handler.addFilter(RedactingFilter())
        root.addHandler(handler)
    root.setLevel(level)
    root._pawpal_configured = True  # type: ignore[attr-defined]
