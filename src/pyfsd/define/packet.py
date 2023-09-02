from collections.abc import Sequence
from enum import Enum
from typing import AnyStr, Iterable, List, Optional, Tuple, Type, Union, cast, overload

from twisted.python.deprecate import deprecated

from .utils import asciiOnly

__all__ = [
    "concat",
    "makePacket",
    "breakPacket",
    "FSDCLIENTPACKET",
    "CLIENT_USED_COMMAND",
    "CompatibleString",
    "SPLIT_SIGN",
]


class CompatibleString:
    value: str

    def __init__(self, value: str) -> None:
        assert asciiOnly(value), "String can only contain ASCII characters"
        self.value = value

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f'CompatibleString("{self.value}")'

    def __int__(self) -> int:
        return int(self.value)

    def __float__(self) -> float:
        return float(self.value)

    def __complex__(self) -> complex:
        return complex(self.value)

    def __bytes__(self) -> bytes:
        return self.value.encode()

    def __hash__(self) -> int:
        return hash(self.value)

    def __getnewargs__(self) -> Tuple[str]:
        return (self.value[:],)

    def __eq__(self, value: object) -> bool:
        if isinstance(value, CompatibleString):
            return self.value == value.value
        elif isinstance(value, str):
            return self.value == value
        elif isinstance(value, bytes):
            return self.value.encode() == value
        else:
            return NotImplemented

    def __lt__(self, value: object) -> bool:
        if isinstance(value, CompatibleString):
            return self.value < value.value
        elif isinstance(value, str):
            return self.value < value
        elif isinstance(value, bytes):
            return self.value.encode() < value
        else:
            return NotImplemented

    def __le__(self, value: object) -> bool:
        if isinstance(value, CompatibleString):
            return self.value <= value.value
        elif isinstance(value, str):
            return self.value <= value
        elif isinstance(value, bytes):
            return self.value.encode() <= value
        else:
            return NotImplemented

    def __gt__(self, value: object) -> bool:
        if isinstance(value, CompatibleString):
            return self.value > value.value
        elif isinstance(value, str):
            return self.value > value
        elif isinstance(value, bytes):
            return self.value.encode() > value
        else:
            return NotImplemented

    def __ge__(self, value: object) -> bool:
        if isinstance(value, CompatibleString):
            return self.value >= value.value
        elif isinstance(value, str):
            return self.value >= value
        elif isinstance(value, bytes):
            return self.value.encode() >= value
        else:
            return NotImplemented

    def __contains__(self, part: Union[str, bytes, "CompatibleString"]) -> bool:
        if isinstance(part, CompatibleString):
            return part.value in self.value
        elif isinstance(part, str):
            return part in self.value
        elif isinstance(part, bytes):
            return part in self.value.encode()
        else:
            raise TypeError(
                "'in <CompatibleString>' requires string or bytes or "
                f"CompatibleString as left operand, not {type(part).__name__}"
            )

    def __len__(self) -> int:
        return len(self.value)

    def __getitem__(self, index: Union[int, slice]) -> "CompatibleString":
        return self.__class__(self.value[index])

    @overload
    def __add__(self, other: str) -> str:
        ...

    @overload
    def __add__(self, other: bytes) -> bytes:
        ...

    @overload
    def __add__(self, other: "CompatibleString") -> "CompatibleString":
        ...

    def __add__(self, other: object) -> object:
        if isinstance(other, CompatibleString):
            return CompatibleString(self.value + other.value)
        elif isinstance(other, str):
            return self.value + other
        elif isinstance(other, bytes):
            return self.value.encode() + other
        else:
            return NotImplemented

    @overload
    def __radd__(self, other: str) -> str:
        ...

    @overload
    def __radd__(self, other: bytes) -> bytes:
        ...

    @overload
    def __radd__(self, other: "CompatibleString") -> "CompatibleString":
        ...

    def __radd__(self, other: object) -> object:
        if isinstance(other, CompatibleString):
            return other.value + self.value
        elif isinstance(other, str):
            return other + self.value
        elif isinstance(other, bytes):
            return other + self.value.encode()
        else:
            return NotImplemented

    def __mul__(self, n: int) -> "CompatibleString":
        return self.__class__(self.value * n)

    def __rmul__(self, n: int) -> "CompatibleString":
        return self.__class__(self.value * n)

    def __mod__(self, args: Union[tuple, object]) -> "CompatibleString":
        return self.__class__(self.value % args)

    @overload
    def __rmod__(self, template: str) -> str:
        ...

    @overload
    def __rmod__(self, template: bytes) -> bytes:
        ...

    @overload
    def __rmod__(self, template: "CompatibleString") -> "CompatibleString":
        ...

    def __rmod__(self, template: object) -> object:
        # Useless?
        if isinstance(template, CompatibleString):
            # ????
            return template % self
        elif isinstance(template, str):
            return template % self.value
        elif isinstance(template, bytes):
            return template % self.value.encode()
        else:
            return NotImplemented

    def asType(self, type_: Type[AnyStr]) -> AnyStr:
        if type_ is str:
            return self.value  # type: ignore[return-value]
        elif type_ is bytes:
            return self.value.encode()  # type: ignore[return-value]
        else:
            raise TypeError(f"Invaild string type: {type_}")


