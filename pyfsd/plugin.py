# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
from typing import TYPE_CHECKING

from zope.interface import Attribute, Interface, implementer

if TYPE_CHECKING:
    from .object.client import Client
    from .protocol.client import FSDClientProtocol
    from .service import PyFSDService


class IPyFSDPlugin(Interface):
    plugin_name = Attribute("plugin_name")
    api = Attribute("API Level")

    def beforeStart(pyfsd: "PyFSDService") -> None:
        ...

    def beforeStop() -> None:
        ...

    def newConnectionEstablished(protocol: "FSDClientProtocol") -> None:
        ...

    def newClientCreated(protocol: "FSDClientProtocol") -> None:
        ...

    def lineReceivedFromClient(protocol: "FSDClientProtocol", byte_line: bytes) -> None:
        ...

    def clientDisconnected(protocol: "FSDClientProtocol", client: "Client") -> bool:
        ...


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
        self, protocol: "FSDClientProtocol", byte_line: bytes
    ) -> None:
        ...

    def clientDisconnected(  # type: ignore[empty-body]
        self, protocol: "FSDClientProtocol", client: "Client"
    ) -> bool:
        ...


class PreventEvent(Exception):
    pass
