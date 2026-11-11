"""
Structured Logging Configuration
Ensures sensitive tokens, passwords, and secrets are masked from all log outputs.
"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Set

# Patterns that indicate sensitive secrets
SENSITIVE_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE),
    re.compile(r"(UPSTOX_API_SECRET[=:\s]+)[A-Za-z0-9_\-]{8,}", re.IGNORECASE),
    re.compile(r"(UPSTOX_ACCESS_TOKEN[=:\s]+)[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"(TELEGRAM_BOT_TOKEN[=:\s]+)[A-Za-z0-9_\-:]{20,}", re.IGNORECASE),
    re.compile(r"(ey[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,})"),  # JWT
]


class SecretMaskingFilter(logging.Filter):
    """Filter that masks sensitive tokens from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.mask_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._sanitize_value(v) for v in record.args)
        return True

    @staticmethod
    def mask_secrets(text: str) -> str:
        for pattern in SENSITIVE_PATTERNS:
            text = pattern.sub(r"\1***REDACTED***", text)
        return text

    def _sanitize_value(self, val):
        if isinstance(val, str):
            return self.mask_secrets(val)
        return val


class ISTFormatter(logging.Formatter):
    """Custom formatter providing timestamps in Asia/Kolkata (IST)."""

    def __init__(self, fmt=None, datefmt=None, tz_str="Asia/Kolkata"):
        super().__init__(fmt, datefmt)
        self.tz = ZoneInfo(tz_str)

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self.tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """Configures root logger with secret masking and console/file handlers."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    formatter = ISTFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S%z",
    )
    masking_filter = SecretMaskingFilter()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(masking_filter)
    root_logger.addHandler(console_handler)

    # File Handler
    file_handler = logging.FileHandler(log_path / "trading_system.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(masking_filter)
    root_logger.addHandler(file_handler)

    return logging.getLogger("trading_system")


def get_logger(name: str = "trading_system") -> logging.Logger:
    """Returns a named logger."""
    return logging.getLogger(name)


