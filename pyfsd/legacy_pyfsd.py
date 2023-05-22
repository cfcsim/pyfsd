from typing import TYPE_CHECKING

from twisted.cred.portal import Portal
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint

from .auth import CredentialsChecker, Realm
from .factory.client import FSDClientFactory

if TYPE_CHECKING:
    from twisted.enterprise.adbapi import ConnectionPool

    from .metar.manager import MetarManager


class PyFSD:
    client_factory: FSDClientFactory
    db_pool: "ConnectionPool"
    metar_manager: "MetarManager"
    client_endpoint: TCP4ServerEndpoint

    def __init__(
        self,
        db_pool: "ConnectionPool",
        metar_manager: "MetarManager",
        client_port: int,
    ) -> None:
        self.db_pool = db_pool
        self.client_factory = FSDClientFactory(
            Portal(Realm(), checkers=[CredentialsChecker(self.db_pool.runQuery)])
        )
        self.metar_manager = metar_manager
        if metar_manager.cron:
            reactor.callInThread(metar_manager.startCache)
            reactor.addSystemEventTrigger("before", "shutdown", metar_manager.stopCache)
        self.client_port = client_port

    def run(self) -> None:
        self.client_endpoint = TCP4ServerEndpoint(reactor, self.client_port)
        self.client_endpoint.listen(self.client_factory)
        reactor.run()  # type: ignore
