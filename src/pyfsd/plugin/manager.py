"""PyFSD plugin manager.

Attributes:
    PLUGIN_EVENTS: All available PyFSD plugin events.
"""

from abc import ABC
from asyncio import CancelledError
from inspect import getfile, getmro
from os import getcwd
from sys import exc_info
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
)

from structlog import get_logger

from .. import plugins
from ..define.check_dict import check_dict
from ..define.utils import iter_callable, str_to_int
from . import API_LEVEL, PreventEvent
from .collect import iter_plugins, iter_submodules
from .interfaces import Plugin, PyFSDPlugin
from .types import PluginHandledEventResult, PluginInfo

if TYPE_CHECKING:
    from types import ModuleType

_T_ABC = TypeVar("_T_ABC", bound=ABC)

logger = get_logger(__name__)
__all__ = [
    "format_plugin",
    "PLUGIN_EVENTS",
    "PluginManager",
]

PLUGIN_EVENTS = tuple(func.__name__ for func in iter_callable(PyFSDPlugin))


class InternalPluginFileInfo(PluginInfo):
    """Internal plugin file info used in PyFSD plugin manager.

    Note that in PluginInfo, we call a file a plugin. There, we call every class that
        implemented Plugin as a plugin.

    Attributes:
        name (str): Name of this plugin file.
        api (int): API level of this plugin file.
        version (tuple[int, str]): int and human readable version of this plugin file.
        expected_config (type[TypedDict] | dict | None):
            Configuration structure description, in dict or TypedDict.
            structure parameter of pyfsd.define.check_dict function.
            None if this plugin requires no config. (disables config check)
        path: Path of this plugin file.
        plugins: All plugins under the file.
    """

    path: str
    plugins: Tuple[ABC, ...]


def deal_exception(name: str) -> None:
    """Handle exceptions when importing plugins."""
    type_, exception, traceback = exc_info()

    # Cut traceback to plugin file
    current_traceback = traceback
    while (
        current_traceback is not None
        and current_traceback.tb_next is not None
        and current_traceback.tb_frame.f_code.co_name != "<module>"
    ):
        current_traceback = current_traceback.tb_next
    traceback = current_traceback

    logger.exception(
        f"Error happened during load plugin {name}",
        exc_info=(type_, exception, traceback),
    )


_cwd = getcwd()


def get_plugin_file_info(plugin: "ModuleType") -> Optional[InternalPluginFileInfo]:
    """Get a plugin file's info.

    Note that this function won't collect the plugins attribute.

    Args:
        plugin: The plugin.

    Returns:
        The info or None.
    """
    orig_plugin_info = getattr(plugin, "plugin_info", None)
    if orig_plugin_info is None:
        return None
    name = orig_plugin_info.get("name", getfile(plugin).split("/")[-1][:-3])
    api = str_to_int(str(orig_plugin_info.get("api", -1)), default_value=-1)
    orig_version = orig_plugin_info.get("version", (0, "unknown"))
    if isinstance(orig_version, tuple) and len(orig_version) >= 2:
        version = (str_to_int(str(orig_version[0]), 0), str(orig_version[1]))
    else:
        version = (0, "unknown")
    orig_expected_config = orig_plugin_info.get("expected_config", None)
    return {
        "name": name,
        "api": api,
        "version": version,
        "expected_config": orig_expected_config
        if isinstance(orig_expected_config, dict)
        else None,
        "path": getfile(plugin),
        "plugins": (),
    }


def brief_path(path: str) -> str:
    """Shorten filepath to relative one if it's under current working directory."""
    if path.startswith(_cwd):
        return path[len(_cwd) + 1 :]
    return path


def format_plugin(info: InternalPluginFileInfo, with_version: bool = False) -> str:
    """Format a plugin file into string.

    Args:
        info: The plugin file's info.
        with_version: Append version to result or not.

    Returns:
        The formatted result.
    """
    return (
        f"{info['name']}"
        + (f" {info['version'][1]} ({info['version'][0]}) " if with_version else "")
        + f"({brief_path(info['path'])})"
    )


class Plugins(Dict):
    """A dict that stores all collected plugins, sorted by ABC.

    plugins_dict[ABC] => List[Plugins implemented ABC]
    """

    def __getitem__(self, __key: Type[_T_ABC]) -> List[_T_ABC]:
        return super().__getitem__(__key)  # type: ignore[no-any-return]

    def __setitem__(self, __key: Type[_T_ABC], __value: List[_T_ABC]) -> None:
        return super().__setitem__(__key, __value)


