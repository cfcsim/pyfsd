"""Typings of PyFSD plugin architecture."""

from typing import TYPE_CHECKING, Literal, Tuple, Type, TypedDict, Union

if TYPE_CHECKING:
    from .interfaces import PyFSDPlugin

__all__ = [
    "PluginHandledEventResult",
    "PyFSDHandledEventResult",
    "PyFSDHandledLineResult",
]


class PluginInfo(TypedDict):
    """Info of a PyFSD Plugin.

    Attributes:
        name: Name of this plugin.
        api: API level of this plugin.
        version: int and human readable version of this plugin.
        expected_config: Configuration structure description, in dict or TypedDict.
            structure parameter of pyfsd.define.check_dict function.
            None if this plugin requires no config. (disables config check)
    """

    name: str
    api: int
    version: Tuple[int, str]
    expected_config: Union[Type[TypedDict], dict, None]  # type: ignore[valid-type]


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
