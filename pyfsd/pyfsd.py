from typing import TYPE_CHECKING, Optional

from twisted.application.service import Application, IServiceCollection, Service
from twisted.application.strports import service

# from .auth import CredentialsChecker, Realm
from .factory.client import FSDClientFactory

# from twisted.cred.portal import Portal
# from twisted.internet import reactor
# from twisted.internet.endpoints import TCP4ServerEndpoint


if TYPE_CHECKING:
    from twisted.python.components import Componentized


class PyFSDService(Service):
    client_factory: Optional[FSDClientFactory] = None

    def makeClientFactory(self) -> FSDClientFactory:
        self.client_factory = FSDClientFactory(None)
        return self.client_factory


def makeApplication(
    client_strport: str, uid: Optional[int] = None, gid: Optional[int] = None
) -> "Componentized":
    app = Application("PyFSD", uid=uid, gid=gid)
    pyfsd = PyFSDService()
    serviceCollection = IServiceCollection(app)
    pyfsd.setServiceParent(serviceCollection)
    service(client_strport, pyfsd.makeClientFactory()).setServiceParent(
        serviceCollection
    )
    return app
