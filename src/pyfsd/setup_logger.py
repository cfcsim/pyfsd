# https://www.structlog.org/en/stable/standard-library.html
"""Logger configurer."""

from logging import CRITICAL, DEBUG, ERROR, INFO, NOTSET, WARNING
from logging.config import dictConfig
from sys import version_info
from typing import Dict, List, Literal, Type, TypedDict, Union

from structlog import (
    configure,
    dev,
    processors,
    reset_defaults,
    stdlib,
)

if version_info >= (3, 11):
    from typing import NotRequired  # type: ignore[attr-defined,unused-ignore]
else:
    from typing_extensions import NotRequired

HandlerConfig = TypedDict(
    "HandlerConfig",
    {
        "class": str,
        "level": NotRequired[str],
        "formatter": NotRequired[str],
        "filters": NotRequired[List[str]],
    },
)


class LoggerConfig(TypedDict, total=False):
    """Type of value of logging.config.dictConfig.loggers."""

    level: str
    propagate: bool
    filters: List[str]
    handlers: List[str]


class TimeFormatConfig(TypedDict):
    """Config of time formatter.

    Attributes document comes from structlog.processors.TimeStamper.

    Attributes:
        fmt: strftime format string, or "iso" for ISO 8601, or "timestamp" \
            for a UNIX timestamp.
        utc: Whether timestamp should be in UTC or local time.
        key: Target key in event_dict for added timestamps.
    """

    fmt: Union[str, Literal["iso", "timestamp"], None]
    utc: bool
    key: str


class PyFSDLoggerConfig(TypedDict):
    """PyFSD logger config.

    Attributes:
        handlers: See dictConfig.
        loggers: See dictConfig.
        include_extra: Print log's extra or not.
        extract_record: Extract thread and process names and add them to the event dict.
    """

    handlers: Dict[str, Union[dict, HandlerConfig]]  # Allow extra keys
    logger: Union[dict, LoggerConfig]
    include_extra: NotRequired[bool]
    extract_record: NotRequired[bool]
    time: NotRequired[TimeFormatConfig]


def make_filtering_stdlib_bound_logger(min_level: int) -> Type[stdlib.BoundLogger]:
    """Create a new BoundLogger that only logs min_level or higher."""
    if min_level == NOTSET:
        return stdlib.BoundLogger

    def do_nothing(*_: object, **__: object) -> None:
        return None

    async def async_do_nothing(*_: object, **__: object) -> None:
        return None

    class BoundLogger(stdlib.BoundLogger):
        def log(
            self, level: int, event: str | None = None, *args: object, **kw: object
        ) -> object:
            if level < min_level:
                return None
            return super().log(level, event, *args, **kw)

        async def alog(
            self, level: object, event: str, *args: object, **kw: object
        ) -> None:
            if isinstance(level, int) and level < min_level:
                return None
            return await super().alog(level, event, *args, **kw)

        if min_level > CRITICAL:  # how
            critical = do_nothing
            fatal = do_nothing
            acritical = async_do_nothing
            afatal = async_do_nothing
        elif min_level > ERROR:
            error = do_nothing
            exception = do_nothing
            aerror = async_do_nothing
            aexception = async_do_nothing
        elif min_level > WARNING:
            warning = do_nothing
            warn = do_nothing
            awarning = async_do_nothing
        elif min_level > INFO:
            info = do_nothing
            ainfo = async_do_nothing
        elif min_level > DEBUG:
            debug = do_nothing
            adebug = async_do_nothing

    return BoundLogger


def setup_logger(config: PyFSDLoggerConfig) -> None:
    """Setup logger with config."""
    reset_defaults()
    include_extra, extract_record, time = (
        config.get("include_extra", False),
        config.get("extract_record", False),
        config.get(
            "time", {"fmt": "%Y-%m-%d %H:%M:%S", "utc": False, "key": "timestamp"}
        ),
    )
    if time["fmt"] == "timestamp":
        time["fmt"] = None
    timestamper = processors.TimeStamper(**time)
    pre_chain = [
        # Add the log level and a timestamp to the event_dict if the log entry
        # is not from structlog.
        stdlib.add_log_level,
        stdlib.add_logger_name,
        timestamper,
    ]
    if include_extra:
        pre_chain.append(stdlib.ExtraAdder())

    def suppress_extra(_: object, __: str, event_dict: dict) -> dict:
        """Remove log's extra."""
        if "extra" in event_dict:
            del event_dict["extra"]
        return event_dict

    def extract_from_record(_: object, __: str, event_dict: dict) -> dict:
        """Extract thread and process names and add them to the event dict."""
        record = event_dict["_record"]
        event_dict["thread_name"] = record.threadName
        event_dict["process_name"] = record.processName
        return event_dict

    extra_dealers = []
    if not include_extra:
        extra_dealers.append(suppress_extra)
    elif extract_record:
        extra_dealers.append(extract_from_record)

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "plain": {
                    "()": stdlib.ProcessorFormatter,
                    "processors": [
                        *extra_dealers,
                        stdlib.ProcessorFormatter.remove_processors_meta,
                        dev.ConsoleRenderer(
                            colors=False, exception_formatter=dev.better_traceback
                        ),
                    ],
                    "foreign_pre_chain": pre_chain,
                },
                "json": {
                    "()": stdlib.ProcessorFormatter,
                    "processors": [
                        *extra_dealers,
                        stdlib.ProcessorFormatter.remove_processors_meta,
                        processors.JSONRenderer(),
                    ],
                    "foreign_pre_chain": pre_chain,
                },
                "colored": {
                    "()": stdlib.ProcessorFormatter,
                    "processors": [
                        *extra_dealers,
                        stdlib.ProcessorFormatter.remove_processors_meta,
                        dev.ConsoleRenderer(
                            colors=True, exception_formatter=dev.better_traceback
                        ),
                    ],
                    "foreign_pre_chain": pre_chain,
                },
            },
            "handlers": config["handlers"],  # type: ignore[typeddict-item]
            "loggers": {"": config["logger"]},  # type: ignore[dict-item]
        }
    )
    configure(
        processors=[
            stdlib.add_log_level,
            stdlib.add_logger_name,
            stdlib.PositionalArgumentsFormatter(),
            timestamper,
            processors.StackInfoRenderer(),
            stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=stdlib.LoggerFactory(),
        wrapper_class=make_filtering_stdlib_bound_logger(
            {
                "NOTSET": 0,
                "DEBUG": 10,
                "INFO": 20,
                "WARNING": 30,
                "ERROR": 40,
                "CRITICAL": 50,
            }[config["logger"]["level"]]
        ),
        cache_logger_on_first_use=True,
    )
