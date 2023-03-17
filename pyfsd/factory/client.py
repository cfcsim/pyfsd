from random import randint
from typing import TYPE_CHECKING, Optional
from weakref import WeakValueDictionary

from twisted.internet.protocol import Factory
from twisted.internet.task import LoopingCall

from ..config import config
from ..define.packet import FSDClientPacket
from ..protocol.client import FSDClientProtocol

if TYPE_CHECKING:
    from twisted.cred.portal import Portal
    from twisted.internet.interfaces import IAddress

    from ..define.broadcast import BroadcastChecker
    from ..object.client import Client

__all__ = ["FSDClientFactory"]
client_blacklist = config.get("pyfsd", "client_blacklist").split()


class FSDClientFactory(Factory):
    clients: WeakValueDictionary[str, "Client"] = WeakValueDictionary()
    portal: "Portal"
    heartbeater: LoopingCall

    def __init__(self, portal: "Portal") -> None:
        self.heartbeater = LoopingCall(self.heartbeat)
        self.heartbeater.start(70, now=False)
        self.portal = portal

    #        self.portal.login(UsernameMD5Password("1012", "test"), None)

    def __del__(self) -> None:
        if self.heartbeater.running:
            self.heartbeater.stop()
        for client in self.clients.values():
            client.transport.loseConnection()

    def heartbeat(self) -> None:
        random_int: int = randint(-214743648, 2147483647)
        self.broadcast(
            FSDClientPacket.makePacket(
                FSDClientPacket.WIND_DELTA + "SERVER",
                "*",
                random_int % 11 - 5,
                random_int % 21 - 10,
            )
        )

    def buildProtocol(self, addr: "IAddress") -> Optional[FSDClientProtocol]:
        if addr.host in client_blacklist:
            return None
        return FSDClientProtocol(self)

    def broadcast(
        self,
        *lines: str,
        check_func: "BroadcastChecker" = lambda _, __: True,
        auto_newline: bool = True,
        from_client: Optional["Client"] = None,
    ) -> None:
        data = "\r\n".join(lines) if auto_newline else "".join(lines)
        for client in self.clients.values():
            if client == from_client:
                continue
            if not check_func(from_client, client):
                continue
            client.transport.write(data.encode())  # type: ignore

    def sendTo(self, callsign: str, *lines: str, auto_newline: bool = True) -> bool:
        try:
            data = "\r\n".join(lines) if auto_newline else "".join(lines)
            self.clients[callsign].transport.write(data)  # type: ignore
            return True
        except KeyError:
            return False
