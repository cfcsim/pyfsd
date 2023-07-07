# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
from typing import TYPE_CHECKING, Optional

from zope.interface import Attribute, Interface, implementer

if TYPE_CHECKING:
    from .object.client import Client
    from .protocol.client import FSDClientProtocol
    from .service import PyFSDService


class IPyFSDPlugin(Interface):
    plugin_name: str = Attribute("plugin_name", "Name of this plugin.")
    api: int = Attribute("API Level", "API level of this plugin.")

    def beforeStart(pyfsd: "PyFSDService") -> None:
        """Called when service :class:`pyfsd.service.PyFSDService` starting.

        :param pyfsd: PyFSD Service.
        :type pyfsd: class:`pyfsd.service.PyFSDService`
        :return: None
        :rtype: None
        """

    def beforeStop() -> None:
        """Called when service :class:`pyfsd.service.PyFSDService` stopping.

        :return: None
        :rtype: None
        """

    def newConnectionEstablished(protocol: "FSDClientProtocol") -> None:
        """Called when new connection established.

        :param protocol: Protocol of the connection which established.
        :type protocol: class:`pyfsd.protocol.client.FSDClientProtocol`
        :return: None
        :rtype: None
        """

    def newClientCreated(protocol: "FSDClientProtocol") -> None:
        """Called when new client :class:`pyfsd.object.client.Client` created.

        :param protocol: Protocol of the client which created.
        :type protocol: class:`pyfsd.protocol.client.FSDClientProtocol`
        :return: None
        :rtype: None
        """

    def lineReceivedFromClient(protocol: "FSDClientProtocol", line: bytes) -> None:
        """Called when line received from client.

        :param protocol: Protocol of the connection which received line.
        :type protocol: class:`pyfsd.protocol.client.FSDClientProtocol`
        :param line: Line data.
        :type line: bytes
        :return: None
        :rtype: None
        :raises class:`pyfsd.plugin.PreventEvent`: Stop the event.
        """

    def clientDisconnected(protocol: "FSDClientProtocol", client: Optional["Client"]) -> bool:
        """Called when connection disconnected.

        :param protocol: The protocol of the connection which disconnected.
        :type protocol: class:`pyfsd.protocol.client.FSDClientProtocol`
        :param client: The client attribute of the protocol.
        :type client: class:`pyfsd.object.client.Client`, optional
        :return: None
        :rtype: None
        """


@implementer(IPyFSDPlugin)
class BasePyFSDPlugin:
    plugin_name = "<plugin name missing>"
    api = 1

    def beforeStart(self, pyfsd: "PyFSDService") -> None:
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


class PreventEvent(Exception):
    pass
