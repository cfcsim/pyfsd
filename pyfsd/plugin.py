from typing import TYPE_CHECKING

from zope.interface import Attribute, Interface, implementer

if TYPE_CHECKING:
    from .object.client import Client
    from .protocol.client import FSDClientProtocol
    from .service import PyFSDService


class IPyFSDPlugin(Interface):  # type: ignore[misc, valid-type]
    plugin_name = Attribute("plugin_name")

    def beforeStart(pyfsd: "PyFSDService") -> None:  # type: ignore[empty-body]
        ...

    def beforeStop() -> None:  # type: ignore[empty-body, misc]
        ...

    def newConnectionEstablished(
        protocol: "FSDClientProtocol",  # type: ignore
    ) -> None:  # type: ignore[empty-body]
        ...

    def newClientCreated(
        protocol: "FSDClientProtocol",  # type: ignore
    ) -> None:  # type: ignore[empty-body]
        ...

    def lineReceivedFromClient(
        protocol: "FSDClientProtocol", byte_line: bytes  # type: ignore
    ) -> None:  # type: ignore[empty-body]
        ...

    def clientDisconnected(  # type: ignore[empty-body]
        protocol: "FSDClientProtocol", client: "Client"  # type: ignore
    ) -> bool:
        ...


@implementer(IPyFSDPlugin)
class BasePyFSDPlugin:
    plugin_name = "<plugin name missing>"

    def beforeStart(self, pyfsd: "PyFSDService") -> None:
        ...

    def beforeStop(self) -> None:
        ...

    def newConnectionEstablished(  # type: ignore[empty-body]
        self, protocol: "FSDClientProtocol"
    ) -> bool:
        ...

    def newClientCreated(  # type: ignore[empty-body]
        self, protocol: "FSDClientProtocol"
    ) -> bool:
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
