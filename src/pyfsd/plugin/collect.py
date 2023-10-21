from importlib import import_module
from pkgutil import iter_modules
from typing import TYPE_CHECKING, Callable, Iterable, Optional, Type, TypeVar

from .interfaces import Plugin

if TYPE_CHECKING:
    from abc import ABC
    from types import ModuleType


def iter_submodule(
    path: Iterable[str],
    name: str,
    error_handler: Optional[Callable[[str], None]] = None,
) -> Iterable["ModuleType"]:
    for module_info in iter_modules(path, name + "."):
        try:
            yield import_module(module_info.name)
        except BaseException:
            if error_handler:
                error_handler(module_info.name)
            else:
                raise


__T_ABC = TypeVar("__T_ABC", bound="ABC")


# XXX Incorrect typing?
def iter_plugins(root: object, plugin_abc: Type[__T_ABC]) -> Iterable[__T_ABC]:
    for member in root.__dict__.values():
        if isinstance(member, Plugin) and isinstance(member, plugin_abc):
            yield member


def iter_submodule_plugins(
    root_modules: "ModuleType",
    plugin_abc: Type[__T_ABC],
    error_handler: Optional[Callable[[str], None]] = None,
) -> Iterable[__T_ABC]:
    for module in iter_submodule(
        root_modules.__path__, root_modules.__name__, error_handler
    ):
        for plugin in iter_plugins(module, plugin_abc):
            yield plugin
