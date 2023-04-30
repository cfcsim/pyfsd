from typing import TYPE_CHECKING

from zope.interface import Attribute, Interface, implementer

if TYPE_CHECKING:
    from .service import PyFSDService


class IPyFSDPlugin(Interface):
    plugin_name = Attribute("plugin_name")

    def beforeStart(pyfsd: "PyFSDService") -> None:
        ...

    def beforeStop() -> None:
        ...


@implementer(IPyFSDPlugin)
class BasePyFSDPlugin:
    plugin_name = "<plugin name missing>"

    def beforeStart(self, pyfsd: "PyFSDService") -> None:
        ...

    def beforeStop(self) -> None:
        ...
