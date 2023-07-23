from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, TypedDict

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


class CronFetcherInfo(TypedDict):
    failed: Iterable[IMetarFetcher]
    succeed: Optional[IMetarFetcher]


class MetarManager:
    fetchers: List[IMetarFetcher]
    metar_cache: MetarInfoDict = {}
    cron: bool = False
    config: dict
    cron_time: Optional[float]
    cron_fetcher_info: Optional[CronFetcherInfo] = None
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
        # warn = []
        fetcher_info: CronFetcherInfo = {"failed": (), "succeed": None}
        failed_fetchers = []
        for fetcher in self.fetchers:
            try:
                # with catch_warnings(record=True) as warn:
                self.metar_cache = fetcher.fetchAll(self.config)
                fetcher_info["succeed"] = fetcher
                break
            except (NotImplementedError, MetarNotAvailableError):
                failed_fetchers.append(fetcher)
        fetcher_info["failed"] = tuple(failed_fetchers)
        self.fetcher_info = fetcher_info
        self.logger.info(
            f"Fetched {len(self.metar_cache)} METARs."  # with {len(warn)} warnings."
        )

    def startCache(self, in_thread: bool = False) -> None:
        if self.cron_time is None or not self.cron:
            raise RuntimeError("No cron time specified")
        if self.cron_task is not None and self.cron_task.running:
            raise RuntimeError("Metar cache task already running")
        if in_thread:
            from twisted.internet.threads import deferToThread

            self.cron_task = LoopingCall(lambda: deferToThread(self.cacheMetar))
        else:
            self.cron_task = LoopingCall(self.cacheMetar)
        self.cron_task.start(self.cron_time)

    def stopCache(self) -> None:
        if self.cron_task is not None and self.cron_task.running:
            self.cron_task.stop()

    def query(self, icao: str) -> Optional["Metar"]:
        def queryEach(to_skip: Iterable[IMetarFetcher] = ()) -> Optional["Metar"]:
            for fetcher in self.fetchers:
                if fetcher in to_skip:
                    continue
                try:
                    result = fetcher.fetch(self.config, icao)
                    if result is not None:
                        return result
                except (NotImplementedError, MetarNotAvailableError):
                    pass
            return None

        fallback_mode = self.config.get("fallback", None)
        if self.cron:
            if self.cron_task is None:
                if fallback_mode == "once":
                    return queryEach()
                else:
                    raise RuntimeError("Metar cache not available")
            result = self.metar_cache.get(icao, None)
            if result is None:
                if fallback_mode == "once":
                    return queryEach(
                        to_skip=self.fetcher_info["failed"]
                        if self.config["skip_failed_fetchers"]
                        else ()
                    )
                else:
                    return None
            else:
                return result
        else:
            result = queryEach()
            if result is None and fallback_mode == "cron":
                return self.metar_cache.get(icao, None)
            else:
                return result
