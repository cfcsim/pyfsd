from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    AnyStr,
    BinaryIO,
    Generic,
    List,
    Optional,
    cast,
)

if TYPE_CHECKING:
    from twisted.conch.recvline import RecvLine


class OutputProxy(Generic[AnyStr]):
    __origin_output: IO[AnyStr]

    def __init__(self, origin_output: IO[AnyStr]) -> None:
        self.__origin_output = origin_output

    @property
    def mode(self) -> str:
        return self.__origin_output.mode

    @property
    def name(self) -> str:
        return self.__origin_output.name

    def close(self) -> None:
        return self.__origin_output.close()

    @property
    def closed(self) -> bool:
        return self.__origin_output.closed

    def fileno(self) -> int:
        return self.__origin_output.fileno()

    def flush(self) -> None:
        return self.__origin_output.flush()

    def isatty(self) -> bool:
        return self.__origin_output.isatty()

    def read(self, n: int = -1) -> AnyStr:
        return self.__origin_output.read(n)

    def readable(self) -> bool:
        return self.__origin_output.readable()

    def readline(self, limit: int = -1) -> AnyStr:
        return self.__origin_output.readline(limit)

    def readlines(self, hint: int = -1) -> List[AnyStr]:
        return self.__origin_output.readlines(hint)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self.__origin_output.seek(offset, whence)

    def seekable(self) -> bool:
        return self.__origin_output.seekable()

    def tell(self) -> int:
        return self.__origin_output.tell()

    def truncate(self, size: int = -1) -> int:
        return self.__origin_output.truncate(size)

    def writable(self) -> bool:
        return self.__origin_output.writable()

    def write(self, s: AnyStr) -> int:
        return self.__origin_output.write(s)

    def writelines(self, lines: List[AnyStr]) -> None:
        return self.__origin_output.writelines(lines)

    def __enter__(self) -> IO[AnyStr]:
        return cast(IO[AnyStr], self)

    def __exit__(self, type_, value, traceback) -> None:
        return self.__origin_output.__exit__(type_, value, traceback)

    @property
    def buffer(self) -> BinaryIO:
        return self.__origin_output.buffer  # type: ignore[attr-defined]

    @property
    def encoding(self) -> str:
        return self.__origin_output.encoding  # type: ignore[attr-defined]

    @property
    def errors(self) -> Optional[str]:
        return self.__origin_output.errors  # type: ignore[attr-defined]

    @property
    def line_buffering(self) -> bool:
        return self.__origin_output.line_buffering  # type: ignore[attr-defined]

    @property
    def newlines(self) -> Any:
        return self.__origin_output.newlines  # type: ignore[attr-defined]


class PSInserter(OutputProxy):
    __recvline: "RecvLine"

    def __init__(self, origin_output: IO[AnyStr], recvline: "RecvLine") -> None:
        super().__init__(origin_output)
        self.__recvline = recvline

    @property
    def buffer(self) -> BinaryIO:
        return PSInserter(super().buffer, self.__recvline)  # type: ignore

    def write(self, s: AnyStr) -> int:
        """
        if isinstance(s, bytes):
            return super().write(
                b"\r%s%s" % (s, self.__recvline.ps[self.__recvline.pn])
            )
        else:
            return super().write(
                f"\r{s}{self.__recvline.ps[self.__recvline.pn].decode('ascii')}"
            )
        """
        n = super().write(s)
        self.__recvline.terminal.write(self.__recvline.ps[self.__recvline.pn])
        return n

    def writelines(self, lines: List[AnyStr]) -> None:
        val = super().writelines(lines)
        self.__recvline.terminal.write(self.__recvline.ps[self.__recvline.pn])
        return val