class PluginManager:
    """PyFSD Plugin manager.

    Attributes:
        all_plugins: All collected plugin files.
        sorted_plugins: Dict[ABC Class, Tuple[All plugins implemented this ABC, ...]]
        sorted_pyfsd_plugins:
            Dict[Event name, Tuple[All plugins that will handle the event, ...]]
    """

    all_plugins: Optional[Tuple[InternalPluginFileInfo, ...]] = None
    sorted_plugins: Optional[Plugins] = None
    sorted_pyfsd_plugins: Optional[Dict[str, List[PyFSDPlugin]]] = None

    def pick_plugins(self, plugin_config_root: dict) -> None:
        """Pick all plugins into self.all_plugins & self.sorted_plugins."""
        plugins_dict: Plugins = Plugins()
        all_plugin_infos: List[InternalPluginFileInfo] = []
        all_plugins: List[ABC] = []  # to find repeated plugins TODO better solution
        for module in iter_submodules(
            plugins.__path__, plugins.__name__, deal_exception
        ):
            plugin_info = get_plugin_file_info(module)
            if plugin_info is None:
                logger.warning("Invalid plugin file: %s", brief_path(getfile(module)))
                continue
            # Check API
            if plugin_info["api"] != API_LEVEL:
                logger.error(
                    "Cannot load plugin %s: needs API %d",
                    plugin_info["name"],
                    plugin_info["api"],
                )
                continue
            # Check config
            if plugin_info["expected_config"] is not None:
                plugin_config = plugin_config_root.get(plugin_info["name"], None)
                if plugin_config is None:
                    logger.error(
                        "Cannot load plugin %s: config required",
                        plugin_info["name"],
                    )
                    continue
                config_errors = tuple(
                    check_dict(
                        plugin_config,
                        plugin_info["expected_config"],
                        name=f"plugin[{plugin_info['name']!r}]",
                        allow_unexpected_key=True,
                    )
                )
                if config_errors:
                    error_string = f"Cannot load plugin {plugin_info['name']}:\n"
                    for config_error in config_errors:
                        error_string += str(config_error) + "\n"
                    logger.error(error_string.rstrip("\n"))
                    continue
            # Nothing wrong, load it
            logger.debug(
                "Loading plugin %s", format_plugin(plugin_info, with_version=True)
            )

            file_plugins = []
            for plugin in iter_plugins(module, Plugin):
                if plugin in all_plugins:  # Detect repeated plugins
                    continue
                all_plugins.append(plugin)
                file_plugins.append(plugin)
                plugin_class = type(plugin)
                for cls in getmro(plugin_class):
                    if issubclass(cls, ABC) and cls not in (plugin_class, Plugin, ABC):
                        if cls not in plugins_dict:
                            plugins_dict[cls] = []
                        plugins_dict[cls].append(plugin)
            plugin_info["plugins"] = tuple(file_plugins)
            all_plugin_infos.append(plugin_info)
        self.sorted_plugins = plugins_dict
        self.all_plugins = tuple(all_plugin_infos)
        self.sort_pyfsd_plugins()

    def get_plugins(self, plugin_abc: Type[_T_ABC]) -> List[_T_ABC]:
        """Get list of plugins that implemented specified ABC."""
        if self.sorted_plugins is None:
            raise RuntimeError("Plugins not picked")
        if plugin_abc not in self.sorted_plugins:
            return []
        return self.sorted_plugins[plugin_abc]

    def sort_pyfsd_plugins(self) -> None:
        """Sort PyFSD plugins into self.pyfsd_plugins."""
        event_handlers: Dict[str, List[PyFSDPlugin]] = {
            name: [] for name in PLUGIN_EVENTS
        }
        for plugin in self.get_plugins(PyFSDPlugin):
            for event in PLUGIN_EVENTS:
                if hasattr(plugin, event) and getattr(
                    type(plugin),
                    event,
                ) is not getattr(PyFSDPlugin, event):
                    event_handlers[event].append(plugin)

        self.sorted_pyfsd_plugins = event_handlers

    def iter_plugin_by_event_name(self, event_name: str) -> Iterable[PyFSDPlugin]:
        """Yields all plugins that handles specified event.

        Args:
            event_name: The event's name. Must be in PLUGIN_EVENTS

        Returns:
            The plugin.
        """
        if self.sorted_pyfsd_plugins is None:
            raise RuntimeError("PyFSD plugins not loaded")
        if event_name not in PLUGIN_EVENTS:
            msg = f"Invaild event {event_name}"
            raise ValueError(msg)
        yield from self.sorted_pyfsd_plugins[event_name]

    def iter_handler_by_event_name(self, event_name: str) -> Iterable[Callable]:
        """Yields event handler of all plugins that handles specified event.

        Args:
            event_name: The event's name. Must be in PLUGIN_EVENTS

        Returns:
            The event handler, {plugin}.{event_name}
        """
        return (
            getattr(plugin, event_name)
            for plugin in self.iter_plugin_by_event_name(event_name)
        )

    async def trigger_event(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
        prevent_able: bool = False,
    ) -> "PluginHandledEventResult | None":
        """Trigger a event and spread it to plugins."""
        for plugin in self.iter_plugin_by_event_name(event_name):
            try:
                await getattr(plugin, event_name)(*args, **kwargs)
            except PreventEvent as prevent_result:
                if not prevent_able:
                    await logger.aerror(
                        f"Error happened in {plugin!r}: Cannot prevent event: "
                        + event_name,
                    )
                    continue
                return PluginHandledEventResult(
                    **prevent_result.result,
                    handled_by_plugin=True,
                    plugin=plugin,
                )
            except CancelledError:
                pass
            except BaseException:
                await logger.aexception(
                    f"Error happened when calling plugin {plugin!r}",
                )
        return None

    def __repr__(self) -> str:
        """Return the canonical string representation."""
        if not self.all_plugins:
            return "<pyfsd.plugin.manager.PluginManager (not initialized)>"
        return (
            "<pyfsd.plugin.manager.PluginManager "
            f"({len(self.all_plugins)}plugin(s))>"
        )

    def __str__(self) -> str:
        """Return all plugins' name."""
        if not self.all_plugins:
            return ""
        return ", ".join(plugin["name"] for plugin in self.all_plugins)

    def plugins_count(self) -> int:
        """Get count of plugins."""
        return len(self.all_plugins) if self.all_plugins else 0
