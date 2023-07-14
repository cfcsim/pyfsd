from typing import AnyStr, Iterable, List, Optional, Tuple, Type, Union, cast, overload

# Not yet typed
from constantly import ValueConstant, Values  # type: ignore[import]

from .utils import constToAnyStr

__all__ = ["concat", "makePacket", "breakPacket", "FSDCLIENTPACKET"]


def concat(*items: Union[AnyStr, ValueConstant]) -> AnyStr:
    temp_part: str = ""
    result: Optional[AnyStr] = None
    result_type: Optional[Union[Type[str], Type[bytes]]] = None
    for item in items:
        is_const = isinstance(item, ValueConstant)
        if result is None or result_type is None:
            if is_const:
                temp_part += item.value  # type: ignore[union-attr]
                continue
            else:
                result_type = type(item)
                assert result_type in (str, bytes), "Invaild type: {result_type!r}"
                result = cast(
                    AnyStr,
                    result_type(
                        temp_part  # type: ignore[arg-type]
                        if result_type is str
                        else temp_part.encode("ascii")
                    ),
                )
        if is_const:
            if result_type is str:
                result += item.value  # type: ignore[union-attr]
            else:
                result += item.value.encode("ascii")  # type: ignore[union-attr]
        else:
            result += item  # type: ignore
    if result is None:
        return cast(AnyStr, temp_part)
    else:
        return cast(AnyStr, result)


def makePacket(*items: Union[AnyStr, ValueConstant]) -> AnyStr:
    temp_part: str = ""
    result: Optional[AnyStr] = None
    result_type: Optional[Union[Type[str], Type[bytes]]] = None
    for item in items:
        is_const = isinstance(item, ValueConstant)
        if result is None or result_type is None:
            if is_const:
                temp_part += item.value + ":"  # type: ignore[union-attr]
                continue
            else:
                result_type = type(item)
                assert result_type in (str, bytes), "Invaild type: {result_type!r}"
                result = cast(
                    AnyStr,
                    result_type(
                        temp_part  # type: ignore[arg-type]
                        if result_type is str
                        else temp_part.encode("ascii")
                    ),
                )
        if result_type is str:
            if is_const:
                result += item.value + ":"  # type: ignore[union-attr]
            else:
                result += item + ":"  # type: ignore[operator]
        else:
            if is_const:
                result += item.value.encode("ascii") + b":"  # type: ignore[union-attr]
            else:
                result += item + b":"  # type: ignore[operator]
    if result is None:
        return cast(AnyStr, temp_part[:-1])
    else:
        return cast(AnyStr, result[:-1])


@overload
def breakPacket(
    packet: AnyStr, heads: Iterable[AnyStr]
) -> Tuple[Optional[AnyStr], Tuple[AnyStr, ...]]:
    ...


@overload
def breakPacket(
    packet: AnyStr, heads: Iterable[ValueConstant]
) -> Tuple[Optional[ValueConstant], Tuple[AnyStr, ...]]:
    ...


@overload
def breakPacket(
    packet: AnyStr, heads: Iterable[Union[AnyStr, ValueConstant]]
) -> Tuple[Optional[Union[AnyStr, ValueConstant]], Tuple[AnyStr, ...]]:
    ...


def breakPacket(
    packet: AnyStr, heads: Iterable[Union[AnyStr, ValueConstant]]
) -> Tuple[Optional[Union[AnyStr, ValueConstant]], Tuple[AnyStr, ...]]:
    packet_type = type(packet)
    assert packet_type in (str, bytes)
    head: Optional[Union[AnyStr, ValueConstant]] = None
    true_head: Optional[AnyStr] = None
    splited_packet: List[AnyStr]
    for may_head in heads:
        if isinstance(may_head, ValueConstant):
            true_head = constToAnyStr(packet_type, may_head)
        else:
            true_head = may_head
        if packet.startswith(true_head):
            head = may_head
            break
    if packet_type is str:
        splited_packet = cast(List[AnyStr], packet.split(":"))  # type: ignore[arg-type]
    elif packet_type is bytes:
        splited_packet = cast(
            List[AnyStr], packet.split(b":")  # type: ignore[arg-type]
        )
    else:
        raise TypeError(f"{packet_type!r}")
    if head is not None and true_head is not None:
        splited_packet[0] = splited_packet[0][len(true_head) :]
    return (head, tuple(splited_packet))


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
