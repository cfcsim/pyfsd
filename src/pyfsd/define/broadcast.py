"""The core of PyFSD broadcast system -- broadcast checker.

Example:
    FSDClientFactory.broadcast(..., check_func=atChecker)
"""

from typing import Callable, Optional

from pyfsd.object.client import Client

from .utils import calc_distance

BroadcastChecker = Callable[[Optional[Client], Client], bool]


def create_broadcast_range_checker(visual_range: int) -> BroadcastChecker:
    """Create a broadcast checker which checks visual range.

    Paramaters:
        visual_range: Visual range.

    Returns:
        The broadcast checker.
    """

    def checker(from_client: Optional[Client], to_client: Client) -> bool:
        if from_client is None:
            raise RuntimeError("broadcast_range_checker needs from_client")
        if not from_client.position_ok or not to_client.position_ok:
            return False
        distance = calc_distance(from_client.position, to_client.position)
        return distance < visual_range

    return checker


def broadcast_position_checker(
    from_client: Optional[Client],
    to_client: Client,
) -> bool:
    """A broadcast checker which checks visual range while broadcasting position.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    if from_client is None:
        raise RuntimeError("broadcast_position_checker needs from_client")
    if not from_client.position_ok or not to_client.position_ok:
        return False
    visual_range: int
    x: int = to_client.get_range()
    y: int = from_client.get_range()
    if to_client.is_controller:
        visual_range = to_client.visual_range
    elif not from_client.is_controller:
        visual_range = x + y
    else:
        visual_range = max(x, y)
    distance = calc_distance(from_client.position, to_client.position)
    return distance < visual_range


def broadcast_message_checker(from_client: Optional[Client], to_client: Client) -> bool:
    """A broadcast checker which checks visual range while broadcasting message.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    if from_client is None:
        raise RuntimeError("broadcast_message_checker needs from_client")
    if not from_client.position_ok or not to_client.position_ok:
        return False
    visual_range: int
    x: int = to_client.get_range()
    y: int = from_client.get_range()
    if (not from_client.is_controller) and (not to_client.is_controller):
        visual_range = x + y
    else:
        visual_range = max(y, x)
    distance = calc_distance(from_client.position, to_client.position)
    return distance < visual_range


def broadcast_checkers(*checkers: BroadcastChecker) -> BroadcastChecker:
    """Create a set of broadcast.

    Paramaters:
        checkers: The broadcast checkers.

    Returns:
        The broadcast checker.
    """

    def checker(from_client: Optional[Client], to_client: Client) -> bool:
        return all(checker(from_client, to_client) for checker in checkers)

    return checker


def all_ATC_checker(_: Optional[Client], to_client: Client) -> bool:  # noqa: N802
    """A broadcast checker which only broadcast to ATC.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    return to_client.is_controller


def all_pilot_checker(_: Optional[Client], to_client: Client) -> bool:
    """A broadcast checker which only broadcast to pilot.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    return not to_client.is_controller


def at_checker(from_client: Optional[Client], to_client: Client) -> bool:
    """A broadcast checker which checks visual range when dest startswith @.

    Paramaters:
        from_client: The from client.
        to_client: The dest client.

    Returns:
        The check result (send message to to_client or not).
    """
    if from_client is None:
        raise RuntimeError("at_checker needs from_client")
    if not from_client.position_ok or not to_client.position_ok:
        return False
    distance = calc_distance(from_client.position, to_client.position)
    return distance < from_client.get_range()


def is_multicast(callsign: str) -> bool:
    """Determine if dest callsign is multicast sign.

    Paramaters:
        callsign: The dest callsign.

    Returns:
        Is multicast or not.
    """
    return callsign in {"*", "*A"} or (callsign == "*P" or callsign.startswith("@"))
