import logging
import sys

import structlog

from app.settings import LOG_LEVEL


class LoggingAgent:

    def __init__(self):
        configure_structlog()
        self.logger = structlog.get_logger('internal-mobility-matching')

    def get_context_bound_logger(self):
        return self.logger.bind(**structlog.contextvars.get_contextvars())


def add_common_context_args(**context_args: dict):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**context_args)


def update_common_context_args(**context_args):
    structlog.contextvars.bind_contextvars(**context_args)


def configure_structlog(log_level=None):
    log_level = log_level or getattr(logging, LOG_LEVEL.upper())
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )

    shared_processors = (
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.PATHNAME,
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        )
    )
    if sys.stderr.isatty():
        processors = shared_processors + (
            structlog.dev.ConsoleRenderer(),
        )
    else:
        processors = shared_processors + (
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        )

    structlog.configure_once(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


agent = LoggingAgent()
