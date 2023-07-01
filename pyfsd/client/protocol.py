from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Literal, Tuple, cast

from twisted.protocols.basic import LineReceiver

from pyfsd.define.packet import FSDCLIENTPACKET, breakPacket, concat, makePacket

if TYPE_CHECKING:
    from constantly import ValueConstant  # type: ignore[import]

    from pyfsd.object.client import Client


Event = Literal["error", "message", "other_packet"]
EventHandler = Callable[[Tuple[bytes, ...]], None]


class FSDClientProtocol(LineReceiver):
    client: "Client"
    handlers: Dict[Event, List[Tuple[EventHandler, bool]]] = {}

    def callHandlers(self, event: Event, items: Tuple[bytes, ...]) -> None:
        for handler_pair in self.handlers.get(event, []):
            handler, once = handler_pair
            handler(items)
            if once:
                self.handlers[event].remove(handler_pair)

    def __init__(self, client: "Client") -> None:
        self.client = client

    def login(self, password: bytes) -> None:
        if self.client.type == "ATC":
            self.sendLine(
                makePacket(
                    concat(FSDCLIENTPACKET.ADD_ATC, self.client.callsign),
                    b"SERVER",
                    self.client.realname,
                    self.client.cid.encode(),
                    password,
                    b"%d" % self.client.rating,
                    b"%d" % self.client.protocol,
                )
            )
        elif self.client.type == "PILOT":
            self.sendLine(
                makePacket(
                    concat(FSDCLIENTPACKET.ADD_PILOT, self.client.callsign),
                    b"SERVER",
                    self.client.cid.encode(),
                    password,
                    b"%d" % self.client.rating,
                    b"%d" % self.client.protocol,
                    b"%d" % self.client.sim_type,
                    self.client.realname,
                )
            )

    def lineReceived(self, line: bytes) -> None:
        head, items = breakPacket(
            line, cast(Iterable["ValueConstant"], FSDCLIENTPACKET.iterconstants())
        )
        if head is FSDCLIENTPACKET.ERROR:
            self.callHandlers("error", items[2:])
        elif head is FSDCLIENTPACKET.MESSAGE:
            self.callHandlers("message", items)
        else:
            self.callHandlers("other_packet", items)

    def addHandler(
        self, event: Event, handler: EventHandler, once: bool = False
    ) -> None:
        if event not in self.handlers:
            self.handlers[event] = []
        self.handlers[event].append((handler, once))

    def connectionMade(self):
        pass
