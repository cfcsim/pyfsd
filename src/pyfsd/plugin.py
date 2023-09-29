# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
"""PyFSD plugin architecture."""
from typing import TYPE_CHECKING, Literal, Optional, Tuple, TypedDict, Union

from zope.interface import Attribute, Interface, implementer

if TYPE_CHECKING:
    from twisted.application.service import IService

    from .object.client import Client
    from .protocol.client import FSDClientProtocol
    from .service import PyFSDService


API_LEVEL = 3


class PluginHandledEventResult(TypedDict):
    """A result handled by plugin.
    This means a plugin raised `pyfsd.plugin.PreventEvent`.

    Attributes:
        handled_by_plugin: Event handled by plugin or not.
        plugin: The plugin.
    """

    handled_by_plugin: Literal[True]
    plugin: "IPyFSDPlugin"


class PyFSDHandledEventResult(TypedDict):
    """A result handled by PyFSD.

    Attributes:
        handled_by_plugin: Event handled by plugin or not.
        success: The event successfully handled or not.
    """

    handled_by_plugin: Literal[False]
    success: bool


class PyFSDHandledLineResult(PyFSDHandledEventResult):
    """A lineReceivedFromClient result handled by PyFSD.

    Attributes:
        handled_by_plugin (Literal[False]): Event handled by plugin or not.
        success (bool): The event successfully handled or not.
        packet_ok: The packet is correct or not.
        has_result: Succeed in generating result or not.
    """

    packet_ok: bool
    has_result: bool


class PreventEvent(BaseException):
    """Prevent a PyFSD plugin event.

    Attributes:
        result: The event result reported by plugin.
    """

    result: dict

    def __init__(self, result: dict = {}) -> None:
        self.result = result


class IPyFSDPlugin(Interface):
    """Interface of PyFSD Plugin.

    Attributes:
        plugin_name: Name of this plugin.
        api: API level of this plugin.
        version: int and human readable version of this plugin.
        expected_config: Configuration structure description.
            structure parameter of pyfsd.define.config_check function.
            None if this plugin doesn't need config. (disables config check)
    """

    plugin_name: str = Attribute("plugin_name", "Name of this plugin.")
    api: int = Attribute("api", "API level of this plugin.")
    version: Tuple[int, str] = Attribute(
        "version", "int and human readable version of this plugin."
    )
    expected_config: Optional[dict] = Attribute(
        "expected_config", "Configuration structure description."
    )

    def beforeStart(pyfsd: "PyFSDService", config: Optional[dict]) -> None:
        """Called before services start.

        Args:
            pyfsd: PyFSD Service.
            config: plugin.<plugin_name> section of PyFSD configure file.
                None if the section doesn't exist.
        """

    def afterStart(pyfsd: "PyFSDService", config: Optional[dict]) -> None:
        """Called while service `pyfsd.service.PyFSDService` starting.

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

    def auditLineFromClient(
        protocol: "FSDClientProtocol",
        line: bytes,
        result: Union[PyFSDHandledLineResult, PluginHandledEventResult],
    ) -> None:
        """Called when line received from client (after lineReceivedFromClient).
        Note that this event cannot be prevented.

        Args:
            protocol: Protocol of the connection which received line.
            line: Line data.
            result: The lineReceivedFromClient event result.

        """

    def clientDisconnected(
        protocol: "FSDClientProtocol", client: Optional["Client"]
    ) -> None:
        """Called when connection disconnected.

        Args:
            protocol: The protocol of the connection which disconnected.
            client: The client attribute of the protocol.
        """


class IServiceBuilder(Interface):
    """Interface of service builder, a object which can build a service.

    Attributes:
        service_name: Name of the to-build service.
    """

    service_name: str = Attribute("service_name", "Name of the to-build service.")

    def buildService(pyfsd: "PyFSDService", config: Optional[dict]) -> "IService":
        """Build a service.

        Args:
            config: plugin.<service_name> section of PyFSD configure file.
                None if the section doesn't exist.

        Returns:
            A twisted service (IService).
        """


class ICallAfterStartPlugin(Interface):
    """Interface of call after start plugin.

    Syntactic sugar of IPyFSDPlugin.afterStart
    """

    def __call__(pyfsd: "PyFSDService", all_config: dict) -> None:
        """Called while service `pyfsd.service.PyFSDService` starting.

        Args:
            pyfsd: PyFSD Service.
            all_config: PyFSD configure file.
        """


@implementer(IPyFSDPlugin)
class BasePyFSDPlugin:
    """(A?)Base class of PyFSD Plugin."""

    plugin_name = "<plugin name missing>"
    api = -1
    version = (-1, "<plugin version missing>")
    expected_config = None

    def beforeStart(self, pyfsd: "PyFSDService", config: Optional[dict]) -> None:
        ...

    def afterStart(self, pyfsd: "PyFSDService", config: Optional[dict]) -> None:
        ...

    def beforeStop(self) -> None:
        ...

    def newConnectionEstablished(self, protocol: "FSDClientProtocol") -> None:
        ...

    def newClientCreated(self, protocol: "FSDClientProtocol") -> None:
        ...

    def lineReceivedFromClient(
        self, protocol: "FSDClientProtocol", line: bytes
    ) -> None:
        ...

    def auditLineFromClient(
        self,
        protocol: "FSDClientProtocol",
        line: bytes,
        result: Union[PyFSDHandledLineResult, PluginHandledEventResult],
    ) -> None:
        ...

    def clientDisconnected(
        self, protocol: "FSDClientProtocol", client: Optional["Client"]
    ) -> None:
        ...