Sequence.register(CompatibleString)
SPLIT_SIGN = CompatibleString(":")


class FSDCLIENTPACKET(CompatibleString, Enum):
    __init__ = Enum.__init__  # type: ignore[assignment]
    ADD_ATC = "#AA"
    REMOVE_ATC = "#DA"
    ADD_PILOT = "#AP"
    REMOVE_PILOT = "#DP"
    REQUEST_HANDOFF = "$HO"
    MESSAGE = "#TM"
    REQUEST_WEATHER = "#RW"
    PILOT_POSITION = "@"
    ATC_POSITION = "%"
    PING = "$PI"
    PONG = "$PO"
    AC_HANDOFF = "$HA"
    PLAN = "$FP"
    SB = "#SB"
    PC = "#PC"
    WEATHER = "#WX"
    CLOUD_DATA = "#CD"
    WIND_DATA = "#WD"
    TEMP_DATA = "#TD"
    REQUEST_COMM = "$C?"
    REPLY_COMM = "$CI"
    REQUEST_ACARS = "$AX"
    REPLY_ACARS = "$AR"
    ERROR = "$ER"
    CQ = "$CQ"
    CR = "$CR"
    KILL = "$!!"
    WIND_DELTA = "#DL"


@deprecated(
    type("_dv", (), {"package": "pyfsd", "short": lambda: "0.0.2.dev0"}), "+ operator"
)
def concat(*items: Union[AnyStr, FSDCLIENTPACKET]) -> AnyStr:
    result = items[0]
    for item in items[1:]:
        result += item  # type: ignore[assignment]
    if isinstance(result, FSDCLIENTPACKET):
        raise ValueError("Must contain str or bytes")
    return cast(AnyStr, result)


def makePacket(*items: Union[AnyStr, FSDCLIENTPACKET]) -> AnyStr:
    result = CompatibleString("")
    for item in items:
        result += item + SPLIT_SIGN  # type: ignore[assignment]
    if isinstance(result, FSDCLIENTPACKET):
        raise ValueError("Must contain str or bytes")
    return cast(AnyStr, result[:-1])


@overload
def breakPacket(
    packet: AnyStr, heads: Iterable[AnyStr]
) -> Tuple[Optional[AnyStr], Tuple[AnyStr, ...]]:
    ...


@overload
def breakPacket(
    packet: AnyStr, heads: Iterable[FSDCLIENTPACKET]
) -> Tuple[Optional[FSDCLIENTPACKET], Tuple[AnyStr, ...]]:
    ...


@overload
def breakPacket(
    packet: AnyStr, heads: Iterable[Union[AnyStr, FSDCLIENTPACKET]]
) -> Tuple[Optional[Union[AnyStr, FSDCLIENTPACKET]], Tuple[AnyStr, ...]]:
    ...


def breakPacket(
    packet: AnyStr, heads: Iterable[Union[AnyStr, FSDCLIENTPACKET]]
) -> Tuple[Optional[Union[AnyStr, FSDCLIENTPACKET]], Tuple[AnyStr, ...]]:
    packet_type = type(packet)
    assert packet_type in (str, bytes)
    head: Optional[Union[AnyStr, FSDCLIENTPACKET]] = None
    splited_packet: List[AnyStr]
    for may_head in heads:
        true_head: AnyStr
        if isinstance(may_head, FSDCLIENTPACKET):
            true_head = may_head.asType(packet_type)
        else:
            true_head = may_head  # type: ignore[assignment]
        if packet.startswith(true_head):
            head = may_head
            break
    splited_packet = packet.split(SPLIT_SIGN.asType(packet_type))
    if head is not None:
        splited_packet[0] = splited_packet[0][len(head) :]
    return (head, tuple(splited_packet))


CLIENT_USED_COMMAND = [
    FSDCLIENTPACKET.ADD_ATC,
    FSDCLIENTPACKET.REMOVE_ATC,
    FSDCLIENTPACKET.ADD_PILOT,
    FSDCLIENTPACKET.REMOVE_PILOT,
    FSDCLIENTPACKET.REQUEST_HANDOFF,
    FSDCLIENTPACKET.PILOT_POSITION,
    FSDCLIENTPACKET.ATC_POSITION,
    FSDCLIENTPACKET.PING,
    FSDCLIENTPACKET.PONG,
    FSDCLIENTPACKET.MESSAGE,
    FSDCLIENTPACKET.AC_HANDOFF,
    FSDCLIENTPACKET.PLAN,
    FSDCLIENTPACKET.SB,
    FSDCLIENTPACKET.PC,
    FSDCLIENTPACKET.WEATHER,
    FSDCLIENTPACKET.REQUEST_COMM,
    FSDCLIENTPACKET.REPLY_COMM,
    FSDCLIENTPACKET.REQUEST_ACARS,
    FSDCLIENTPACKET.CQ,
    FSDCLIENTPACKET.CR,
    FSDCLIENTPACKET.KILL,
]
