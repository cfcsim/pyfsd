from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, TypedDict

from twisted.internet.defer import Deferred, succeed
from twisted.internet.task import LoopingCall
from twisted.logger import Logger
from twisted.plugin import getPlugins

from .. import plugins
from .fetch import (
    IMetarFetcher,
    MetarInfoDict,
    MetarNotAvailableError,
    NOAAMetarFetcher,
)

# from warnings import catch_warnings  ** not thread safe


if TYPE_CHECKING:
    from metar.Metar import Metar
    from twisted.python.failure import Failure


class CronFetcherInfo(TypedDict):
    failed: Iterable[IMetarFetcher]
    succeed: Optional[IMetarFetcher]


class NotImplementedInfo(TypedDict):
    cron: List[IMetarFetcher]
    once: List[IMetarFetcher]


class MetarManager:
    fetchers: List[IMetarFetcher]
    metar_cache: MetarInfoDict = {}
    cron: bool = False
    config: dict
    cron_time: Optional[float]
    cron_fetcher_info: Optional[CronFetcherInfo] = None
    not_implemented_info: NotImplementedInfo = {"cron": [], "once": []}
    cron_task: Optional[LoopingCall] = None
    logger = Logger()

    def __init__(self, config: dict) -> None:
        self.cron_time = (
            config["cron_time"]
            if config["mode"] == "cron" or config.get("fallback", None) == "cron"
            else None
        )
        self.cron = self.cron_time is not None
        self.config = config
        self.pickFetchers(config["fetchers"])

    def pickFetchers(self, enabled_fetchers: Iterable[str]) -> int:
        count = 1
        temp_fetchers: Dict[str, IMetarFetcher] = {}
        fetchers = []
        temp_fetchers[NOAAMetarFetcher.metar_source] = IMetarFetcher(NOAAMetarFetcher())
        for fetcher in getPlugins(IMetarFetcher, package=plugins):
            count += 1
            temp_fetchers[fetcher.metar_source] = fetcher
        for need_fetcher in enabled_fetchers:
            if need_fetcher not in temp_fetchers:
                self.logger.error(f"No such METAR fetcher: {need_fetcher}")
            else:
                fetchers.append(temp_fetchers[need_fetcher])
        self.fetchers = fetchers
        return count

    def cacheMetar(self) -> None:
        self.logger.info("Fetching METAR")
        fetcher_info: CronFetcherInfo = {"failed": [], "succeed": None}
        fetchers = self.fetchers.copy()

        def giveResult(metars: MetarInfoDict) -> None:
            if fetcher_info["succeed"] is None:
                self.logger.error("No metar fetched")
                # self.metar_cache is not empty mean previous fetch succeeded, keep it
                if not self.metar_cache:
                    self.cron_fetcher_info = fetcher_info
            else:
                # Only overwrite metar_cache if fetch succeed.
                self.logger.info(f"Fetched {len(metars)} METARs.")
                self.metar_cache = metars
                self.cron_fetcher_info = fetcher_info

        def tryNext() -> None:
            if len(fetchers) == 0:
                giveResult({})
                return

            fetcher = fetchers.pop(0)

            if fetcher in self.not_implemented_info["cron"]:
                tryNext()
                return

            def callback(metars: MetarInfoDict) -> None:
                fetcher_info["succeed"] = fetcher
                giveResult(metars)

            def errback(failure: "Failure") -> None:
                if failure.type is not MetarNotAvailableError:
                    self.logger.failure(
                        "Uncaught exception in metar fetcher",
                        failure=failure,
                    )
                fetcher_info["failed"].append(fetcher)  # type: ignore[attr-defined]
                tryNext()

            try:
                fetcher.fetchAll(self.config).addCallback(callback).addErrback(errback)
            except NotImplementedError:
                if fetcher not in self.not_implemented_info["cron"]:
                    self.not_implemented_info["cron"].append(fetcher)
                tryNext()

        tryNext()

    def startCache(self) -> None:
        if self.cron_time is None or not self.cron:
            msg = "No cron time specified"
            raise RuntimeError(msg)
        if self.cron_task is not None and self.cron_task.running:
            msg = "Metar cache task already running"
            raise RuntimeError(msg)
        self.cron_task = LoopingCall(self.cacheMetar)
        self.cron_task.start(self.cron_time)

    def stopCache(self) -> None:
        if self.cron_task is not None and self.cron_task.running:
            self.cron_task.stop()

    def queryEach(
        self,
        icao: str,
        to_skip_fetchers: Iterable[IMetarFetcher] = (),
        ignore_case: bool = True,
    ) -> Deferred[Optional["Metar"]]:
        if ignore_case:
            icao = icao.upper()

        fetchers = self.fetchers.copy()

        for to_skip_fetcher in to_skip_fetchers:
            fetchers.remove(to_skip_fetcher)

        result_deferred: Deferred[Optional["Metar"]] = Deferred()

        def giveResult(metar: Optional["Metar"]) -> None:
            result_deferred.callback(metar)

        def tryNext() -> None:
            if len(fetchers) == 0:
                giveResult(None)
                return

            fetcher = fetchers.pop(0)

            if fetcher in self.not_implemented_info["once"]:
                tryNext()
                return

            def callback(metar: Optional["Metar"]) -> None:
                giveResult(metar)

            def errback(failure: "Failure") -> None:
                self.logger.failure(
                    "Uncaught exception in metar fetcher",
                    failure=failure,
                )
                tryNext()

            try:
                fetcher.fetch(self.config, icao).addCallback(callback).addErrback(
                    errback,
                )
            except NotImplementedError:
                if fetcher not in self.not_implemented_info["once"]:
                    self.not_implemented_info["once"].append(fetcher)
                tryNext()

        tryNext()
        return result_deferred

    def query(self, icao: str, ignore_case: bool = True) -> Deferred[Optional["Metar"]]:
        if ignore_case:
            icao = icao.upper()

        fallback_mode = self.config.get("fallback", None)
        if self.cron:
            if self.cron_task is None:
                if fallback_mode == "once":
                    return self.queryEach(icao, ignore_case=False)
                else:
                    msg = (
                        "Metar cache not available because metar fetch task not "
                        "started. This shouldn't happen."
                    )
                    raise RuntimeError(
                        msg,
                    )
            result = self.metar_cache.get(icao, None)
            if result is None:
                if fallback_mode == "once":
                    return self.queryEach(
                        icao,
                        ignore_case=False,
                        to_skip_fetchers=(self.cron_fetcher_info["succeed"],)
                        if self.config["skip_previous_fetcher"]
                        and self.cron_fetcher_info is not None
                        and self.cron_fetcher_info["succeed"] is not None
                        else (),
                    )
                else:
                    return succeed(None)
            else:
                return succeed(result)
        else:
            if fallback_mode != "cron":
                return self.queryEach(icao, ignore_case=False)
            else:
                result_deferred: Deferred[Optional["Metar"]] = Deferred()

                def handleResult(result: Optional["Metar"]) -> None:
                    if result is None:
                        result_deferred.callback(self.metar_cache.get(icao, None))
                    else:
                        result_deferred.callback(result)

                self.queryEach(icao, ignore_case=False).addCallback(handleResult)
                return result_deferred
