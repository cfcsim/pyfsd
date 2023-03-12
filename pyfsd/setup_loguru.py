import sys
from typing import TYPE_CHECKING

from loguru import logger
from twisted.logger import ILogObserver, globalLogBeginner
from twisted.logger._format import _formatEvent
from zope.interface import implementer

if TYPE_CHECKING:
    from twisted.logger import LogEvent
    from twisted.python.failure import Failure


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


def setup_loguru() -> None:
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
    globalLogBeginner.beginLoggingTo = lambda *_, **__: None


def extractException(failure: "Failure"):
    if failure.type is None:
        return None
    elif not issubclass(failure.type, Exception):
        return None
    return failure.type, failure.value, failure.tb


@logger.catch(message="Loguru observer failure")
@implementer(ILogObserver)
def loguruLogObserver(event: "LogEvent") -> None:
    if "failure" in event:
        logger.opt(
            exception=extractException(event["failure"]),  # type: ignore
            depth=4,
        ).error("Unhandled Error")
    else:
        event_text = _formatEvent(event)
        if event_text is not None:
            # namespace = event["log_namespace"].rsplit(".", 1)[0]
            depth = getDepth()
            level_name = event["log_level"].name.upper()
            if level_name == "WARN":
                level_name = "WARNING"
            logger.opt(depth=depth).log(level_name, event_text)
