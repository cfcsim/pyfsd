# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
from typing import TYPE_CHECKING, Optional

from zope.interface import Attribute, Interface, implementer

if TYPE_CHECKING:
    from .object.client import Client
    from .protocol.client import FSDClientProtocol
    from .service import PyFSDService


class PreventEvent(BaseException):
    """Prevent a PyFSD plugin event."""


class IPyFSDPlugin(Interface):
    """Interface of PyFSD Plugin.

    Attributes:
        plugin_name: Name of this plugin.
        api: API level of this plugin.
    """

    plugin_name: str = Attribute("plugin_name", "Name of this plugin.")
    api: int = Attribute("API Level", "API level of this plugin.")

    def beforeStart(pyfsd: "PyFSDService", config: Optional[dict]) -> None:
        """Called when service `pyfsd.service.PyFSDService` starting.

        Args:
            pyfsd: PyFSD Service.
            config: plugin.<plugin_name> section of PyFSD configure file.
                None if the section doesn't exist.
        """

    def beforeStop() -> None:
        """Called when service `pyfsd.service.PyFSDService` stopping."""

    def newConnectionEstablished(protocol: "FSDClientProtocol") -> None:
        """Called when new connection established.

        Args:
            protocol: Protocol of the connection which established.
        """

    def newClientCreated(protocol: "FSDClientProtocol") -> None:
        """Called when new client `pyfsd.object.client.Client` created.

        Args:
            protocol: Protocol of the client which created.
        """

    def lineReceivedFromClient(protocol: "FSDClientProtocol", line: bytes) -> None:
        """Called when line received from client.

        Args:
            protocol: Protocol of the connection which received line.
            line: Line data.

        Raises:
            PreventEvent: Prevent the event.
        """

    def clientDisconnected(
        protocol: "FSDClientProtocol", client: Optional["Client"]
    ) -> bool:
        """Called when connection disconnected.

        Args:
            protocol: The protocol of the connection which disconnected.
            client: The client attribute of the protocol.
        """


@implementer(IPyFSDPlugin)
class BasePyFSDPlugin:
    plugin_name = "<plugin name missing>"
    api = 1

    def beforeStart(self, pyfsd: "PyFSDService", config: Optional[dict]) -> None:
        ...

    def beforeStop(self) -> None:
        ...

    def newConnectionEstablished(  # type: ignore[empty-body]
        self, protocol: "FSDClientProtocol"
    ) -> None:
        ...

    def newClientCreated(  # type: ignore[empty-body]
        self, protocol: "FSDClientProtocol"
    ) -> None:
        ...

    def lineReceivedFromClient(
        self, protocol: "FSDClientProtocol", line: bytes
    ) -> None:
        ...

    def clientDisconnected(  # type: ignore[empty-body]
        self, protocol: "FSDClientProtocol", client: Optional["Client"]
    ) -> bool:
        ...
