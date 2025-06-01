# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
"""PyFSD plugin architecture.

Attributes:
    API_LEVEL (tuple[int, int]): Current PyFSD plugin api level, (major, minor).
        If changes will break something, major is increased, otherwise minor.
    EventResult: event handle result for handleable events.
"""

from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import (
    Callable,
    Literal,
    Optional,
    TypedDict,
    TypeVar,
    Union,
)

__all__ = [
    "API_LEVEL",
    "EventListenersDict",
    "EventResult",
    "Plugin",
    "PluginHandledEventResult",
    "PreventEvent",
    "PyFSDHandledEventResult",
    "SimplePlugin",
    "StubPlugin",
]


C = TypeVar("C", bound=Callable[..., Awaitable])

API_LEVEL = (5, 0)
EventResult = Union["PluginHandledEventResult", "PyFSDHandledEventResult"]


class PreventEvent(BaseException):
    """Prevent a PyFSD plugin event.

    Attributes:
        result: The event result reported by plugin.
    """

    result: dict

    def __init__(self, result: Optional[dict] = None) -> None:
        """Create a PreventEvent instance."""
        if result is None:
            result = {}
        self.result = result


class EventListenersDict(TypedDict):
    """Dict that stores event listeners (handlers & auditers)."""

    handlers: dict[str, list[Callable[..., Awaitable]]]
    auditers: dict[str, list[Callable[..., Awaitable]]]


class Plugin:
    """Base class of a PyFSD plugin.

    Attributes:
        name: Name of this plugin.
        api: API level of this plugin. See `pyfsd.plugin.API_LEVEL`
        version: int and human readable version of this plugin.
        expected_config: Configuration structure description, in dict or TypedDict,
            which is structure parameter of pyfsd.define.check_dict function.
            use None to disable config check.
    """

    name: str
    api: tuple[int, int]
    version: tuple[int, str]
    expected_config: Union[type[TypedDict], dict, None]  # type: ignore[valid-type]

    def __hash__(self) -> int:
        """Return hash of this plugin."""
        # self.name is ensured to be unique by PluginManager
        return hash(self.name)

    def __eq__(self, value: object, /) -> bool:
        """Check if this plugin equals to another one."""
        if value is self:
            return True
        if isinstance(value, Plugin):
            return (
                self.name == value.name
                and self.api == value.api
                and self.version == value.version
            )
        return NotImplemented

    def __repr__(self) -> str:
        """Return the canonical string representation of this plugin."""
        return f"<PyFSDPlugin {self.name} v{self.version[1]} ({self.version[0]})>"

    async def setup(self) -> Optional[EventListenersDict]:
        """Setup this plugin.

        Returns:
            A dict that stores event listeners. See `pyfsd.plugin.EventListenersDict`
                None if this plugin does not register event listeners.
        """


@dataclass(frozen=True, eq=False, repr=False)
class StubPlugin(Plugin):
    """Stub plugin that does nothing."""

    # TODO: Currently we have to copy these attributes until python 3.10
    # see github issue microsoft/vscode-python#20378
    name: str
    api: tuple[int, int]
    version: tuple[int, str]
    expected_config: Union[type[TypedDict], dict, None]  # type: ignore[valid-type]


@dataclass(frozen=True, eq=False, repr=False)
class SimplePlugin(Plugin):
    """Create a simple plugin by decorators.

    Attributes:
        listeners: Event listeners.
    """

    # TODO: see `pyfsd.plugin.StubPlugin`
    name: str
    api: tuple[int, int]
    version: tuple[int, str]
    expected_config: Union[type[TypedDict], dict, None]  # type: ignore[valid-type]
    listeners: EventListenersDict = field(  # type: ignore[assignment]
        default_factory=lambda: {"auditers": {}, "handlers": {}}
    )

    async def setup(self) -> EventListenersDict:
        """Return listeners registered by self.handle() and self.audit() before."""
        if callable(pre_setup := getattr(self, "__pre_setup", None)):
            await pre_setup()
        return self.listeners

    def handle(self, event: str) -> Callable[[C], C]:
        """Add a event handler for specified event."""
        if event not in self.listeners["handlers"]:
            self.listeners["handlers"][event] = []

        def decorator(handler: C) -> C:
            self.listeners["handlers"][event].append(handler)
            return handler

        return decorator

    def audit(self, event: str) -> Callable[[C], C]:
        """Add a event auditer for specified event."""
        if event not in self.listeners["auditers"]:
            self.listeners["auditers"][event] = []

        def decorator(auditer: C) -> C:
            self.listeners["auditers"][event].append(auditer)
            return auditer

        return decorator

    def setuper(self, setuper: C) -> C:
        """Set setuper."""
        if callable(getattr(self, "__pre_setup", None)):
            raise TypeError("setuper already exist")
        object.__setattr__(self, "__pre_setup", setuper)
        return setuper


class PluginHandledEventResult(TypedDict):
    """A result handled by plugin.

    This means a plugin raised `pyfsd.plugin.PreventEvent`.

    Attributes:
        handled_by_plugin: Event handled by plugin or not.
        plugin_name: Name of the plugin.
    """

    handled_by_plugin: Literal[True]
    plugin: Plugin


class PyFSDHandledEventResult(TypedDict):
    """A result handled by PyFSD.

    Attributes:
        handled_by_plugin: Event handled by plugin or not.
        success: The event successfully handled or not.
    """

    handled_by_plugin: Literal[False]
    success: bool
