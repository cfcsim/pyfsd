from typing import Optional

from twisted.application.service import Service
from twisted.application.internet import TCPServer

# from .auth import CredentialsChecker, Realm
from .factory.client import FSDClientFactory

# from twisted.cred.portal import Portal
# from twisted.internet import reactor
# from twisted.internet.endpoints import TCP4ServerEndpoint


class PyFSDService(Service):
    client_factory: Optional[FSDClientFactory] = None
    config: dict

    def __init__(self, config: dict) -> None:
        self.config = config

    def getClientService(self) -> TCPServer:
        self.client_factory = FSDClientFactory(
            None,
            self.config["pyfsd"]["client"]["blacklist"],
            self.config["pyfsd"]["client"]["motd"],
        )
        return TCPServer(
            int(self.config["pyfsd"]["client"]["port"]), self.client_factory
        )
