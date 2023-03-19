from twisted.cred.portal import Portal  # noqa: E402
from twisted.enterprise.adbapi import ConnectionPool
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint

from .auth import CredentialsChecker, Realm
from .config import config
from .factory.client import FSDClientFactory


class PyFSD:
    client_factory: FSDClientFactory
    db_pool: ConnectionPool

    def __init__(self) -> None:
        self.db_pool = ConnectionPool(
            "sqlite3", config.get("pyfsd", "database_name"), check_same_thread=False
        )
        self.client_factory = FSDClientFactory(
            Portal(Realm(), checkers=[CredentialsChecker(self.db_pool.runQuery)])
        )

    def run(self) -> None:
        TCP4ServerEndpoint(reactor, 6809).listen(self.client_factory)
        reactor.run()  # type: ignore
