from typing import TYPE_CHECKING, List

from twisted.conch.manhole import (
    CTRL_A,
    CTRL_BACKSLASH,
    CTRL_C,
    CTRL_D,
    CTRL_E,
    CTRL_L,
    Manhole,
)
from twisted.conch.recvline import HistoricRecvLine

# from .utf_8 import lastCBLength

if TYPE_CHECKING:
    from twisted.conch.insults.insults import ServerProtocol


class PromptProtocol(Manhole):
    terminal: "ServerProtocol"
    support_utf_8: bool = True
    lineBuffer: List[bytes]

    def __init__(self) -> None:
        pass

    def connectionMade(self) -> None:
        HistoricRecvLine.connectionMade(self)
        self.keyHandlers[CTRL_C] = self.handle_INT
        self.keyHandlers[CTRL_D] = self.handle_EOF
        self.keyHandlers[CTRL_L] = self.handle_FF
        self.keyHandlers[CTRL_A] = self.handle_HOME
        self.keyHandlers[CTRL_E] = self.handle_END
        self.keyHandlers[CTRL_BACKSLASH] = self.handle_QUIT

    def lineReceived(self, line) -> None:
        pass

    def handle_INT(self) -> None:
        """
        Handle ^C as an interrupt keystroke by resetting the current input
        variables to their initial state.
        """
        self.pn = 0
        self.lineBuffer = []
        self.lineBufferIndex = 0

        self.terminal.nextLine()
        self.terminal.write(b"KeyboardInterrupt")
        self.terminal.nextLine()
        self.terminal.write(self.ps[self.pn])

    def initializeScreen(self) -> None:
        self.terminal.write(self.ps[self.pn])
        self.setInsertMode()

    def handle_QUIT(self):
        self.setTypeoverMode()
        if self.terminal.transport is not None:
            self.terminal.transport.loseConnection()  # Avoid clear screen

    def keystrokeReceived(self, keyID, _):
        handler = self.keyHandlers.get(keyID)
        if handler is not None:
            handler()
        elif ord(keyID) > 0x1F:  # Support unicode
            self.characterReceived(keyID, False)
        else:
            self._log.warn("Received unhandled keyID: {keyID!r}", keyID=keyID)

    # Below section trying support UTF-8. Not working now.


#   def determineWidthBackward(self) -> int:
#       assert self.support_utf_8
#       is_end = False
#       if (n := self.lineBufferIndex - (len(self.lineBuffer)-1)) > 0:
#           if n == 1:
#               is_end = True
#           else:
#               raise RuntimeError(
#                   "lineBufferIndex does not pair with lineBuffer. "
#                   "This should'n t happen."
#               )
#       reversed_buffer = self.lineBuffer
#       reversed_buffer.reverse()
#       cb_length = lastCBLength(reversed_buffer)
#       return cb_length + 2 if is_end else cb_length + 1

#   def handle_LEFT(self):
#       if self.lineBufferIndex > 0:
#           should_backward = 1
#           if (
#               self.support_utf_8
#               and ord(self.lineBuffer[self.lineBufferIndex - 1]) > 127
#           ):
#               should_backward = self.determineWidthBackward()
#           self.lineBufferIndex -= (
#               should_backward  # + 1 if should_backward > 1 else should_backward
#           )
#           if should_backward > 0:
#               self.terminal.cursorBackward(
#                   should_backward
#               )  # - 1 if should_backward > 1 else should_backward)
