# ruff: noqa: B027
"""Interfaces of PyFSD plugin architecture."""
from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Awaitable,
    ClassVar,
    Generator,
    Optional,
    Tuple,
    Type,
    TypedDict,
    Union,
)

if TYPE_CHECKING:
    from ..object.client import Client
    from ..protocol.client import ClientProtocol
    from .types import PluginHandledEventResult, PyFSDHandledLineResult

__all__ = ["Plugin", "PyFSDPlugin", "AwaitableMaker"]


class Plugin(ABC):  # noqa: B024
    """Base interface of plugin.

    Used to ensure a class is a plugin.
    """


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
    expected_config: ClassVar[Union[Type[TypedDict], dict, None]]  # type: ignore[valid-type]

    async def before_start(self) -> None:
        """Called before PyFSD start."""

    async def before_stop(self) -> None:
        """Called when PyFSD stopping."""

    async def new_connection_established(self, protocol: "ClientProtocol") -> None:
        """Called when new connection established.

        Args:
            protocol: Protocol of the connection which established.
        """

    async def new_client_created(self, protocol: "ClientProtocol") -> None:
        """Called when new client `pyfsd.object.client.Client` created.

        Args:
            protocol: Protocol of the client which created.
        """

    async def line_received_from_client(
        self,
        protocol: "ClientProtocol",
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
        protocol: "ClientProtocol",
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
        protocol: "ClientProtocol",
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
    def __call__(self) -> Generator[Awaitable, None, None]:
        """Make a awaitable object.

        Yields:
            First time yield the awaitable object, the next time do clean up.
            Examples::
                server = Server()
                server.prepare()
                yield server.run()
                server.clean()

        Returns:
            A awaitable object.
        """
