from typing import TYPE_CHECKING, Optional, Tuple

from twisted.application.service import Service
from twisted.internet.stdio import StandardIO

from .raw_mode import RawMode

if TYPE_CHECKING:
    from twisted.internet.interfaces import IProtocol


class RawStdinService(Service):
    stdio: Optional[StandardIO] = None
    raw_mode: RawMode
    stdio_arg: Tuple[tuple, dict]

    def __init__(
        self,
        proto: "IProtocol",
        stdin: Optional[int] = 0,
        stdout: Optional[int] = 1,
        reactor=None,
    ):
        self.stdio_arg = (
            (proto,),
            {"stdin": stdin, "stdout": stdout, "reactor": reactor},
        )
        self.raw_mode = RawMode(stdin)

    def startService(self):
        super().startService()
        assert self.stdio is None
        self.raw_mode.setup()
        self.stdio = StandardIO(*self.stdio_arg[0], **self.stdio_arg[1])
        setattr(self.stdio, "raw_mode", self.raw_mode)

    def stopService(self):
        assert self.stdio is not None
        if not self.stdio.disconnected:
            print("Disconnecting")
            self.stdio.loseConnection()
        self.stdio = None
        if self.raw_mode.in_raw_mode:
            self.raw_mode.restore()
        super().stopService()
