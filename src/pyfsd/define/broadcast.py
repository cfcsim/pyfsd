"""The core of PyFSD broadcast system -- broadcast checker

Example:
    FSDClientFactory.broadcast(..., check_func=atChecker)
"""
from typing import Callable, Optional

from ..object.client import Client
from .utils import calcDistance

BroadcastChecker = Callable[[Optional[Client], Client], bool]


def createBroadcastRangeChecker(visual_range: int) -> BroadcastChecker:
    """Create a broadcast checker which checks visual range.

    Paramaters:
        visual_range: Visual range.

    Returns:
        The broadcast checker.
    """

    def checker(from_client: Optional[Client], to_client: Client) -> bool:
        assert from_client is not None
        if not from_client.position_ok or not to_client.position_ok:
            return False
        distance = calcDistance(from_client.position, to_client.position)
        return distance < visual_range

    return checker


def broadcastPositionChecker(from_client: Optional[Client], to_client: Client) -> bool:
    """A broadcast checker which checks visual range while broadcasting position.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    assert from_client is not None
    if not from_client.position_ok or not to_client.position_ok:
        return False
    visual_range: int
    x: int = to_client.getRange()
    y: int = from_client.getRange()
    if to_client.type == "ATC":
        visual_range = to_client.visual_range
    elif from_client.type == "PILOT":
        visual_range = x + y
    else:
        visual_range = max(x, y)
    distance = calcDistance(from_client.position, to_client.position)
    return distance < visual_range


def broadcastMessageChecker(from_client: Optional[Client], to_client: Client) -> bool:
    """A broadcast checker which checks visual range while broadcasting message.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    assert from_client is not None
    if not from_client.position_ok or not to_client.position_ok:
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
    """Create a set of broadcast.

    Paramaters:
        checkers: The broadcast checkers.

    Returns:
        The broadcast checker.
    """

    def checker(from_client: Optional[Client], to_client: Client) -> bool:
        for checker in checkers:
            if not checker(from_client, to_client):
                return False
        return True

    return checker


def allATCChecker(_: Optional[Client], to_client: Client) -> bool:
    """A broadcast checker which only broadcast to ATC.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    return to_client.type == "ATC"


def allPilotChecker(_: Optional[Client], to_client: Client) -> bool:
    """A broadcast checker which only broadcast to pilot.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    return to_client.type == "ATC"


def atChecker(from_client: Optional[Client], to_client: Client) -> bool:
    """A broadcast checker which checks visual range when dest startswith @.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    assert from_client is not None
    if not from_client.position_ok or not to_client.position_ok:
        return False
    distance = calcDistance(from_client.position, to_client.position)
    return distance < from_client.getRange()


def isMulticast(callsign: str) -> bool:
    """Determine if dest callsign is multicast sign.

    Paramaters:
        callsign: The dest callsign.

    Returns:
        Is multicast or not.
    """
    if callsign == "*":
        return True
    elif callsign == "*A":
        return True
    elif callsign == "*P":
        return True
    elif callsign.startswith("@"):
        return True
    return False
