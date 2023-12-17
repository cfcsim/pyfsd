"""Tools to collect PyFSD plugins."""
from importlib import import_module
from pkgutil import iter_modules
from typing import TYPE_CHECKING, Callable, Iterable, Optional, Type, TypeVar

from .interfaces import Plugin

if TYPE_CHECKING:
    from abc import ABC
    from types import ModuleType


def iter_submodules(
    path: Iterable[str],
    name: str,
    error_handler: Optional[Callable[[str], None]] = None,
) -> Iterable["ModuleType"]:
    """Yields {name}'s submodules on path.

    Args:
        path: search path, like package.__path__
        name: package name, like package.__name__
        error_handler: Handler that will be called because of uncaught exception

    Returns:
        Submodules.
    """
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
    """Yield objects that implemented specified ABC in a root object.

    Args:
        root: The root object to be iterated.
        plugin_abc: The ABC.

    Returns:
        objects that implemented plugin_abc.
    """
    for member in root.__dict__.values():
        if isinstance(member, Plugin) and isinstance(member, plugin_abc):
            yield member


def iter_submodule_plugins(
    root_module: "ModuleType",
    plugin_abc: Type[__T_ABC],
    error_handler: Optional[Callable[[str], None]] = None,
) -> Iterable[__T_ABC]:
    """Yield objects that implemented specified ABC in a root module.

    Args:
        root_module: The root module to be iterated.
        plugin_abc: The ABC.
        error_handler: Handler that will be called because of uncaught exception

    Returns:
        objects that implemented plugin_abc.
    """
    for module in iter_submodules(
        root_module.__path__, root_module.__name__, error_handler
    ):
        for plugin in iter_plugins(module, plugin_abc):
            yield plugin
