"""Typings of PyFSD plugin architecture."""
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from .interfaces import PyFSDPlugin

__all__ = [
    "PluginHandledEventResult",
    "PyFSDHandledEventResult",
    "PyFSDHandledLineResult",
]


class PluginHandledEventResult(TypedDict):
    """A result handled by plugin.

    This means a plugin raised `pyfsd.plugin.PreventEvent`.

    Attributes:
        handled_by_plugin: Event handled by plugin or not.
        plugin: The plugin.
    """

    handled_by_plugin: Literal[True]
    plugin: "PyFSDPlugin"


class PyFSDHandledEventResult(TypedDict):
    """A result handled by PyFSD.

    Attributes:
        handled_by_plugin: Event handled by plugin or not.
        success: The event successfully handled or not.
    """

    handled_by_plugin: Literal[False]
    success: bool


class PyFSDHandledLineResult(PyFSDHandledEventResult):
    """Result of a lineReceivedFromClient event handled by PyFSD.

    Attributes:
        handled_by_plugin (Literal[False]): Event handled by plugin or not.
        success (bool): The event successfully handled or not.
        packet: The packet.
        packet_ok: The packet is valid or not.
        has_result: Has result or not.
    """

    packet_ok: bool
    has_result: bool
    packet: bytes
