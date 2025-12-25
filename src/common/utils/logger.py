import logging
import sys
import os
from typing import Any

NOTICE_LEVEL = 25
logging.addLevelName(NOTICE_LEVEL, "NOTICE")


RESET = "\033[0m"
COLORS = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "NOTICE": "\033[38;5;33m",  # Blue-ish
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[1;41m",  # White on red
}


class ColorFormatter(logging.Formatter):
    """Only color console output."""

    def format(self, record: logging.LogRecord) -> str:
        if getattr(record, "use_color", False):
            color = COLORS.get(record.levelname, "")
            record.levelname = f"{color}{record.levelname:<7}{RESET}"
        return super().format(record)


# -------------------------------------------------------------------
# 3. Custom Logger: route info() -> NOTICE
# -------------------------------------------------------------------
class CustomLogger(logging.Logger):
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        super().log(NOTICE_LEVEL, msg, *args, **kwargs)


logging.setLoggerClass(CustomLogger)


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")


console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(NOTICE_LEVEL)
console_handler.setFormatter(ColorFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
console_handler.addFilter(lambda record: setattr(record, "use_color", True) or True)
console_handler.addFilter(lambda record: record.levelno >= NOTICE_LEVEL)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
file_handler.addFilter(lambda record: record.name.startswith("app"))


root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.handlers.clear()
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)


for noisy in ["httpx", "urllib3", "opensearch"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or "app")


logger = get_logger("app")
logger.debug("Logger initialized successfully.")
