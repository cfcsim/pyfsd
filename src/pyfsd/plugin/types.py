"""Typings of PyFSD plugin architecture."""
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from .interfaces import IPyFSDPlugin

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
    plugin: "IPyFSDPlugin"


class PyFSDHandledEventResult(TypedDict):
    """A result handled by PyFSD.

    Attributes:
        handled_by_plugin: Event handled by plugin or not.
        success: The event successfully handled or not.
    """

    handled_by_plugin: Literal[False]
    success: bool


class PyFSDHandledLineResult(PyFSDHandledEventResult):
    """A lineReceivedFromClient result handled by PyFSD.

    Attributes:
        handled_by_plugin (Literal[False]): Event handled by plugin or not.
        success (bool): The event successfully handled or not.
        packet_ok: The packet is correct or not.
        has_result: Succeed in generating result or not.
    """

    packet_ok: bool
    has_result: bool
