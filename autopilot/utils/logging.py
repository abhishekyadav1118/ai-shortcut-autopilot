"""Structured and colored logging utility."""

import logging
import re
import sys

# Regex pattern to sanitize known secret keys in log outputs
SECRET_PATTERN = re.compile(r"(AIza[0-9A-Za-z-_]{35}|sk-ant-[0-9A-Za-z-_]{30,}|ya29\.[0-9A-Za-z-_]+)")


class SecretMaskingFormatter(logging.Formatter):
    """Logging formatter that redacts detected API keys and secrets."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return SECRET_PATTERN.sub("[REDACTED_SECRET]", original)


def get_logger(name: str = "autopilot") -> logging.Logger:
    """Obtain or configure application logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        handler.setFormatter(SecretMaskingFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        logger.propagate = False
    return logger
