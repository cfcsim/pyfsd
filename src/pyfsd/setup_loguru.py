import sys
import warnings
from io import TextIOWrapper
from typing import (
    TYPE_CHECKING,
    Iterable,
    List,
    Optional,
    TextIO,
    Tuple,
    Type,
    Union,
    cast,
)

from loguru import logger
from loguru._datetime import aware_now, datetime
from loguru._logger import start_time
from twisted.logger import FileLogObserver, ILogObserver, globalLogBeginner
from twisted.logger._format import _formatEvent
from twisted.python.failure import (
    EXCEPTION_CAUGHT_HERE,
    Failure,
    _Frame,
    _Traceback,
    _TracebackFrame,
    traceupLength,
)
from zope.interface import implementer

if TYPE_CHECKING:
    from types import FrameType, TracebackType

    from loguru import Record
    from twisted.logger import LogEvent

_warnings_showwarning = warnings.showwarning


class InvaildException(Exception):
    type: object
    value: object

    def __init__(self, _: object) -> None:
        raise RuntimeError("Using createInvaildException.")

    def __str__(self) -> str:
        if isinstance(self.type, type):
            name = self.type.__name__
        else:
            name = type(self.type).__name__
        return f"({name}){self.value}"


def createInvaildException(type_: object) -> Type[InvaildException]:
    class InvaildException1(InvaildException):
        def __init__(self, value: object) -> None:
            self.type = type_
            self.value = value

    return InvaildException1


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


def warningCapturer(
    message: Union[Warning, str],
    category: Type[Warning],
    filename: str,
    lineno: int,
    file: Optional[TextIO] = None,
    line: Optional[str] = None,
) -> None:
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
    logger.remove()
    _beginLoggingTo = globalLogBeginner.beginLoggingTo

    def handler(  # type: ignore[no-untyped-def]
        observers: Iterable[ILogObserver],
        discardBuffer: bool = False,
        redirectStandardIO: bool = True,
    ):
        have_file = False
        # Catch log file
        for observer in observers:
            if isinstance(observer, FileLogObserver):
                if observer._encoding is not None:
                    file = TextIOWrapper(observer._outFile, observer._encoding)
                else:
                    file = cast(TextIOWrapper, observer._outFile)
                logger.add(file)
                have_file = True
            else:
                _beginLoggingTo(
                    observers,
                    discardBuffer=discardBuffer,
                    redirectStandardIO=redirectStandardIO,
                )
        # Setup loguru
        if have_file:
            _beginLoggingTo(
                [loguruLogObserver],
                discardBuffer=discardBuffer,
                redirectStandardIO=False,
            )
            warnings.showwarning = warningCapturer

    # Avoid adding other observers
    setattr(globalLogBeginner, "beginLoggingTo", handler)


def extractException(
    failure: Failure, shorten: bool = True
) -> Tuple[Type[BaseException], Optional[BaseException], Optional["TracebackType"]]:
    """Extract exception info from a failure.

    Args:
        failure: The failure.

    Returns:
        The exception info.
    """
    # I'll try my best to explain it.
    # Read twisted:src/twisted/python/failure.py:Failure:__init__ for better understand

    def copyFrame(frame: "FrameType") -> _Frame:
        """Copy a frame.

        Args:
            frame: The frame.

        Returns:
            The copyed frame.
        """

        new_frame = _Frame((None,) * 5, None)
        new_frame.f_code = frame.f_code  # type: ignore[assignment]
        new_frame.f_lineno = frame.f_lineno
        new_frame.f_globals = frame.f_globals
        new_frame.f_locals = frame.f_locals
        new_frame.f_lasti = frame.f_lasti
        new_frame.f_builtins = frame.f_builtins
        new_frame.f_trace = frame.f_trace  # pyright: ignore
        return new_frame

    def tookException(
        failure: Failure,
    ) -> Tuple[Type[BaseException], Optional[BaseException]]:
        """Took type & value (exception info) out of a failure.

        Args:
            failure: The failure.

        Returns:
            result[0] is type, result[1] is value
        """
        type_: Type[BaseException]
        value: Optional[BaseException]

        if not isinstance(failure.type, type) or not issubclass(
            failure.type, BaseException
        ):
            # Malicious failure!
            if isinstance(failure.value, BaseException):
                type_ = type(failure.value)
            else:
                type_ = createInvaildException(failure.type)
        else:
            type_ = failure.type

        if isinstance(failure.value, str):
            try:  # type: ignore[unreachable]
                # https://github.com/twisted/twisted
                # /blob/a9ee8e59a5cd1950bf1a18c4b6ca813e5f56ad08/src/ \
                # twisted/python/failure.py#L289
                # failure.type won't be None if failure.value is str
                value = type_(failure.value)  # pyright: ignore
            except Exception:
                value = createInvaildException(type_)(failure.type)
        else:
            if issubclass(type_, InvaildException):
                value = type_(failure.value)
            else:
                value = failure.value

        return type_, value

    def tookTraceback(
        failure: Failure, shorten: bool = True
    ) -> Union[_TracebackFrame, "TracebackType", None]:
        if failure.tb is not None:
            if not shorten:
                return failure.tb
            frame = failure.tb.tb_frame
            # TODO: Determine stackOffset
            stack: List[_Frame] = []
            while frame is not None:
                new_frame = copyFrame(frame)
                try:
                    stack[0].f_back = new_frame
                except IndexError:
                    # First frame
                    pass
                stack.insert(0, new_frame)
                frame = frame.f_back

            tb_frame = _TracebackFrame(failure.tb.tb_frame)
            tb_frame.tb_next = failure.tb.tb_next  # pyright: ignore
            caught_frame = _Frame((EXCEPTION_CAUGHT_HERE, "", 0, (), ()), None)
            caught_frame.f_back = stack[traceupLength - 1]  # pyright: ignore

            first_frame = copyFrame(failure.tb.tb_frame)
            first_frame.f_back = caught_frame
            tb_frame.tb_frame = first_frame
            return tb_frame
        elif len(failure.frames) > 0:
            return _Traceback(  # type: ignore[no-any-return]
                [
                    *failure.stack[:traceupLength],  # pyright: ignore
                    (EXCEPTION_CAUGHT_HERE, "", 0, (), ()),
                ]
                if shorten
                else failure.stack,
                failure.frames,
            )
        else:
            # What should I do now?
            return None

    return *tookException(failure), cast(
        "TracebackType", tookTraceback(failure, shorten)
    )


def getSystem(event: "LogEvent") -> str:
    if "log_system" in event:
        try:
            return str(event["log_system"])
        except:  # noqa: E722
            return "?"
    else:
        if "log_namespace" in event:
            return str(event["log_namespace"])
        else:
            return "-"


@logger.catch(message="Loguru observer failure")
@implementer(ILogObserver)
def loguruLogObserver(event: "LogEvent") -> None:
    level_name = event["log_level"].name.upper()
    if level_name == "WARN":
        level_name = "WARNING"
    event_text = _formatEvent(event)
    if event_text is not None:
        depth = getDepth()

        def patcher(record: "Record") -> None:
            record["time"] = datetime.fromtimestamp(event["log_time"])
            system = getSystem(event)
            if (name := record.get("name", None)) is not None and not system.startswith(
                name
            ):
                record["name"] = f"({system}):{name}"
            else:
                record["name"] = system
            record["elapsed"] = aware_now() - start_time

        logger.patch(patcher).opt(
            depth=depth,
            exception=extractException(event["log_failure"])
            if "log_failure" in event
            else None,
        ).log(level_name, event_text)
