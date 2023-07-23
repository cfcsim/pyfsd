from inspect import getfile
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    TypedDict,
)

from twisted.application.internet import TCPServer
from twisted.application.service import IService, Service
from twisted.cred.portal import Portal
from twisted.enterprise.adbapi import ConnectionPool
from twisted.logger import Logger
from twisted.plugin import getPlugins

from . import plugins
from ._version import __version__
from .auth import CredentialsChecker, Realm
from .database import IDatabaseMaker, SQLite3DBMaker
from .define.utils import iterCallable, verifyConfigStruct
from .factory.client import FSDClientFactory
from .metar.service import MetarService
from .plugin import BasePyFSDPlugin, IPyFSDPlugin

if TYPE_CHECKING:
    from metar.Metar import Metar
    from twisted.internet.defer import Deferred


def formatPlugin(plugin: IPyFSDPlugin) -> str:
    return f"{plugin.plugin_name} ({getfile(type(plugin))})"


def formatService(plugin: IService) -> str:
    plugin_type = type(plugin)
    if isinstance(plugin.name, str):
        return f"{plugin.name} ({plugin_type.__name__} from {getfile(plugin_type)})"
    else:
        return f"{plugin_type.__name__} (getfile(plugin_type))"


MAX_API = BasePyFSDPlugin.api
PLUGIN_EVENTS = tuple(func.__name__ for func in iterCallable(BasePyFSDPlugin))


class PluginDict(TypedDict):
    all: Tuple[IPyFSDPlugin, ...]
    tagged: Dict[str, List[Callable]]


class PyFSDService(Service):
    client_factory: Optional[FSDClientFactory] = None
    fetch_metar: Optional[Callable[[str], "Deferred[Optional[Metar]]"]] = None
    db_pool: Optional[ConnectionPool] = None
    portal: Optional[Portal] = None
    plugins: Optional[PluginDict] = None
    logger: Logger = Logger()
    config: dict
    version = __version__

    def __init__(self, config: dict) -> None:
        self.config = config
        self.checkConfig()
        self.connectDatabase()
        self.checkAndInitDatabase()
        self.makePortal()
        self.pickPlugins()

    def startService(self) -> None:
        self.logger.info("PyFSD {version}", version=self.version)
        has_root_plugin_config = "plugin" in self.config
        if self.plugins is not None:
            for plugin in self.plugins["all"]:
                if not has_root_plugin_config:
                    config = None
                else:
                    config = self.config["plugin"].get(plugin.plugin_name, None)
                self.logger.info(
                    "Loading plugin {plugin}",
                    plugin=formatPlugin(plugin),
                )
                plugin.beforeStart(self, config)
            super().startService()

    def stopService(self) -> None:
        if self.plugins is not None:
            for plugin in self.plugins["all"]:
                plugin.beforeStop()
            super().stopService()

    def checkConfig(self) -> None:
        verifyConfigStruct(
            self.config,
            {
                "pyfsd": {
                    "database": {"source": str},
                    "client": {
                        "port": int,
                        "motd": str,
                        "motd_encoding": str,
                        "blacklist": list,
                    },
                    "metar": {"mode": str, "fetchers": list},
                }
            },
        )
        # Metar
        metar_cfg = self.config["pyfsd"]["metar"]
        fallback_mode = metar_cfg.get("fallback", None)
        if fallback_mode is not None:
            verifyConfigStruct(
                metar_cfg,
                {"fallback": str, "skip_failed_fetchers": bool},
                prefix="pyfsd.metar.",
            )
            assert metar_cfg["mode"] != metar_cfg["fallback"]
        if metar_cfg["mode"] == "cron" or fallback_mode == "cron":
            verifyConfigStruct(metar_cfg, {"cron_time": int}, prefix="pyfsd.metar.")
        elif metar_cfg["mode"] != "once" or (
            fallback_mode is not None and fallback_mode != "once"
        ):
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
            self.iterHandlerByEventName,
            self.config["pyfsd"]["client"]["blacklist"],
            self.config["pyfsd"]["client"]["motd"]
            .encode(self.config["pyfsd"]["client"]["motd_encoding"])
            .splitlines(),
        )
        return TCPServer(
            int(self.config["pyfsd"]["client"]["port"]), self.client_factory
        )

    def getMetarService(self) -> MetarService:
        metar_service = MetarService(self.config["pyfsd"]["metar"])
        self.fetch_metar = metar_service.query
        return metar_service

    def getServicePlugins(self) -> Tuple[IService, ...]:
        temp_plugins: List[IService] = []
        for plugin in getPlugins(IService, plugins):
            if plugin in temp_plugins:
                self.logger.debug(
                    "service {service} already loaded, skipping.",
                    service=formatService(plugin),
                )
            else:
                temp_plugins.append(plugin)
        return tuple(temp_plugins)

    def pickPlugins(self) -> None:
        all_plugins = []
        event_handlers: Dict[str, List[Callable]] = dict(
            (name, []) for name in PLUGIN_EVENTS
        )
        for plugin in getPlugins(IPyFSDPlugin, plugins):
            if plugin in all_plugins:
                self.logger.debug(
                    "plugin {plugin} already loaded, skipping.",
                    plugin=formatPlugin(plugin),
                )
            else:
                if plugin.api > MAX_API:
                    self.logger.error(
                        "{plugin} needs API {api}, try update PyFSD",
                        api=plugin.api,
                        plugin=formatPlugin(plugin),
                    )
                else:
                    all_plugins.append(plugin)
                    for event in PLUGIN_EVENTS:
                        if hasattr(plugin, event) and getattr(
                            type(plugin), event
                        ) is not getattr(BasePyFSDPlugin, event):
                            event_handlers[event].append(getattr(plugin, event))

        self.plugins = {"all": tuple(all_plugins), "tagged": event_handlers}

    def iterHandlerByEventName(self, event_name: str) -> Iterator[Callable]:
        assert self.plugins is not None, "plugin not loaded"
        if event_name not in PLUGIN_EVENTS:
            raise ValueError(f"Invaild event {event_name}")
        return iter(self.plugins["tagged"][event_name])
