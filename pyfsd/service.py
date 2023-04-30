from typing import TYPE_CHECKING, Callable, Optional, Tuple

from twisted.application.internet import TCPServer
from twisted.application.service import IService, Service
from twisted.cred.portal import Portal
from twisted.enterprise.adbapi import ConnectionPool
from twisted.logger import Logger
from twisted.plugin import getPlugins

from . import plugins
from .auth import CredentialsChecker, Realm
from .database import IDatabaseMaker, SQLite3DBMaker
from .define.utils import verifyConfigStruct
from .factory.client import FSDClientFactory
from .metar.service import MetarService
from .plugin import IPyFSDPlugin

if TYPE_CHECKING:
    from metar.Metar import Metar
    from twisted.internet.defer import Deferred


class PyFSDService(Service):
    client_factory: Optional[FSDClientFactory] = None
    fetch_metar: Callable[[str], "Deferred[Optional[Metar]]"]
    db_pool: ConnectionPool
    portal: Portal
    logger: Logger = Logger()
    plugins: Tuple[IPyFSDPlugin]
    config: dict

    def __init__(self, config: dict) -> None:
        self.config = config
        self.checkConfig()
        self.connectDatabase()
        self.checkAndInitDatabase()
        self.makePortal()
        self.pickPlugins()

    def startService(self) -> None:
        for plugin in self.plugins:
            self.logger.info("Loading plugin {plugin.plugin_name}", plugin=plugin)
            plugin.beforeStart(self)
        super().startService()

    def checkConfig(self) -> None:
        verifyConfigStruct(
            self.config,
            {
                "pyfsd": {
                    "database": {"source": str},
                    "client": {"port": int, "motd": str, "blacklist": list},
                    "metar": {"mode": str, "fetchers": list},
                }
            },
        )
        if self.config["pyfsd"]["metar"]["mode"] == "cron":
            verifyConfigStruct(
                self.config["pyfsd"]["metar"], {"cron_time": int}, prefix="pyfsd.metar"
            )
        elif self.config["pyfsd"]["metar"]["mode"] != "once":
            raise ValueError(
                f"Invaild metar mode: {self.config['pyfsd']['metar']['mode']}"
            )

    def connectDatabase(self) -> None:
        source_name = self.config["pyfsd"]["database"]["source"]
        if source_name == "sqlite3":
            self.db_pool = SQLite3DBMaker.makeDBPool(self.config["pyfsd"]["database"])
            return
        for source in getPlugins(IDatabaseMaker, plugins):
            if source.db_source == source_name:
                self.db_pool = source.makeDBPool(self.config["pyfsd"]["database"])
                return
        self.logger.warn(
            "No such database source {source_name}, fallback to sqlite3.",
            source_name=source_name,
        )
        self.db_pool = SQLite3DBMaker.makeDBPool(self.config["pyfsd"]["database"])

    def checkAndInitDatabase(self) -> None:
        self.db_pool.runOperation(
            """CREATE TABLE IF NOT EXISTS users(
                callsign TEXT NOT NULL,
                password TEXT NOT NULL,
                rating INT UNSIGNED NOT NULL
            );"""
        )

    def makePortal(self) -> None:
        self.portal = Portal(Realm, (CredentialsChecker(self.db_pool.runQuery),))

    def getClientService(self) -> TCPServer:
        assert self.fetch_metar is not None, "Must start metar service first"
        self.client_factory = FSDClientFactory(
            self.portal,
            self.fetch_metar,
            self.config["pyfsd"]["client"]["blacklist"],
            self.config["pyfsd"]["client"]["motd"].splitlines(),
        )
        return TCPServer(
            int(self.config["pyfsd"]["client"]["port"]), self.client_factory
        )

    def getMetarService(self) -> MetarService:
        metar_service = MetarService(
            self.config["pyfsd"]["metar"]["cron_time"]
            if self.config["pyfsd"]["metar"]["mode"] == "cron"
            else None,
            self.config["pyfsd"]["metar"]["fetchers"],
        )
        self.fetch_metar = metar_service.query
        return metar_service

    def getServicePlugins(self) -> Tuple[IService]:
        return tuple(getPlugins(IService, plugins))

    def pickPlugins(self):
        temp_plugins = []
        for plugin in getPlugins(IPyFSDPlugin, plugins):
            temp_plugins.append(plugin)
        self.plugins = tuple(temp_plugins)
