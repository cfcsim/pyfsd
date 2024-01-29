# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
"""Interfaces of PyFSD plugin architecture."""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Awaitable, ClassVar, Optional, Tuple, Type, TypedDict

if TYPE_CHECKING:
    from ..object.client import Client
    from ..protocol.client import FSDClientProtocol
    from ..service import PyFSDService
    from .types import PluginHandledEventResult, PyFSDHandledLineResult

__all__ = ["Plugin", "PyFSDPlugin", "CallAfterStartPlugin", "AwaitableMaker"]


class Plugin(ABC):
    """Base interface of plugin."""


class PyFSDPlugin(ABC):
    """Interface of PyFSD Plugin.

    Attributes:
        plugin_name: Name of this plugin.
        api: API level of this plugin.
        version: int and human readable version of this plugin.
        expected_config: Configuration structure description, TypedDict.
            structure parameter of pyfsd.define.check_dict function.
            None if this plugin requires no config. (disables config check)
    """

    plugin_name: ClassVar[str]
    api: ClassVar[int]
    version: ClassVar[Tuple[int, str]]
    expected_config: ClassVar[Optional[Type[TypedDict]]]  # type: ignore[valid-type]

    async def before_start(self, pyfsd: "PyFSDService", config: Optional[dict]) -> None:
        """Called before services start.

        Args:
            pyfsd: PyFSD Service.
            config: plugin.<plugin_name> section of PyFSD configure file.
                None if the section doesn't exist.
        """

    async def after_start(self, pyfsd: "PyFSDService", config: Optional[dict]) -> None:
        """Called while service `pyfsd.service.PyFSDService` starting.

        Args:
            pyfsd: PyFSD Service.
            config: plugin.<plugin_name> section of PyFSD configure file.
                None if the section doesn't exist.
        """

    async def before_stop(self) -> None:
        """Called when service `pyfsd.service.PyFSDService` stopping."""

    async def new_connection_established(self, protocol: "FSDClientProtocol") -> None:
        """Called when new connection established.

        Args:
            protocol: Protocol of the connection which established.
        """

    async def new_client_created(self, protocol: "FSDClientProtocol") -> None:
        """Called when new client `pyfsd.object.client.Client` created.

        Args:
            protocol: Protocol of the client which created.
        """

    async def line_received_from_client(
        self,
        protocol: "FSDClientProtocol",
        line: bytes,
    ) -> None:
        """Called when line received from client.

        Args:
            protocol: Protocol of the connection which received line.
            line: Line data.

        Raises:
            PreventEvent: Prevent the event.
        """

    async def audit_line_from_client(
        self,
        protocol: "FSDClientProtocol",
        line: bytes,
        result: "PyFSDHandledLineResult | PluginHandledEventResult",
    ) -> None:
        """Called when line received from client (after lineReceivedFromClient).
        Note that this event cannot be prevented.

        Args:
            protocol: Protocol of the connection which received line.
            line: Line data.
            result: The lineReceivedFromClient event result.

        """

    async def client_disconnected(
        self,
        protocol: "FSDClientProtocol",
        client: Optional["Client"],
    ) -> None:
        """Called when connection disconnected.

        Args:
            protocol: The protocol of the connection which disconnected.
            client: The client attribute of the protocol.
        """


class AwaitableMaker(ABC):
    """Interface of Awaitable maker, a object which can make a awaitable object.

    Should be used to load a blocking awaitable object.

    Attributes:
        awaitable_name: Name of the to-make awaitable object.
    """

    awaitable_name: ClassVar[str]

    @abstractmethod
    async def __call__(
        self,
        pyfsd: "PyFSDService",
        config: Optional[dict],
    ) -> Awaitable:
        """Make a awaitable object.

        Args:
            config: plugin.<awaitable_name> section of PyFSD configure file.
                None if the section doesn't exist.

        Returns:
            A awaitable object.
        """


class CallAfterStartPlugin(ABC):
    """Interface of call after start plugin.

    Syntactic sugar of PyFSDPlugin.afterStart
    """

    @abstractmethod
    async def __call__(self, pyfsd: "PyFSDService", all_config: dict) -> None:
        """Called while service `pyfsd.service.PyFSDService` starting.

        Args:
            pyfsd: PyFSD Service.
            all_config: PyFSD configure file.
        """
