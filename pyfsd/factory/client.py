from random import randint
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Mapping, Optional

from twisted.internet.defer import succeed
from twisted.internet.protocol import Factory
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread

from ..auth import IUserInfo, UsernameSHA256Password
from ..define.packet import FSDCLIENTPACKET, concat, makePacket
from ..define.utils import joinLines
from ..plugin import PreventEvent
from ..protocol.client import FSDClientProtocol

if TYPE_CHECKING:
    from metar.Metar import Metar
    from twisted.cred.portal import Portal
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IAddress
    from twisted.internet.protocol import Protocol

    from ..define.broadcast import BroadcastChecker
    from ..object.client import Client

__all__ = ["FSDClientFactory"]


class FSDClientFactory(Factory):
    clients: Dict[bytes, "Client"]
    portal: "Portal"
    heartbeater: LoopingCall
    blacklist: list
    motd: List[bytes]
    protocol = FSDClientProtocol
    fetch_metar: Callable[[str], "Deferred[Optional[Metar]]"]
    handler_finder: Callable[[str], Iterable[Callable]]

    def __init__(
        self,
        portal: "Portal",
        fetch_metar: Callable[[str], "Deferred[Optional[Metar]]"],
        handler_finder: Callable[[str], Iterable[Callable]],
        blacklist: list,
        motd: List[bytes],
    ) -> None:
        self.clients = {}
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
            makePacket(
                concat(FSDCLIENTPACKET.WIND_DELTA, "SERVER"),
                "*",
                f"{random_int % 11 - 5}",
                f"{random_int % 21 - 10}",
            ).encode("ascii")
        )

    def buildProtocol(self, addr: "IAddress") -> Optional["Protocol"]:
        if addr.host in self.blacklist:  # type: ignore[attr-defined]
            return None
        return super().buildProtocol(addr)

    def broadcast(
        self,
        *lines: bytes,
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
            client.transport.write(data)  # type: ignore

    def sendTo(self, callsign: bytes, *lines: bytes, auto_newline: bool = True) -> bool:
        data = joinLines(*lines, newline=auto_newline)
        try:
            self.clients[callsign].transport.write(data)  # type: ignore
            return True
        except KeyError:
            return False

    def login(self, username: str, password: str) -> "Deferred":
        return self.portal.login(
            UsernameSHA256Password(username, password), None, IUserInfo
        )

    def triggerEvent(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
        in_thread: bool = True,
        prevent_able: bool = True,
    ) -> "Deferred[bool]":
        def trigger() -> bool:
            for handler in self.event_handler_finder(event_name):
                try:
                    handler(*args, **kwargs)
                except PreventEvent:
                    if not prevent_able:
                        raise
                    return True
            return False

        if in_thread:
            return deferToThread(trigger)
        else:
            return succeed(trigger())
