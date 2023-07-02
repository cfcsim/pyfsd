from typing import TYPE_CHECKING, Callable, Iterable, Literal, Tuple, cast

from twisted.protocols.basic import LineReceiver

from pyfsd.define.packet import FSDCLIENTPACKET, breakPacket, concat, makePacket

if TYPE_CHECKING:
    from constantly import ValueConstant  # type: ignore[import]

    from pyfsd.object.client import Client


Event = Literal["error", "message", "other_packet"]
EventHandler = Callable[[Event, Tuple[bytes, ...]], None]


class FSDClientProtocol(LineReceiver):
    client: "Client"
    handler: "EventHandler"

    def __init__(self, client: "Client", handler: EventHandler) -> None:
        self.client = client
        self.handler = handler

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
            self.handler("error", items[2:])
        elif head is FSDCLIENTPACKET.MESSAGE:
            self.handler("message", items)
        else:
            self.handler("other_packet", items)

    def connectionMade(self):
        if self.client.transport is None:
            self.client.transport = self.transport
