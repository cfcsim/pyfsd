# ruff: noqa: B027
"""Interfaces of PyFSD plugin architecture."""

from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Generator,
    Optional,
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


class PyFSDPlugin(ABC):  # noqa: B024
    """Interface of PyFSD Plugin."""

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

    Used to await a blocking awaitable object when PyFSD starts.
    """

    @abstractmethod
    def __call__(self) -> Generator[Optional[Awaitable], None, None]:
        """Make a awaitable object.

        Yields:
            First time yield the awaitable object, the next time do clean up.
            If nothing needs to be awaited, yield None first time. (code block after
                yield still executes.)
            Example::
                server = Server()
                server.prepare()
                yield server.run()
                server.clean()

        Returns:
            A awaitable object.
        """
