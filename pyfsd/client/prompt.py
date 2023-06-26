from typing import TYPE_CHECKING, List

from twisted.protocols.basic import LineReceiver

if TYPE_CHECKING:
    from .protocol import FSDClientProtocol


class PromptProtocol(LineReceiver):
    delimiter = b"\n"
    protocol: "FSDClientProtocol"
    password: str

    def __init__(self, protocol: "FSDClientProtocol", password: str) -> None:
        self.protocol = protocol
        self.password = password

    def connectionMade(self):
        self.sendLine(b"Client prompt ready.")
        self.protocol.addHandler("error", print)
        self.protocol.addHandler("message", print)
        self.protocol.addHandler("other_packet", print)
        self.transport.write(b"> ")

    def lineReceived(self, line):
        self.handleCommand(line.decode().split(" "))
        self.transport.write(b"> ")

    def handleCommand(self, command: List[str]):
        if command[0] == "login":
            self.protocol.login(self.password.encode())

    def dataReceived(self, data):
        print(data)
        super().dataReceived(data)

    def rawDataReceived(self, data):
        print(data)
        super().rawDataReceived(data)
