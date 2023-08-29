from inspect import getfile
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    TypedDict,
    Union,
)

from alchimia.engine import TwistedEngine
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable
from twisted.application.internet import TCPServer
from twisted.application.service import Service
from twisted.cred.portal import Portal
from twisted.internet.defer import succeed
from twisted.internet.threads import deferToThread
from twisted.logger import Logger
from twisted.plugin import getPlugins

from . import plugins
from ._version import version as pyfsd_version
from .auth import CredentialsChecker, Realm
from .db_tables import users
from .define.config_check import LiteralValue, MayExist, verifyConfigStruct
from .define.utils import iterCallable
from .factory.client import FSDClientFactory
from .metar.service import MetarService
from .plugin import BasePyFSDPlugin, IPyFSDPlugin, IServiceBuilder, PreventEvent

if TYPE_CHECKING:
    from metar.Metar import Metar
    from twisted.application.service import IService
    from twisted.internet.defer import Deferred

    from .plugin import PluginHandledEventResult, ToHandledByPyFSDEventResult


def formatPlugin(plugin: IPyFSDPlugin) -> str:
    return f"{plugin.plugin_name} ({getfile(type(plugin))})"


def formatService(plugin: IServiceBuilder) -> str:
    return f"{plugin.service_name} ({getfile(type(plugin))})"


MAX_API = BasePyFSDPlugin.api
PLUGIN_EVENTS = tuple(func.__name__ for func in iterCallable(BasePyFSDPlugin))
config: Optional[dict] = None


class PluginDict(TypedDict):
    all: Tuple[IPyFSDPlugin, ...]
    tagged: Dict[str, List[IPyFSDPlugin]]


