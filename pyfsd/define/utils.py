from re import compile
from typing import TYPE_CHECKING, Callable, Literal, Optional

from haversine import Unit, haversine

from ..object.client import Client

if TYPE_CHECKING:
    from ..object.client import ClientType, Position

__all__ = [
    "BroadcastChecker",
    "strToInt",
    "strToFloat",
    "isCallsignVaild",
    "calcDistance",
    "broadcastCheckerFrom",
    "createBroadcastClientTypeChecker",
    "createBroadcastRangeChecker",
    "broadcastPositionChecker",
    "broadcastMessageChecker",
]
__invaild_char_regex = compile("[!@#$%*:& \t]")

BroadcastChecker = Callable[[Optional[Client], Client], bool]


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


def broadcastCheckerFrom(limit: str) -> Optional[BroadcastChecker]:
    def allATCChecker(_: Optional[Client], to_client: Client) -> bool:
        return to_client.type == "ATC"

    def allPilotChecker(_: Optional[Client], to_client: Client) -> bool:
        return to_client.type == "ATC"

    def allChecker(_: Optional[Client], __: Client) -> bool:
        return True

    def atChecker(from_client: Optional[Client], to_client: Client) -> bool:
        assert from_client is not None
        if from_client.position is None or to_client.position is None:
            return False
        distance = calcDistance(from_client.position, to_client.position)
        return distance < from_client.getRange()

    if limit == "*A":
        return allATCChecker
    elif limit == "*P":
        return allPilotChecker
    elif limit == "*":
        return allChecker
    elif limit.startswith("@"):
        return atChecker
    return None


def createBroadcastClientTypeChecker(
    from_type: Optional["ClientType"] = None,
    to_type: Optional["ClientType"] = None,
) -> BroadcastChecker:
    def checker(from_client: Optional[Client], to_client: Client) -> bool:
        if from_type is not None and (
            from_client is None or from_client.type != from_type
        ):
            return False
        if to_type is not None and to_client.type != to_type:
            return False
        return True

    return checker


def createBroadcastRangeChecker(visual_range: int) -> BroadcastChecker:
    def checker(from_client: Optional[Client], to_client: Client) -> bool:
        assert from_client is not None
        if from_client.position is None or to_client.position is None:
            return False
        distance = calcDistance(from_client.position, to_client.position)
        return distance < visual_range

    return checker


def broadcastPositionChecker(from_client: Optional[Client], to_client: Client) -> bool:
    assert from_client is not None
    if from_client.position is None or to_client.position is None:
        return False
    visual_range: int
    x: int = to_client.getRange()
    y: int = from_client.getRange()
    if to_client.type == "ATC":
        if to_client.visual_range is not None:
            visual_range = to_client.visual_range
        else:
            return False
    elif from_client.type == "PILOT":
        visual_range = x + y
    else:
        if x > y:
            visual_range = x
        else:
            visual_range = y
    distance = calcDistance(from_client.position, to_client.position)
    return distance < visual_range


def broadcastMessageChecker(from_client: Optional[Client], to_client: Client) -> bool:
    assert from_client is not None
    if from_client.position is None or to_client.position is None:
        return False
    visual_range: int
    x: int = to_client.getRange()
    y: int = from_client.getRange()
    if from_client.type == "PILOT" and to_client.type == "PILOT":
        visual_range = x + y
    else:
        if x > y:
            visual_range = x
        else:
            visual_range = y
    distance = calcDistance(from_client.position, to_client.position)
    return distance < visual_range


def broadcastCheckers(*checkers: BroadcastChecker) -> BroadcastChecker:
    def checker(from_client: Optional[Client], to_client: Client) -> bool:
        for checker in checkers:
            if not checker(from_client, to_client):
                return False
        return True

    return checker
