from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    AnyStr,
    BinaryIO,
    Callable,
    Iterable,
    Iterator,
    List,
    Optional,
    cast,
)

if TYPE_CHECKING:
    from twisted.conch.recvline import RecvLine


class OutputProxy(IO[AnyStr]):
    _origin_output: IO[AnyStr]

    def __init__(self, origin_output: IO[AnyStr]) -> None:
        self._origin_output = origin_output

    @property
    def mode(self) -> str:
        return self._origin_output.mode

    @property
    def name(self) -> str:
        return self._origin_output.name

    def close(self) -> None:
        return self._origin_output.close()

    @property
    def closed(self) -> bool:
        return self._origin_output.closed

    def fileno(self) -> int:
        return self._origin_output.fileno()

    def flush(self) -> None:
        return self._origin_output.flush()

    def isatty(self) -> bool:
        return self._origin_output.isatty()

    def read(self, n: int = -1) -> AnyStr:
        return self._origin_output.read(n)

    def readable(self) -> bool:
        return self._origin_output.readable()

    def readline(self, limit: int = -1) -> AnyStr:
        return self._origin_output.readline(limit)

    def readlines(self, hint: int = -1) -> List[AnyStr]:
        return self._origin_output.readlines(hint)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._origin_output.seek(offset, whence)

    def seekable(self) -> bool:
        return self._origin_output.seekable()

    def tell(self) -> int:
        return self._origin_output.tell()

    def truncate(self, size: Optional[int] = -1) -> int:
        return self._origin_output.truncate(size)

    def writable(self) -> bool:
        return self._origin_output.writable()

    def write(self, s: AnyStr) -> int:
        return self._origin_output.write(s)

    def writelines(self, lines: Iterable[AnyStr]) -> None:
        return self._origin_output.writelines(lines)

    def __enter__(self) -> IO[AnyStr]:
        return cast(IO[AnyStr], self)

    def __exit__(self, type_, value, traceback) -> None:
        return self._origin_output.__exit__(type_, value, traceback)

    def __iter__(self) -> Iterator[AnyStr]:
        return self._origin_output.__iter__()

    def __next__(self) -> AnyStr:
        return self._origin_output.__next__()

    @property
    def buffer(self) -> BinaryIO:
        return self._origin_output.buffer  # type: ignore[attr-defined]

    @property
    def encoding(self) -> str:
        return self._origin_output.encoding  # type: ignore[attr-defined]

    @property
    def errors(self) -> Optional[str]:
        return self._origin_output.errors  # type: ignore[attr-defined]

    @property
    def line_buffering(self) -> bool:
        return self._origin_output.line_buffering  # type: ignore[attr-defined]

    @property
    def newlines(self) -> Any:
        return self._origin_output.newlines  # type: ignore[attr-defined]


class AsyncPrint(OutputProxy):
    __recvline: "RecvLine"

    def __init__(self, origin_output: IO[AnyStr], recvline: "RecvLine") -> None:
        self._origin_output = origin_output
        self.__recvline = recvline

    @property
    def buffer(self) -> BinaryIO:
        return AsyncPrint(super().buffer, self.__recvline)  # type: ignore

    def _do(self, to_do: Callable, *args, **kwargs):
        rl = self.__recvline
        rl.terminal.eraseLine()
        rl.terminal.cursorBackward(len(rl.lineBuffer) + len(rl.ps[rl.pn]))
        rl.terminal.write("\r")
        val = to_do(*args, **kwargs)
        rl.terminal.write(rl.ps[rl.pn])
        if rl.lineBuffer:
            oldBuffer = rl.lineBuffer
            rl.lineBuffer = []
            rl.lineBufferIndex = 0
            for ch in oldBuffer[:-1]:
                rl.characterReceived(ch, True)
            rl.characterReceived(oldBuffer[-1], False)
        return val

    # Any -- why????
    def write(self, s: Any) -> int:
        return self._do(super().write, s)

    def writelines(self, lines: Iterable[Any]) -> None:
        return self._do(super().writelines, lines)
