# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
"""PyFSD plugin architecture."""
from typing import TYPE_CHECKING, Optional, Union

from zope.interface import implementer

from .interfaces import IPyFSDPlugin
from .types import PluginHandledEventResult, PyFSDHandledLineResult

if TYPE_CHECKING:
    from ..object.client import Client
    from ..protocol.client import FSDClientProtocol
    from ..service import PyFSDService


__all__ = ["API_LEVEL", "PreventEvent", "BasePyFSDPlugin"]

API_LEVEL = 3


class PreventEvent(BaseException):
    """Prevent a PyFSD plugin event.

    Attributes:
        result: The event result reported by plugin.
    """

    result: dict

    def __init__(self, result: dict = {}) -> None:
        self.result = result


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
