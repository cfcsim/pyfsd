"""Tools to collect PyFSD plugins."""

from importlib import import_module
from pkgutil import iter_modules
from typing import TYPE_CHECKING, Callable, Iterable, Optional

if TYPE_CHECKING:
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
