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
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
)

from structlog import get_logger

from .. import plugins
from ..define.check_dict import check_dict
from ..define.utils import iter_callable
from . import API_LEVEL, PreventEvent
from .collect import iter_submodule_plugins
from .interfaces import AwaitableMaker, Plugin, PyFSDPlugin
from .types import PluginHandledEventResult

_T_ABC = TypeVar("_T_ABC", bound=ABC)

logger = get_logger(__name__)
__all__ = ["format_plugin", "PLUGIN_EVENTS", "PluginDict", "PluginManager"]


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


def format_plugin(plugin: PyFSDPlugin, with_version: bool = False) -> str:
    """Format a PyFSD plugin into string.

    Args:
        plugin: The plugin.
        with_version: Append version to string or not.

    Returns:
        The formatted result.
    """
    path = getfile(type(plugin))
    if path.startswith(_cwd):
        path = path[len(_cwd) + 1 :]
    return (
        f"{plugin.plugin_name}"
        + (f" {plugin.version[1]} ({plugin.version[0]}) " if with_version else "")
        + f"({path})"
    )


def format_awaitable(plugin: AwaitableMaker) -> str:
    """Format a awaitable maker into string.

    Args:
        plugin: The maker.

    Returns:
        The formatted result.
    """
    path = getfile(type(plugin))
    if path.startswith(_cwd):
        path = path[len(_cwd) + 1 :]
    return f"{plugin.awaitable_name} ({path})"


PLUGIN_EVENTS = tuple(func.__name__ for func in iter_callable(PyFSDPlugin))


class Plugins(Dict):
    """A dict stores all plugins.

    plugins_dict[ABC] => List[Plugins implemented ABC]
    """

    def __getitem__(self, __key: Type[_T_ABC]) -> List[_T_ABC]:
        return super().__getitem__(__key)  # type: ignore[no-any-return]

    def __setitem__(self, __key: Type[_T_ABC], __value: List[_T_ABC]) -> None:
        return super().__setitem__(__key, __value)


class PluginDict(TypedDict):
    """A dict stores all PyFSDPlugin.

    Attributes:
        all: All plugins.
        tagged: Plugins tagged by events.
    """

    all: Tuple[PyFSDPlugin, ...]
    tagged: Dict[str, List[PyFSDPlugin]]


class PluginManager:
    """PyFSD Plugin manager.

    Attributes:
        plugins: Taged collected plugins.
        pyfsd_plugins: Collected PyFSDPlugins.
    """

    plugins: Optional[Plugins] = None
    pyfsd_plugins: Optional[PluginDict] = None

    def pick_plugins(self) -> None:
        """Pick all plugins into self.pyfsd_plugins."""
        plugins_dict: Plugins = Plugins()
        for plugin in iter_submodule_plugins(plugins, Plugin, deal_exception):
            plugin_class = type(plugin)
            for cls in getmro(plugin_class):
                if issubclass(cls, ABC) and cls not in (plugin_class, Plugin, ABC):
                    if cls not in plugins_dict:
                        plugins_dict[cls] = []
                    plugins_dict[cls].append(plugin)
        self.plugins = plugins_dict

    def get_plugins(self, plugin_abc: Type[_T_ABC]) -> List[_T_ABC]:
        """Get list of plugins that implemented specified ABC."""
        if self.plugins is None:
            raise RuntimeError("Plugins not picked")
        if plugin_abc not in self.plugins:
            return []
        return self.plugins[plugin_abc]

    def load_pyfsd_plugins(self, plugin_config_root: dict) -> None:
        """Pick PyFSD plugins into self.pyfsd_plugins.

        Args:
            plugin_config_root: 'plugin' section of config.
        """
        all_plugins = []
        event_handlers: Dict[str, List[PyFSDPlugin]] = {
            name: [] for name in PLUGIN_EVENTS
        }
        for plugin in self.get_plugins(PyFSDPlugin):
            # Tell user loading plugin
            logger.info(
                "Loading plugin %s",
                format_plugin(plugin, with_version=True),
            )
            if plugin in all_plugins:
                # Skip already loaded plugin
                logger.debug(
                    "plugin %s already loaded, skipping.",
                    format_plugin(plugin),
                )
            else:
                # Check API
                if not isinstance(plugin.api, int) or plugin.api > API_LEVEL:
                    logger.error(
                        "%s needs API %d, try update PyFSD",
                        format_plugin(plugin),
                        plugin.api,
                    )
                else:
                    # Check API again.....
                    if plugin.api != API_LEVEL:
                        logger.warning(
                            "%s using outdated API %d, may cause some problem",
                            plugin=format_plugin(plugin),
                            api=plugin.api,
                        )

                    # Check config
                    plugin_config = plugin_config_root.get(plugin.plugin_name, None)
                    if plugin.expected_config is not None:
                        if plugin_config is None:
                            logger.error(
                                "Cannot load plugin %s because it needs config.",
                                plugin.plugin_name,
                            )
                            continue
                        config_errors = tuple(
                            check_dict(
                                plugin_config,
                                plugin.expected_config,
                                name=f"plugin[{plugin.plugin_name!r}]",
                                allow_unexpected_key=True,
                            )
                        )
                        if config_errors:
                            error_string = (
                                f"Cannot load plugin {plugin.plugin_name} "
                                "because of following config error:\n"
                            )
                            for config_error in config_errors:
                                error_string += str(config_error) + "\n"
                            logger.error(error_string.rstrip("\n"))
                            continue

                    # Everything is ok, save it
                    all_plugins.append(plugin)
                    for event in PLUGIN_EVENTS:
                        if hasattr(plugin, event) and getattr(
                            type(plugin),
                            event,
                        ) is not getattr(PyFSDPlugin, event):
                            event_handlers[event].append(plugin)

        self.pyfsd_plugins = {"all": tuple(all_plugins), "tagged": event_handlers}

    def iter_plugin_by_event_name(self, event_name: str) -> Iterable[PyFSDPlugin]:
        """Yields all plugins that handles specified event.

        Args:
            event_name: The event's name. Must be in PLUGIN_EVENTS

        Returns:
            The plugin.
        """
        if self.pyfsd_plugins is None:
            raise RuntimeError("PyFSD plugins not loaded")
        if event_name not in PLUGIN_EVENTS:
            msg = f"Invaild event {event_name}"
            raise ValueError(msg)
        yield from self.pyfsd_plugins["tagged"][event_name]

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
                        f"{plugin.plugin_name}: Cannot prevent event: {event_name}",
                    )
                else:
                    return {
                        **prevent_result.result,
                        "handled_by_plugin": True,
                        "plugin": plugin,
                    }
            except CancelledError:
                pass
            except BaseException:
                await logger.aexception(
                    f"Error happened during call plugin {plugin.plugin_name}",
                )
        return None
