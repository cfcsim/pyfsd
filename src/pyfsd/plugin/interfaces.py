# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
"""Interfaces of PyFSD plugin architecture."""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Tuple, Union

if TYPE_CHECKING:
    from ..object.client import Client
    from ..protocol.client import FSDClientProtocol
    from ..service import PyFSDService
    from .types import PluginHandledEventResult, PyFSDHandledLineResult

__all__ = ["IPyFSDPlugin", "ICallAfterStartPlugin", "IServiceBuilder"]


class IPlugin(ABC):
    """Base interface of plugin."""


class IPyFSDPlugin(ABC):
    """Interface of PyFSD Plugin.

    Attributes:
        plugin_name: Name of this plugin.
        api: API level of this plugin.
        version: int and human readable version of this plugin.
        expected_config: Configuration structure description.
            structure parameter of pyfsd.define.config_check function.
            None if this plugin doesn't need config. (disables config check)
    """

    @property
    @abstractmethod
    def plugin_name() -> str:
        """Name of this plugin."""

    @property
    @abstractmethod
    def api() -> int:
        """API level of this plugin."""

    @property
    @abstractmethod
    def vesion() -> Tuple[int, str]:
        """int + human readable version of this plugin."""

    @property
    @abstractmethod
    def expected_config() -> Optional[dict]:
        """Configuration structure description."""

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


class IServiceBuilder(ABC):
    """Interface of service builder, a object which can build a service.

    Attributes:
        service_name: Name of the to-build service.
    """

    @property
    @abstractmethod
    def service_name() -> str:
        """Name of the to-build service."""

    @abstractmethod
    def buildService(pyfsd: "PyFSDService", config: Optional[dict]) -> "IService":
        """Build a service.

        Args:
            config: plugin.<service_name> section of PyFSD configure file.
                None if the section doesn't exist.

        Returns:
            A twisted service (IService).
        """


class ICallAfterStartPlugin(ABC):
    """Interface of call after start plugin.

    Syntactic sugar of IPyFSDPlugin.afterStart
    """

    @abstractmethod
    def __call__(pyfsd: "PyFSDService", all_config: dict) -> None:
        """Called while service `pyfsd.service.PyFSDService` starting.

        Args:
            pyfsd: PyFSD Service.
            all_config: PyFSD configure file.
        """
