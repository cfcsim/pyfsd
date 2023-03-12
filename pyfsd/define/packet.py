from typing import Any, List, Optional, Tuple, Union

from constantly import ValueConstant, Values

__all__ = ["FSDClientPacket"]


class CLIENTPACKET(Values):
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

    @staticmethod
    def makePacket(*parts: Union[ValueConstant, str, int]) -> str:
        buffer = ""
        for part in parts:
            if isinstance(part, ValueConstant):
                buffer += part.value + ":"
            else:
                buffer += str(part) + ":"
        return buffer[:-1]


class FSDClientPacket:
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
    used_command = [
        ADD_ATC,
        REMOVE_ATC,
        ADD_PILOT,
        REMOVE_PILOT,
        REQUEST_HANDOFF,
        PILOT_POSITION,
        ATC_POSITION,
        PING,
        PONG,
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

    @staticmethod
    def makePacket(*packet: Union[str, int]) -> str:
        return ":".join([str(item) for item in packet])

    @classmethod
    def breakPacket(cls, packet: str) -> Tuple[Optional[str], List[str]]:
        if len(packet) < 1:
            return (None, packet.split(":"))
        if packet[0] in [cls.PILOT_POSITION, cls.ATC_POSITION]:
            return (packet[0], packet[1:].split(":"))
        if len(packet) < 3:
            return (None, packet.split(":"))
        if packet[0:3] in cls.used_command:
            return (packet[0:3], packet[3:].split(":"))
        return (None, packet.split(":"))
