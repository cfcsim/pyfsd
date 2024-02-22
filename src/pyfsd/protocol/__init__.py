"""PyFSD protocols."""
from abc import ABCMeta, abstractmethod
from asyncio import Protocol
from typing import TYPE_CHECKING

from ..define.packet import join_lines

if TYPE_CHECKING:
    from asyncio import Transport

__all__ = ["LineReceiver", "LineProtocol"]


class LineReceiver(Protocol, metaclass=ABCMeta):
    """Line receiver.

    Attributes:
        buffer: Buffer used to store a line's data.
        delimiter: Line delimiter.
        max_length: Max acceptable line length. Set it to -1 to allow infinite
    """

    buffer: bytes = b""
    delimiter: bytes = b"\r\n"
    max_length: int = 1024  # 1kb

    @abstractmethod
    def line_received(self, line: bytes) -> None:
        """Called when a line was received."""
        raise NotImplementedError

    @abstractmethod
    def max_length_exceed(self, length: int) -> None:
        """Called when line length exceed max length."""
        raise NotImplementedError

    def data_received(self, data: bytes) -> None:
        """Handle datas and call line_received as soon as we received a line."""
        if self.max_length != -1:
            length = len(self.buffer) + len(data)
            if length > self.max_length:
                self.max_length_exceed(length)

        if self.delimiter in data:
            *lines, left = data.split(self.delimiter)
            lines[0] = self.buffer + lines[0]
            self.buffer = left
            for line in lines:
                self.line_received(line)
        else:
            self.buffer += data


class LineProtocol(LineReceiver):
    """Protocol to deal with lines.

    Attributes:
        buffer: Buffer used to store a line's data.
        delimiter: Line delimiter.
    """

    transport: "Transport"

    def connection_made(self, transport: "Transport") -> None:  # type: ignore[override]
        """Save transport after the connection was made."""
        self.transport = transport

    def max_length_exceed(self, length: int) -> None:
        """Kill when line length exceed max length."""
        self.transport.close()

    def send_line(self, line: bytes) -> None:
        """Send line to client."""
        self.transport.write(line + self.delimiter)

    def send_lines(
        self,
        *lines: bytes,
        auto_newline: bool = True,
        together: bool = True,
    ) -> None:
        """Send lines to client.

        Args:
            lines: Lines to be sent.
            auto_newline: Insert newline between every two line or not.
            together: Send lines together or not.
        """
        if together:
            self.transport.write(
                join_lines(*lines, newline=auto_newline),
            )
        else:
            for line in lines:
                self.transport.write(
                    (line + self.delimiter) if auto_newline else line,
                )
