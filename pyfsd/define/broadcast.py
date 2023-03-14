from typing import Callable, Optional

from ..object.client import Client
from .utils import calcDistance

BroadcastChecker = Callable[[Optional[Client], Client], bool]


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


def allATCChecker(_: Optional[Client], to_client: Client) -> bool:
    return to_client.type == "ATC"


def allPilotChecker(_: Optional[Client], to_client: Client) -> bool:
    return to_client.type == "ATC"


def atChecker(from_client: Optional[Client], to_client: Client) -> bool:
    assert from_client is not None
    if from_client.position is None or to_client.position is None:
        return False
    distance = calcDistance(from_client.position, to_client.position)
    return distance < from_client.getRange()


def isMulticast(callsign: str) -> bool:
    if callsign == "*":
        return True
    elif callsign == "*A":
        return True
    elif callsign == "*P":
        return True
    elif callsign.startswith("@"):
        return True
    return False
