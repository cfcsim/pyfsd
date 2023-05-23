from typing import AnyStr, List, Optional, Tuple, Union, cast

# Not yet typed
from constantly import ValueConstant, Values  # type: ignore[import]

from .utils import asciiOnly, assertNoDuplicate

__all__ = ["makePacket", "breakPacket", "FSDCLIENTPACKET"]


def _makePacket(
    *items: AnyStr, all_str: bool = False, all_bytes: bool = False
) -> AnyStr:
    if all(isinstance(item, str) for item in items) or all_str:
        return ":".join(items)  # type: ignore
    elif all(isinstance(item, bytes) for item in items) or all_bytes:
        return b":".join(items)  # type: ignore
    else:
        raise ValueError("Cannot mix str and bytes")


def makePacket(*_items: Union[AnyStr, ValueConstant]) -> AnyStr:
    items = []
    all_str = all(isinstance(item, (str, ValueConstant)) for item in _items)
    all_bytes = all(isinstance(item, (bytes, ValueConstant)) for item in _items)
    if not (all_str or all_bytes):
        raise ValueError("Cannot mix str and bytes")
    for item in _items:
        if isinstance(item, ValueConstant):
            if not (isinstance(item.value, str) or asciiOnly(item.value)):
                raise ValueError(f"Invaild constant value: {item.value!r}")
            items.append(item.value if all_str else item.value.encode("ascii"))
        else:
            items.append(item)
    return _makePacket(*items, all_str=all_str, all_bytes=all_bytes)


def _breakPacket(
    packet: AnyStr, *heads: AnyStr
) -> Tuple[Optional[AnyStr], Tuple[AnyStr, ...]]:
    assert isinstance(packet, (str, bytes))
    assertNoDuplicate(heads)
    head: Optional[AnyStr] = None
    splited_packet: List[AnyStr]
    for may_head in heads:
        if packet.startswith(may_head):
            head = may_head
    if isinstance(packet, str):
        splited_packet = cast(List[AnyStr], packet.split(":"))
    elif isinstance(packet, bytes):
        splited_packet = cast(List[AnyStr], packet.split(b":"))
    if head is not None:
        splited_packet[0] = splited_packet[0][len(head) :]
    return (head, tuple(splited_packet))


def breakPacket(
    packet: AnyStr, *_heads: Union[AnyStr, ValueConstant]
) -> Tuple[Optional[AnyStr], Tuple[AnyStr, ...]]:
    heads = []
    all_str = all(isinstance(head, (str, ValueConstant)) for head in _heads)
    all_bytes = all(isinstance(head, (bytes, ValueConstant)) for head in _heads)
    if not (all_str or all_bytes):
        raise ValueError("Cannot mix str and bytes")
    for head in _heads:
        if isinstance(head, ValueConstant):
            if not (isinstance(head.value, str) or asciiOnly(head.value)):
                raise ValueError(f"Invaild constant value: {head.value!r}")
            heads.append(head.value if all_str else head.value.encode("ascii"))
        else:
            heads.append(head)
    return _breakPacket(packet, *heads)


class FSDCLIENTPACKET(Values):
    ADD_ATC = ValueConstant("#AA")
    REMOVE_ATC = ValueConstant("#DA")
    ADD_PILOT = ValueConstant("#AP")
    REMOVE_PILOT = ValueConstant("#DP")
    REQUEST_HANDOFF = ValueConstant("$HO")
    MESSAGE = ValueConstant("#TM")
    REQUEST_WEATHER = ValueConstant("#RW")
    PILOT_POSITION = ValueConstant("@")
    ATC_POSITION = ValueConstant("%")
    PING = ValueConstant("$PI")
    PONG = ValueConstant("$PO")
    AC_HANDOFF = ValueConstant("$HA")
    PLAN = ValueConstant("$FP")
    SB = ValueConstant("#SB")
    PC = ValueConstant("#PC")
    WEATHER = ValueConstant("#WX")
    CLOUD_DATA = ValueConstant("#CD")
    WIND_DATA = ValueConstant("#WD")
    TEMP_DATA = ValueConstant("#TD")
    REQUEST_COMM = ValueConstant("$C?")
    REPLY_COMM = ValueConstant("$CI")
    REQUEST_ACARS = ValueConstant("$AX")
    REPLY_ACARS = ValueConstant("$AR")
    ERROR = ValueConstant("$ER")
    CQ = ValueConstant("$CQ")
    CR = ValueConstant("$CR")
    KILL = ValueConstant("$!!")
    WIND_DELTA = ValueConstant("#DL")
    client_used_command = [
        ADD_ATC,
        REMOVE_ATC,
        ADD_PILOT,
        REMOVE_PILOT,
        REQUEST_HANDOFF,
        PILOT_POSITION,
        ATC_POSITION,
        PING,
        PONG,
        MESSAGE,
        AC_HANDOFF,
        PLAN,
        SB,
        PC,
        WEATHER,
        REQUEST_COMM,
        REPLY_COMM,
        REQUEST_ACARS,
        CQ,
        CR,
        KILL,
    ]
