# https://www.structlog.org/en/stable/standard-library.html
"""Logger configurer."""
from logging.config import dictConfig
from sys import version_info
from typing import Dict, List, Literal, TypedDict, Union

from structlog import configure, dev, processors, reset_defaults, stdlib

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
        fmt: strftime format string, or "iso" for ISO 8601, or "timestamp"
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
        wrapper_class=stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
