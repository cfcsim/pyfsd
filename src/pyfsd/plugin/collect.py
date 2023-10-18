from typing import TYPE_CHECKING, Iterable, ModuleType, Type, TypeVar

from .interfaces import IPlugin

if TYPE_CHECKING:
    from abc import ABC

__T_ABC = TypeVar("__T_ABC", bound="ABC")


def iterPlugins(root: object, plugin_abc: Type[__T_ABC]) -> Iterable[__T_ABC]:
    for member in root.__dict__.values():
        if isinstance(member, IPlugin) and isinstance(member, plugin_abc):
            yield member


def iterMemberPlugins(root: object, plugin_abc: Type[__T_ABC]) -> Iterable[__T_ABC]:
    for member in root.__dict__.values():
        for plugin in iterPlugins(member, plugin_abc):
            yield plugin
