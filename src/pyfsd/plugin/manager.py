"""PyFSD plugin manager.

Tip: how the plugin architecture works:
    Assume your plugin registered a handler and an auditer:

        async def setup():
            return {
                "handler": {"some_event": (self.handle_sth,)},
                "auditer": {"some_event": (self.audit_sth,)},
            }

    If this event is handleable, then somewhere of PyFSD will call

        PluginManager.trigger_event_handlers("some_event", ...)

    So handler in your plugin got called:

        def handle_sth(...) -> None: pass

    If the handler prevented the event by `raise PreventEvent`, then this event won't be
        passed to other plugins and PyFSD won't handle the event too.

    Later after this event processed (handled by PyFSD or prevented by one plugin),
        PyFSD'll call `PluginManager.trigger_event_auditers("some_event", ...)`, so
        auditer in your plugin got called:

        def audit_sth(..) -> None: pass
"""

from asyncio import CancelledError, create_task, gather
from collections.abc import Awaitable, Iterable, Mapping
from inspect import getfile
from os import getcwd
from random import choices
from string import ascii_letters
from sys import exc_info
from typing import (
    TYPE_CHECKING,
    Callable,
    Optional,
    TypedDict,
    TypeVar,
)

from structlog import get_logger

from pyfsd import plugins
from pyfsd.define.check_dict import check_dict
from pyfsd.define.utils import mustdone_task_keeper

from . import (
    API_LEVEL,
    EventListenersDict,
    Plugin,
    PluginHandledEventResult,
    PreventEvent,
)
from .collect import iter_submodules

if TYPE_CHECKING:
    from asyncio import _CoroutineLike

logger = get_logger(__name__)
__all__ = [
    "PluginManager",
    "SortedPlugins",
]
C = TypeVar("C", bound="_CoroutineLike")


def deal_exception(name: str) -> None:
    """Handle exceptions when importing plugins."""
    type_, exception, traceback = exc_info()

    if exception is not None and type_ in (
        KeyboardInterrupt,
        CancelledError,
    ):
        raise exception.with_traceback(traceback)

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
        "Error happened during load plugin %s",
        name,
        exc_info=(type_, exception, traceback),
    )


# ruff: noqa: PTH109
_cwd = getcwd()


def brief_path(path: str) -> str:
    """Shorten filepath to relative one if it's under current working directory."""
    if path.startswith(_cwd):
        return path[len(_cwd) + 1 :]
    return path


class SortedPlugins(TypedDict):
    """A dict that stores PyFSD plugins that can handle specified events.

    Attributes:
        auditers: { "event name": ((<plugin>, <auditer from the plugin>), ...), ... }
        handlers: { "event name": ((<plugin>, <handler from the plugin>), ...), ... }
    """

    auditers: dict[str, tuple[tuple[Plugin, Callable[..., Awaitable]], ...]]
    handlers: dict[str, tuple[tuple[Plugin, Callable[..., Awaitable]], ...]]


