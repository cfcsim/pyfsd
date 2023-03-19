from re import compile
from typing import TYPE_CHECKING

from haversine import Unit, haversine

if TYPE_CHECKING:
    from ..object.client import Position

__all__ = [
    "strToInt",
    "strToFloat",
    "isCallsignVaild",
    "calcDistance",
    "joinLines",
]
__invaild_char_regex = compile("[!@#$%*:& \t]")


def strToInt(string: str, default_value: int = 0) -> int:
    try:
        return int(string)
    except ValueError:
        return default_value


def strToFloat(string: str, default_value: float = 0.0) -> float:
    try:
        return float(string)
    except ValueError:
        return default_value


def calcDistance(
    from_position: "Position", to_position: "Position", unit=Unit.NAUTICAL_MILES
) -> float:
    return haversine(from_position, to_position, unit=unit)


def isCallsignVaild(callsign: str) -> bool:
    global __invaild_char_regex
    if len(callsign) < 2 or len(callsign) > 12:
        return False
    if __invaild_char_regex.search(callsign) is not None:
        return False
    return True


def joinLines(*lines: str, newline: bool = True) -> str:
    if newline:
        return "\r\n".join(lines) + "\r\n"
    else:
        return "".join(lines)