class PyFSDService(Service):
    client_factory: Optional[FSDClientFactory] = None
    fetch_metar: Optional[Callable[[str], "Deferred[Optional[Metar]]"]] = None
    db_engine: Optional[TwistedEngine] = None
    portal: Optional[Portal] = None
    plugins: Optional[PluginDict] = None
    logger: Logger = Logger()
    config: dict
    version = pyfsd_version

    def __init__(self, this_config: dict) -> None:
        global config
        assert config is None
        config = this_config
        self.config = this_config
        self.checkConfig()
        self.connectDatabase()
        self.checkAndInitDatabase()
        self.makePortal()
        self.pickPlugins()

    def startService(self) -> None:
        self.logger.info("PyFSD {version}", version=self.version)
        root_plugin_config = self.config.get("plugin", {})
        if self.plugins is not None:
            for plugin in self.plugins["all"]:
                self.logger.info(
                    "Loading plugin {plugin}",
                    plugin=formatPlugin(plugin),
                )
                plugin.beforeStart(
                    self, root_plugin_config.get(plugin.plugin_name, None)
                )
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
                    "database": {"url": str},
                    "client": {
                        "port": int,
                        "motd": str,
                        "motd_encoding": str,
                        "blacklist": list,
                    },
                    "metar": {
                        "mode": LiteralValue("cron", "once"),
                        "fallback": MayExist(LiteralValue("cron", "once")),
                        "fetchers": list,
                        "cron_time": MayExist(int),
                        "skip_previous_fetcher": MayExist(bool),
                    },
                    "plugin": MayExist(dict),
                }
            },
        )
        # Metar
        metar_cfg = self.config["pyfsd"]["metar"]
        fallback_mode = metar_cfg.get("fallback", None)
        if fallback_mode is not None:
            assert (
                metar_cfg["mode"] != metar_cfg["fallback"]
            ), "Metar fallback mode cannot be the same as normal mode."
        if metar_cfg["mode"] == "cron" or fallback_mode == "cron":
            if "cron_time" not in metar_cfg:
                raise KeyError("pyfsd.metar.cron_time")
            elif fallback_mode == "once" and "skip_previous_fetcher" not in metar_cfg:
                raise KeyError("pyfsd.metar.skip_previous_fetcher")
        for key, value in self.config["plugin"].items():
            if not isinstance(value, dict):
                raise TypeError(f"plugin.{key}' must be section")

    def connectDatabase(self) -> None:
        from twisted.internet import reactor

        self.db_engine = TwistedEngine.from_sqlalchemy_engine(
            reactor, create_engine(self.config["pyfsd"]["database"]["url"])
        )

    def checkAndInitDatabase(self) -> None:
        assert self.db_engine is not None, "Must connect database first."

        def createIfNotExist(exist: bool) -> None:
            if not exist:
                self.db_engine.execute(CreateTable(users))  # type: ignore[union-attr]

        self.db_engine.has_table("users").addCallback(createIfNotExist)

    def makePortal(self) -> None:
        assert self.db_engine is not None, "Must connect database first."
        self.portal = Portal(Realm, (CredentialsChecker(self.db_engine.execute),))

    def getClientService(self) -> TCPServer:
        assert self.fetch_metar is not None, "Must start metar service first"
        assert self.portal is not None, "Must create portal first."
        self.client_factory = FSDClientFactory(
            self.portal,
            self.fetch_metar,
            self.deferEvent,
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

    def getServicePlugins(self) -> Tuple["IService", ...]:
        temp_plugin_creators: List[IServiceBuilder] = []
        root_plugin_config = self.config.get("plugin", {})
        for plugin in getPlugins(IServiceBuilder, plugins):
            if plugin in temp_plugin_creators:
                self.logger.debug(
                    "service {service} already loaded, skipping.",
                    service=formatService(plugin),
                )
            else:
                temp_plugin_creators.append(plugin)
        temp_plugins = []
        for creator in temp_plugin_creators:
            temp_plugins.append(
                creator.buildService(
                    self, root_plugin_config.get(creator.service_name, None)
                )
            )
        return tuple(temp_plugins)

    def pickPlugins(self) -> None:
        all_plugins = []
        event_handlers: Dict[str, List[IPyFSDPlugin]] = dict(
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
                            event_handlers[event].append(plugin)

        self.plugins = {"all": tuple(all_plugins), "tagged": event_handlers}

    def iterPluginByEventName(self, event_name: str) -> Iterable[IPyFSDPlugin]:
        assert self.plugins is not None, "plugin not loaded"
        if event_name not in PLUGIN_EVENTS:
            raise ValueError(f"Invaild event {event_name}")
        return iter(self.plugins["tagged"][event_name])

    def iterHandlerByEventName(self, event_name: str) -> Iterable[Callable]:
        return (
            getattr(plugin, event_name)
            for plugin in self.iterPluginByEventName(event_name)
        )

    def triggerEvent(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
        prevent_able: bool = False,
        handle_able: bool = False,
    ) -> Union["PluginHandledEventResult", "ToHandledByPyFSDEventResult",]:
        handlers: List[Callable] = []
        for plugin in self.iterPluginByEventName(event_name):
            try:
                handler = getattr(plugin, event_name)(*args, **kwargs)
            except PreventEvent:
                if not prevent_able:
                    Logger(source=plugin).error(f"Cannot prevent event: {event_name}")
                else:
                    result: PluginHandledEventResult = {
                        "handled_by_plugin": True,
                        "plugin": plugin,
                    }
                    for handler in handlers:
                        handler(result)
                    return result
            except BaseException:
                Logger(source=plugin).failure("Error happened during call plugin")
            else:
                if handler is not None:
                    if handle_able:
                        handlers.append(handler)
                    else:
                        Logger(source=plugin).error(
                            f"Cannot handle event: {event_name}"
                        )
        return {"handled_by_plugin": False, "handlers": handlers}

    def deferEvent(
        self,
        event_name: str,
        args: Iterable,
        kwargs: Mapping,
        prevent_able: bool = False,
        handle_able: bool = False,
        in_thread: bool = False,
    ) -> """Deferred[
        Union[
            "PluginHandledEventResult",
            "ToHandledByPyFSDEventResult",
        ]
    ]""":
        if in_thread:
            return deferToThread(  # type: ignore[no-any-return]
                self.triggerEvent, event_name, args, kwargs, prevent_able, handle_able
            )
        else:
            return succeed(
                self.triggerEvent(event_name, args, kwargs, prevent_able, handle_able)
            )
