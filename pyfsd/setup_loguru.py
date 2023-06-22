import sys
import warnings
from typing import TYPE_CHECKING

from loguru import logger
from loguru._datetime import aware_now, datetime
from loguru._logger import start_time
from twisted.logger import ILogObserver, globalLogBeginner
from twisted.logger._format import _formatEvent
from zope.interface import implementer

if TYPE_CHECKING:
    from loguru import Record
    from twisted.logger import LogEvent
    from twisted.python.failure import Failure

_warnings_showwarning = warnings.showwarning


def getDepth() -> int:
    try:
        raise Exception
    except Exception:
        frame = sys.exc_info()[2].tb_frame  # type: ignore
        have_logger = False
        depth = -1
        while frame is not None:
            try:
                name = frame.f_globals["__name__"]
                if name.startswith("twisted.logger") or name.startswith(
                    "twisted.python.log"
                ):
                    have_logger = True
                elif have_logger:
                    break
            except KeyError:
                pass
            depth += 1
            frame = frame.f_back
        return depth


def warningCapturer(message, category, filename, lineno, file=None, line=None):
    if category is RuntimeWarning and filename.endswith("metar/Metar.py"):
        # ignore metar parse warning
        return
    if file is None:
        logger.opt(depth=2).warning(
            str(warnings.formatwarning(message, category, filename, lineno, line))
        )
    else:
        _warnings_showwarning(message, category, filename, lineno, file, line)


def setupLoguru() -> None:
    # Avoid stderr lost
    logger.remove()
    logger.add(sys.__stderr__)
    # Delete observers
    globalLogBeginner._publisher._observers = []
    # Setup loguru
    globalLogBeginner.beginLoggingTo(
        [loguruLogObserver], redirectStandardIO=False  # type: ignore
    )
    # Avoid adding other observers
    setattr(globalLogBeginner, "beginLoggingTo", lambda *_, **__: None)
    warnings.showwarning = warningCapturer


def extractException(failure: "Failure"):
    return failure.type, failure.value, failure.getTracebackObject()


def getSystem(event: "LogEvent") -> str:
    if "log_system" in event:
        try:
            return str(event["log_system"])
        except:  # noqa: E722
            return "?"
    else:
        if "log_namespace" in event:
            return event["log_namespace"]
        else:
            return "-"


@logger.catch(message="Loguru observer failure")
@implementer(ILogObserver)
def loguruLogObserver(event: "LogEvent") -> None:
    # sys.__stdout__.write(repr(event) + "\n")
    level_name = event["log_level"].name.upper()
    if level_name == "WARN":
        level_name = "WARNING"
    if "failure" in event:
        logger.opt(
            exception=extractException(event["failure"]),  # type: ignore
            depth=4,
        ).log(level_name, "Unhandled Error")
    elif "log_failure" in event:
        logger.opt(
            exception=extractException(event["log_failure"]),  # type: ignore
            depth=4,
        ).log(level_name, "Error info:")
    else:
        event_text = _formatEvent(event)
        if event_text is not None:
            depth = getDepth()

            def patcher(record: "Record") -> None:
                record["time"] = datetime.fromtimestamp(event["log_time"])
                system = getSystem(event)
                if (
                    name := record.get("name", None)
                ) is not None and not system.startswith(name):
                    record["name"] = f"({system}):{name}"
                else:
                    record["name"] = system
                record["elapsed"] = aware_now() - start_time

            logger.patch(patcher).opt(depth=depth).log(level_name, event_text)
