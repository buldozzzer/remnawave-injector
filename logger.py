import logging
import sys
from pathlib import Path


import structlog
from structlog import configure, get_logger
from structlog.dev import ConsoleRenderer, RichTracebackFormatter
from structlog.processors import (
    JSONRenderer,
    TimeStamper,
    StackInfoRenderer,
    UnicodeDecoder,
)
from structlog.stdlib import LoggerFactory, ProcessorFormatter, BoundLogger, add_log_level
from structlog.stdlib import add_logger_name

# Явный импорт
from logging.handlers import RotatingFileHandler


def setup_structlog(
    log_level: str = "INFO",
    json_logs: bool = False,  # True в production
    log_dir: str = "logs",
) -> None:

    Path(log_dir).mkdir(exist_ok=True)

    shared_processors = [
        TimeStamper(fmt="iso", utc=True),
        add_log_level,
        StackInfoRenderer(),
        UnicodeDecoder(),
    ]

    if json_logs:
        formatter = ProcessorFormatter(
            processor=JSONRenderer(ensure_ascii=False, sort_keys=True)
        )
        processors = shared_processors + [ProcessorFormatter.wrap_for_formatter]
    else:
        formatter = ProcessorFormatter(
            processor=ConsoleRenderer(
                colors=True, exception_formatter=RichTracebackFormatter()
            )
        )
        processors = shared_processors + [ProcessorFormatter.wrap_for_formatter]

    configure(
        processors=processors,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        filename=f"{log_dir}/app.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=15,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    # Файл error.log (только ошибки)
    error_handler = RotatingFileHandler(
        filename=f"{log_dir}/error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    # Убираем шум
    for noisy in ["requests", "urllib3", "schedule", "sqlalchemy", "mitmproxy", "mitmproxy.addons", "asyncio"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Стартовое сообщение
    get_logger("injector").info(
        f"Логер успешно инициализирован",
        log_format="json" if json_logs else "console",
        log_level=log_level,
    )


# Глобальный логгер
logger: BoundLogger = get_logger("injector")
