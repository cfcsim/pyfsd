from random import randint
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Mapping, Optional

from twisted.internet.protocol import Factory
from twisted.internet.task import LoopingCall

from ..auth import IUserInfo, UsernameSHA256Password
from ..define.packet import FSDCLIENTPACKET, concat, makePacket
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
    from ..plugin import PluginHandledEventResult, ToHandledByPyFSDEventResult

__all__ = ["FSDClientFactory"]


class FSDClientFactory(Factory):
    clients: Dict[bytes, "Client"]
    portal: "Portal"
    heartbeater: LoopingCall
    blacklist: list
    motd: List[bytes]
    protocol = FSDClientProtocol
    defer_event: Callable[
        [str, Iterable, Mapping, bool, bool, bool],
        "Deferred[PluginHandledEventResult | ToHandledByPyFSDEventResult]",
    ]
    fetch_metar: Callable[[str], "Deferred[Optional[Metar]]"]
    handler_finder: Callable[[str], Iterable[Callable]]

    def __init__(
        self,
        portal: "Portal",
        fetch_metar: Callable[[str], "Deferred[Optional[Metar]]"],
        defer_event: Callable[
            [str, Iterable, Mapping, bool, bool, bool],
            "Deferred[PluginHandledEventResult | ToHandledByPyFSDEventResult]",
        ],
        blacklist: list,
        motd: List[bytes],
    ) -> None:
        self.clients = {}
        self.portal = portal
        self.fetch_metar = fetch_metar
        self.defer_event = defer_event
        self.blacklist = blacklist
        self.motd = motd

    def startFactory(self) -> None:
        self.heartbeater = LoopingCall(self.heartbeat)
        self.heartbeater.start(70, now=False)

    def stopFactory(self) -> None:
        if self.heartbeater.running:
            self.heartbeater.stop()

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
    ) -> bool:
        have_one = False
        data = joinLines(*lines, newline=auto_newline)
        for client in self.clients.values():
            if client == from_client:
                continue
            if not check_func(from_client, client):
                continue
            have_one = True
            client.transport.write(data)  # pyright: ignore
        return have_one

    def sendTo(self, callsign: bytes, *lines: bytes, auto_newline: bool = True) -> bool:
        data = joinLines(*lines, newline=auto_newline)
        try:
            self.clients[callsign].transport.write(data)  # pyright: ignore
            return True
        except KeyError:
            return False

    def login(self, username: str, password: str) -> "Deferred":
        return self.portal.login(  # type: ignore[no-any-return]
            UsernameSHA256Password(username, password), None, IUserInfo
        )
