"""Structured logging configuration.

JSON logs to file for machine parsing, human-readable logs to console.
"""
import json
import logging
import logging.handlers
import os
from datetime import datetime

LOG_DIR = "/var/log/wonderz"
LOG_FILE = os.path.join(LOG_DIR, "app.log")


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Propagate extra fields commonly set via ``extra={...}``
        for key in ("job_id", "agent_id", "user_id", "tokens", "step_name"):
            val = getattr(record, key, None)
            if val is not None:
                log_data[key] = val

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with JSON file handler + console handler."""
    root = logging.getLogger()

    # Avoid adding handlers twice (e.g. on hot-reload)
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        return

    root.setLevel(level)

    # --- JSON file handler (100 MB, 7 backups) ---
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=100_000_000,  # 100 MB
            backupCount=7,
        )
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(level)
        root.addHandler(file_handler)
    except (PermissionError, OSError) as e:
        # If log dir is not writable, skip file handler
        print(f"[logging_config] Could not create file handler: {e}")

    # --- Console handler (human-readable) ---
    console = logging.StreamHandler()
    console.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    console.setLevel(level)
    root.addHandler(console)
