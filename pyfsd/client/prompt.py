from typing import TYPE_CHECKING

from ..prompt.protocol import PromptProtocol

if TYPE_CHECKING:
    from .protocol import FSDClientProtocol


class ClientPrompt(PromptProtocol):
    def __init__(self, protocol: "FSDClientProtocol", password: str) -> None:
        self.protocol = protocol
        self.password = password
        """
        sys.stderr = PSInserter(sys.stderr, self)
        sys.stdout = PSInserter(sys.stdout, self)
        logger.remove()
        logger.add(sys.stderr)
        """

    def lineReceived(self, line):
        self.terminal.write(line)
        self.terminal.nextLine()
        self.terminal.write(self.ps[self.pn])

    def connectionLost(self, _=None):
        from twisted.internet.reactor import stop

        stop()
