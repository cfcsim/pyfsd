from random import randint
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional
from weakref import WeakValueDictionary

from twisted.internet.protocol import Factory
from twisted.internet.task import LoopingCall

from ..auth import IUserInfo, UsernameSHA256Password
from ..define.packet import FSDClientPacket
from ..define.utils import joinLines
from ..protocol.client import FSDClientProtocol

if TYPE_CHECKING:
    from metar.Metar import Metar
    from twisted.cred.portal import Portal
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IAddress
    from twisted.internet.protocol import Protocol

    from ..define.broadcast import BroadcastChecker
    from ..object.client import Client
    from ..plugin import IPyFSDPlugin

__all__ = ["FSDClientFactory"]


class FSDClientFactory(Factory):
    clients: WeakValueDictionary[str, "Client"] = WeakValueDictionary()
    portal: "Portal"
    heartbeater: LoopingCall
    blacklist: list
    motd: List[str]
    protocol = FSDClientProtocol
    fetch_metar: Callable[[str], "Deferred[Optional[Metar]]"]
    handler_finder: Callable[[str], Iterable["IPyFSDPlugin"]]

    def __init__(
        self,
        portal: "Portal",
        fetch_metar: Callable[[str], "Deferred[Optional[Metar]]"],
        handler_finder: Callable[[str], Iterable["IPyFSDPlugin"]],
        blacklist: list,
        motd: List[str],
    ) -> None:
        self.portal = portal
        self.fetch_metar = fetch_metar
        self.event_handler_finder = handler_finder
        self.blacklist = blacklist
        self.motd = motd

    def startFactory(self) -> None:
        self.heartbeater = LoopingCall(self.heartbeat)
        self.heartbeater.start(70, now=False)

    def stopFactory(self):
        if self.heartbeater.running:
            self.heartbeater.stop()

    #   for client in self.clients.values():
    #       client.transport.loseConnection()

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

    def buildProtocol(self, addr: "IAddress") -> Optional["Protocol"]:
        if addr.host in self.blacklist:
            return None
        return super().buildProtocol(addr)

    def broadcast(
        self,
        *lines: str,
        check_func: "BroadcastChecker" = lambda _, __: True,
        auto_newline: bool = True,
        from_client: Optional["Client"] = None,
    ) -> None:
        data = joinLines(*lines, newline=auto_newline)
        for client in self.clients.values():
            if client == from_client:
                continue
            if not check_func(from_client, client):
                continue
            client.transport.write(data.encode())  # type: ignore

    def sendTo(self, callsign: str, *lines: str, auto_newline: bool = True) -> bool:
        data = joinLines(*lines, newline=auto_newline)
        try:
            self.clients[callsign].transport.write(data.encode())  # type: ignore
            return True
        except KeyError:
            return False

    def login(self, username: str, password: str) -> "Deferred":
        return self.portal.login(
            UsernameSHA256Password(username, password), None, IUserInfo
        )
