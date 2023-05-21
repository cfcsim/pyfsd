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
from .plugin import BasePyFSDPlugin, IPyFSDPlugin

if TYPE_CHECKING:
    from metar.Metar import Metar
    from twisted.internet.defer import Deferred


class PyFSDService(Service):
    client_factory: Optional[FSDClientFactory] = None
    fetch_metar: Optional[Callable[[str], "Deferred[Optional[Metar]]"]] = None
    db_pool: Optional[ConnectionPool] = None
    portal: Optional[Portal] = None
    plugins: Optional[Tuple[IPyFSDPlugin]] = None
    logger: Logger = Logger()
    config: dict

    def __init__(self, config: dict) -> None:
        self.config = config
        self.checkConfig()
        self.connectDatabase()
        self.checkAndInitDatabase()
        self.makePortal()
        self.pickPlugins()

    def startService(self) -> None:
        if self.plugins is not None:
            for plugin in self.plugins:
                self.logger.info("Loading plugin {plugin.plugin_name}", plugin=plugin)
                plugin.beforeStart(self)  # type: ignore
            super().startService()

    def stopService(self) -> None:
        if self.plugins is not None:
            for plugin in self.plugins:
                plugin.beforeStop()  # type: ignore[misc]
            super().stopService()

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
                self.db_pool = source.makeDBPool(
                    self.config["pyfsd"]["database"]  # type: ignore
                )  # type: ignore[call-arg]
                return
        self.logger.warn(
            "No such database source {source_name}, fallback to sqlite3.",
            source_name=source_name,
        )
        self.db_pool = SQLite3DBMaker.makeDBPool(self.config["pyfsd"]["database"])

    def checkAndInitDatabase(self) -> None:
        assert self.db_pool is not None, "Must connect database first."
        self.db_pool.runOperation(
            """CREATE TABLE IF NOT EXISTS users(
                callsign TEXT NOT NULL,
                password TEXT NOT NULL,
                rating INT UNSIGNED NOT NULL
            );"""
        )

    def makePortal(self) -> None:
        assert self.db_pool is not None, "Must connect database first."
        self.portal = Portal(Realm, (CredentialsChecker(self.db_pool.runQuery),))

    def getClientService(self) -> TCPServer:
        assert self.fetch_metar is not None, "Must start metar service first"
        assert self.portal is not None, "Must create portal first."
        self.client_factory = FSDClientFactory(
            self.portal,
            self.fetch_metar,
            self.findPluginsByEvent,
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

    def getServicePlugins(self) -> Tuple[IService, ...]:
        return tuple(getPlugins(IService, plugins))

    def pickPlugins(self):
        temp_plugins = []
        for plugin in getPlugins(IPyFSDPlugin, plugins):
            temp_plugins.append(plugin)
        self.plugins = tuple(temp_plugins)

    def findPluginsByEvent(self, event_name: str):
        assert self.plugins is not None, "plugin not loaded"
        if not hasattr(getattr(BasePyFSDPlugin, event_name, None), "__call__"):
            raise ValueError(f"Invaild event {event_name}")
        for plugin in self.plugins:
            if not hasattr(plugin, event_name):
                continue
            plugin_class = type(plugin)
            if issubclass(plugin_class, BasePyFSDPlugin):
                plugin_handler = getattr(plugin_class, event_name, None)
                if not hasattr(plugin_handler, "__call__"):
                    continue
                if plugin_handler is getattr(BasePyFSDPlugin, event_name):
                    continue
            yield plugin
