from typing import TYPE_CHECKING

from twisted.internet.protocol import ClientFactory

from .protocol import FSDClientProtocol

if TYPE_CHECKING:
    from ..object.client import Client
    from .protocol import EventHandler


class FSDClientFactory(ClientFactory):
    client_protocol: FSDClientProtocol

    def __init__(self, client: "Client", handler: "EventHandler") -> None:
        self.client_protocol = FSDClientProtocol(client, handler)

    def buildProtocol(self, _) -> FSDClientProtocol:
        return self.client_protocol
