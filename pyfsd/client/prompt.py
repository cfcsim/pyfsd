import sys
from typing import TYPE_CHECKING, Optional, TextIO, cast

from loguru import logger

from ..prompt.protocol import PromptProtocol
from ..prompt.stdout_helper import AsyncPrint

if TYPE_CHECKING:
    from .protocol import FSDClientProtocol
    from twisted.python.failure import Failure


class ClientPrompt(PromptProtocol):
    def __init__(self, protocol: "FSDClientProtocol", password: str) -> None:
        self.protocol = protocol
        self.password = password
        sys.stderr = cast(TextIO, AsyncPrint(sys.stderr, self))
        sys.stdout = cast(TextIO, AsyncPrint(sys.stdout, self))
        logger.remove()
        logger.add(sys.stderr)

    def lineReceived(self, line: bytes) -> None:
        self.terminal.write(line)
        self.terminal.nextLine()
        self.terminal.write(self.ps[self.pn])

    def connectionLost(self, _: Optional["Failure"] = None) -> None:
        from twisted.internet.reactor import stop  # type: ignore[attr-defined]

        stop()
