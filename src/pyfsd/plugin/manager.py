"""PyFSD plugin manager.

Attributes:
    PLUGIN_EVENTS: All available PyFSD plugin events.
"""

from inspect import getfile
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Tuple, TypedDict

from loguru import logger

from .. import plugins
from ..define.config_check import verifyAllConfigStruct
from ..define.utils import iterCallable
from . import API_LEVEL, PreventEvent
from .collect import iter_submodule_plugins
from .interfaces import AwaitableMaker, PyFSDPlugin
from .types import PluginHandledEventResult

__all__ = ["format_plugin", "PLUGIN_EVENTS", "PluginDict", "PyFSDPluginManager"]


def format_plugin(plugin: PyFSDPlugin, with_version: bool = False) -> str:
    """Format a plugin into string.

    Args:
        plugin: The plugin.
        with_version: Append version to string or not.

    Returns:
        The formatted result.
    """
    return (
        f"{plugin.plugin_name}"
        + (f" {plugin.version[1]} ({plugin.version[0]}) " if with_version else "")
        + f"({getfile(type(plugin))})"
    )


def format_awaitable(plugin: AwaitableMaker) -> str:
    """Format a awaitable maker into string.

    Args:
        plugin: The maker.

    Returns:
        The formatted result.
    """
    return f"{plugin.awaitable_name} ({getfile(type(plugin))})"


PLUGIN_EVENTS = tuple(func.__name__ for func in iterCallable(PyFSDPlugin))


class PluginDict(TypedDict):
    """Plugin set used by PyFSDPluginManager.

    Attributes:
        all: All plugins.
        tagged: Plugins tagged by events.
    """

    all: Tuple[PyFSDPlugin, ...]
    tagged: Dict[str, List[PyFSDPlugin]]


class PyFSDPluginManager:
    """PyFSD Plugin manager.

    Attributes:
        plugins: Plugin set.
    """

    plugins: Optional[PluginDict] = None

    def pick_plugins(self, root_config: dict) -> None:
        """Pick plugins into self.plugins.

        Args:
            root_config: 'plugin' section of config.
        """
        all_plugins = []
        event_handlers: Dict[str, List[PyFSDPlugin]] = {
            name: [] for name in PLUGIN_EVENTS
        }
        for plugin in iter_submodule_plugins(
            plugins,
            PyFSDPlugin,  # type: ignore[type-abstract]
            error_handler=lambda name: logger.exception(
                f"Error happened during load plugin {name}",
            ),
        ):
            # Tell user loading plugin
            logger.info(
                "Loading plugin {plugin}",
                plugin=format_plugin(plugin, with_version=True),
            )
            if plugin in all_plugins:
                # Skip already loaded plugin
                logger.debug(
                    "plugin {plugin} already loaded, skipping.",
                    plugin=format_plugin(plugin),
                )
            else:
                # Check API
                if not isinstance(plugin.api, int) or plugin.api > API_LEVEL:
                    logger.error(
                        "{plugin} needs API {api}, try update PyFSD",
                        api=plugin.api,
                        plugin=format_plugin(plugin),
                    )
                else:
                    # Check API again.....
                    if plugin.api != API_LEVEL:
                        logger.error(
                            "{plugin} using outdated API {api}, may cause some problem",
                            api=plugin.api,
                            plugin=format_plugin(plugin),
                        )

                    # Check config
                    plugin_config = root_config.get(plugin.plugin_name, None)
                    if plugin.expected_config is not None:
                        if plugin_config is None:
                            logger.error(
                                "Cannot load plugin {name} because it needs config.",
                                name=plugin.plugin_name,
                            )
                            return
                        else:
                            config_errors = verifyAllConfigStruct(
                                plugin_config,
                                plugin.expected_config,
                                prefix=f"plugin.{plugin.plugin_name}.",
                            )
                            if config_errors:
                                error_string = (
                                    f"Cannot load plugin {plugin.plugin_name} "
                                    "because of following config error:\n"
                                )
                                for config_error in config_errors:
                                    error_string += str(config_error) + "\n"
                                logger.error(error_string)
                                return

                    # Everything is ok, save it
                    all_plugins.append(plugin)
                    for event in PLUGIN_EVENTS:
                        if hasattr(plugin, event) and getattr(
                            type(plugin),
                            event,
                        ) is not getattr(PyFSDPlugin, event):
                            event_handlers[event].append(plugin)

        self.plugins = {"all": tuple(all_plugins), "tagged": event_handlers}

    def iterPluginByEventName(self, event_name: str) -> Iterable[PyFSDPlugin]:
        """Yields all plugins that handles specified event.

        Args:
            event_name: The event's name. Must be in PLUGIN_EVENTS

        Returns:
            The plugin.
        """
        assert self.plugins is not None, "plugin not loaded"
        if event_name not in PLUGIN_EVENTS:
            msg = f"Invaild event {event_name}"
            raise ValueError(msg)
        return iter(self.plugins["tagged"][event_name])

    def iterHandlerByEventName(self, event_name: str) -> Iterable[Callable]:
        """Yields event handler of all plugins that handles specified event.

        Args:
            event_name: The event's name. Must be in PLUGIN_EVENTS

        Returns:
            The event handler, {plugin}.{event_name}
        """
        return (
            getattr(plugin, event_name)
            for plugin in self.iterPluginByEventName(event_name)
        )

    async def triggerEvent(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
        prevent_able: bool = False,
    ) -> "PluginHandledEventResult | None":
        """Trigger a event and spread it to plugins."""
        for plugin in self.iterPluginByEventName(event_name):
            try:
                await getattr(plugin, event_name)(*args, **kwargs)
            except PreventEvent as prevent_result:
                if not prevent_able:
                    logger.error(
                        f"{plugin.plugin_name}: Cannot prevent event: {event_name}",
                    )
                else:
                    return {  # type: ignore[return-value]
                        **prevent_result.result,  # type: ignore[misc]
                        "handled_by_plugin": True,
                        "plugin": plugin,
                    }
            except BaseException:
                logger.exception(
                    f"Error happened during call plugin {plugin.plugin_name}",
                )
        return None
