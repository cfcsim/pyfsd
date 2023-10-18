from inspect import getfile
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    TypedDict,
)

from twisted.internet.defer import succeed
from twisted.internet.threads import deferToThread
from twisted.logger import Logger
from twisted.plugin import getPlugins

from .. import plugins
from ..define.config_check import verifyAllConfigStruct
from ..define.utils import iterCallable
from . import API_LEVEL, BasePyFSDPlugin, PreventEvent
from .interfaces import IPyFSDPlugin, IServiceBuilder
from .types import PluginHandledEventResult

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred


__all__ = ["formatPlugin", "PLUGIN_EVENTS", "PluginDict", "PyFSDPluginManager"]

def formatPlugin(plugin: IPyFSDPlugin, with_version: bool = False) -> str:
    return (
        f"{plugin.plugin_name}"
        + (f" {plugin.version[1]} ({plugin.version[0]}) " if with_version else "")
        + f"({getfile(type(plugin))})"
    )


def formatService(plugin: IServiceBuilder) -> str:
    return f"{plugin.service_name} ({getfile(type(plugin))})"


PLUGIN_EVENTS = tuple(func.__name__ for func in iterCallable(BasePyFSDPlugin))


class PluginDict(TypedDict):
    all: Tuple[IPyFSDPlugin, ...]
    tagged: Dict[str, List[IPyFSDPlugin]]


class PyFSDPluginManager:
    plugins: Optional[PluginDict] = None
    logger = Logger()

    def pickPlugins(self, root_config: dict) -> None:
        all_plugins = []
        event_handlers: Dict[str, List[IPyFSDPlugin]] = dict(
            (name, []) for name in PLUGIN_EVENTS
        )
        for plugin in getPlugins(IPyFSDPlugin, plugins):
            # Tell user loading plugin
            self.logger.info(
                "Loading plugin {plugin}",
                plugin=formatPlugin(plugin, with_version=True),
            )
            if plugin in all_plugins:
                # Skip already loaded plugin
                self.logger.debug(
                    "plugin {plugin} already loaded, skipping.",
                    plugin=formatPlugin(plugin),
                )
            else:
                # Check API
                if not isinstance(plugin.api, int) or plugin.api > API_LEVEL:
                    self.logger.error(
                        "{plugin} needs API {api}, try update PyFSD",
                        api=plugin.api,
                        plugin=formatPlugin(plugin),
                    )
                else:
                    # Check API again.....
                    if plugin.api != API_LEVEL:
                        self.logger.error(
                            "{plugin} using outdated API {api}, may cause some problem",
                            api=plugin.api,
                            plugin=formatPlugin(plugin),
                        )

                    # Check config
                    plugin_config = root_config.get(plugin.plugin_name, None)
                    if plugin.expected_config is not None:
                        if plugin_config is None:
                            self.logger.error(
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
                                self.logger.error(error_string)
                                return

                    # Everything is ok, save it
                    all_plugins.append(plugin)
                    for event in PLUGIN_EVENTS:
                        if hasattr(plugin, event) and getattr(
                            type(plugin), event
                        ) is not getattr(BasePyFSDPlugin, event):
                            event_handlers[event].append(plugin)

        self.plugins = {"all": tuple(all_plugins), "tagged": event_handlers}

    def iterPluginByEventName(self, event_name: str) -> Iterable[IPyFSDPlugin]:
        assert self.plugins is not None, "plugin not loaded"
        if event_name not in PLUGIN_EVENTS:
            raise ValueError(f"Invaild event {event_name}")
        return iter(self.plugins["tagged"][event_name])

    def iterHandlerByEventName(self, event_name: str) -> Iterable[Callable]:
        return (
            getattr(plugin, event_name)
            for plugin in self.iterPluginByEventName(event_name)
        )

    def triggerEvent(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
        prevent_able: bool = False,
    ) -> "PluginHandledEventResult | None":
        for plugin in self.iterPluginByEventName(event_name):
            try:
                getattr(plugin, event_name)(*args, **kwargs)
            except PreventEvent as prevent_result:
                if not prevent_able:
                    Logger(source=plugin).error(f"Cannot prevent event: {event_name}")
                else:
                    return {  # type: ignore[return-value]
                        **prevent_result.result,  # type: ignore[misc]
                        "handled_by_plugin": True,
                        "plugin": plugin,
                    }
            except BaseException:
                Logger(source=plugin).failure("Error happened during call plugin")
        return None

    def deferEvent(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
        prevent_able: bool = False,
        in_thread: bool = False,
    ) -> "Deferred[PluginHandledEventResult | None]":
        if in_thread:
            return deferToThread(  # type: ignore[no-any-return]
                self.triggerEvent, event_name, args, kwargs, prevent_able
            )
        else:
            return succeed(self.triggerEvent(event_name, args, kwargs, prevent_able))