class PluginManager:
    """PyFSD Plugin manager.

    Attributes:
        all_plugins: All collected plugin files.
        sorted_plugins: Plugins sorted with event name which it audits or handles.
        awaitable_services: Registered awaitable services.
    """

    all_plugins: Optional[tuple[Plugin, ...]] = None
    sorted_plugins: Optional[SortedPlugins] = None

    # ruff: noqa: C901, PLR0912, PLR0915, BLE001
    async def pick_plugins(self, plugin_config_root: dict) -> None:
        """Pick all plugins into self.all_plugins & self.sorted_plugins."""

        def setattr1(obj: object, name: str, val: object) -> None:
            """Set attribute forcefully."""
            object.__setattr__(obj, name, val)

        used_name = []
        all_plugins: list[Plugin] = []
        plugins_handlers: dict[Plugin, EventListenersDict] = {}

        for module in iter_submodules(
            plugins.__path__, plugins.__name__, deal_exception
        ):
            plugin = getattr(module, "pyfsd_plugin", None)
            path = brief_path(getfile(module))
            if not isinstance(plugin, Plugin):
                await logger.awarning(f"Invalid plugin: {path}")
                continue

            default_name = getfile(module).split("/")[-1][:-3]
            if not hasattr(plugin, "name"):
                setattr1(plugin, "name", default_name)
            if not hasattr(plugin, "api"):
                setattr1(plugin, "api", (-1, 0))
            if not hasattr(plugin, "version"):
                setattr1(plugin, "version", (0, "unknown"))
            if not hasattr(plugin, "expected_config"):
                setattr1(plugin, "expected_config", None)

            # ruff: noqa: PLR2004
            if (
                (not (plugin_name_ok := isinstance(plugin.name, str)))
                or (not isinstance(plugin.api, tuple))
                or (not isinstance(plugin.version, tuple))
                or (len(plugin.api) != 2)
                or (len(plugin.version) != 2)
                or (not isinstance(plugin.api[0], int))
                or (not isinstance(plugin.api[1], int))
                or (not isinstance(plugin.version[0], int))
                or (not isinstance(plugin.version[1], str))
                or (
                    plugin.expected_config is not None
                    and not isinstance(plugin.expected_config, dict)
                )
                or (not callable(getattr(plugin, "setup", None)))
            ):
                await logger.aerror(
                    "Cannot load plugin "
                    + (plugin.name if plugin_name_ok else default_name)
                    + ": malformed plugin",
                )
                continue

            # Check API
            # We expect <major> is the same as API_LEVEL's major
            # and <minor> <= API_LEVEL's minor
            if plugin.api[0] != API_LEVEL[0] or plugin.api[1] > API_LEVEL[1]:
                await logger.aerror(
                    f"Cannot load plugin {plugin.name}: needs API {plugin.api}"
                )
                continue

            # Check config
            if plugin.expected_config is not None:
                plugin_config = plugin_config_root.get(plugin.name)
                if plugin_config is None:
                    await logger.aerror(
                        f"Cannot load plugin {plugin.name}: config required"
                    )
                    continue
                config_errors = tuple(
                    check_dict(
                        plugin_config,
                        plugin.expected_config,
                        name=f"plugin[{plugin.name!r}]",
                        allow_extra_keys=True,
                    )
                )
                if config_errors:
                    await logger.aerror(
                        f"Cannot load plugin {plugin.name}: invalid config",
                        stack="\n".join(f"  {err!s}" for err in config_errors),
                    )
                    continue

            # Check duplicated
            if plugin in all_plugins:
                await logger.awarning(f"Duplicated plugin {plugin.name}, skip loading")
                continue

            if plugin.name in used_name:
                new_name = plugin.name
                while new_name in used_name:
                    # ruff: noqa: S311
                    new_name = f"{plugin.name}_{''.join(choices(ascii_letters, k=5))}"
                await logger.awarning(
                    f"Replacing duplicated plugin name {plugin.name} with {new_name}"
                )
                setattr1(plugin, "name", new_name)

            # Nothing wrong, load it
            used_name.append(plugin.name)
            await logger.adebug(f"Loading plugin {plugin!r}")
            try:
                if handlers := await plugin.setup():
                    plugins_handlers[plugin] = handlers
            except (KeyboardInterrupt, CancelledError):
                raise
            except BaseException:
                await logger.aexception(
                    f"Error happened when loading plugin {plugin.name}",
                )
            all_plugins.append(plugin)

        self.all_plugins = tuple(all_plugins)
        self.sort_pyfsd_plugins(plugins_handlers)

    def sort_pyfsd_plugins(
        self, plugins_handlers: dict[Plugin, EventListenersDict]
    ) -> None:
        """Sort PyFSD plugins into self.pyfsd_plugins.

        Args:
            plugins_handlers: {"plugin_name": <EventListenersDict>, ...}
        """
        all_auditers: dict[str, list[tuple[Plugin, Callable[..., Awaitable]]]] = {}
        all_handlers: dict[str, list[tuple[Plugin, Callable[..., Awaitable]]]] = {}

        for plugin, listeners in plugins_handlers.items():
            for event_name, plugin_auditers in listeners["auditers"].items():
                if event_name not in all_auditers:
                    all_auditers[event_name] = []
                all_auditers[event_name].extend(
                    (plugin, auditer) for auditer in plugin_auditers
                )
            for event_name, plugin_handlers in listeners["handlers"].items():
                if event_name not in all_handlers:
                    all_handlers[event_name] = []
                all_handlers[event_name].extend(
                    (plugin, handler) for handler in plugin_handlers
                )

        self.sorted_plugins = {
            "auditers": {
                name: tuple(auditer_infos)
                for name, auditer_infos in all_auditers.items()
            },
            "handlers": {
                name: tuple(handler_infos)
                for name, handler_infos in all_handlers.items()
            },
        }

    async def trigger_event_handlers(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
    ) -> "PluginHandledEventResult | None":
        """Trigger a handle event and call handlers from plugins."""
        if self.sorted_plugins is None:
            raise RuntimeError("plugins not sorted")
        for plugin, handler in self.sorted_plugins["handlers"].get(event_name, ()):
            try:
                await handler(*args, **kwargs)
            # ruff: noqa: PERF203
            except PreventEvent as prevent_result:
                return PluginHandledEventResult(
                    **prevent_result.result,
                    handled_by_plugin=True,
                    plugin=plugin,
                )
            except (KeyboardInterrupt, CancelledError):
                raise
            except BaseException:
                await logger.aexception(
                    f"Error happened when calling plugin {plugin.name}",
                )
        return None

    async def trigger_event_auditers(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
    ) -> None:
        """Trigger a audit event and call auditers from plugins."""
        if self.sorted_plugins is None:
            raise RuntimeError("plugins not sorted")

        async def auditer_runner(auditer: Callable[..., Awaitable], name: str) -> None:
            try:
                await auditer(*args, **kwargs)
            except (KeyboardInterrupt, CancelledError):
                raise
            except BaseException:
                await logger.aexception(f"Error happened when calling plugin {name}")

        # run auditers together since we don't expect response from them
        await gather(
            *(
                auditer_runner(auditer, plugin.name)
                for plugin, auditer in self.sorted_plugins["auditers"].get(
                    event_name, ()
                )
            )
        )

    def trigger_event_auditers_nonblock(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
    ) -> None:
        """Trigger a audit event and call auditers from plugins, not blocking."""
        mustdone_task_keeper.add(
            create_task(self.trigger_event_auditers(event_name, args, kwargs))
        )

    def __repr__(self) -> str:
        """Return the canonical string representation."""
        if not self.all_plugins:
            return "<pyfsd.plugin.manager.PluginManager (not initialized)>"
        return (
            f"<pyfsd.plugin.manager.PluginManager ({len(self.all_plugins)}plugin(s))>"
        )

    def __str__(self) -> str:
        """Return all plugins' name."""
        if not self.all_plugins:
            return ""
        return ", ".join(plugin.name for plugin in self.all_plugins)

    def plugins_count(self) -> int:
        """Get count of plugins."""
        return len(self.all_plugins) if self.all_plugins else 0
