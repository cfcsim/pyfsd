from typing import TYPE_CHECKING, Iterable, List, Optional
from warnings import catch_warnings

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

if TYPE_CHECKING:
    from metar.Metar import Metar


class MetarManager:
    fetchers: List[IMetarFetcher]
    metar_cache: MetarInfoDict = {}
    cron: bool = False
    cron_time: Optional[float]
    cron_task: Optional[LoopingCall] = None
    logger = Logger()

    def __init__(
        self, cron_time: Optional[float], enabled_fetchers: Iterable[str]
    ) -> None:
        self.pickFetchers(enabled_fetchers)
        self.cron_time = cron_time
        self.cron = cron_time is not None

    def pickFetchers(self, enabled_fetchers: Iterable[str]) -> int:
        count = 1
        temp_fetchers = {}
        fetchers = []
        temp_fetchers[NOAAMetarFetcher.name] = NOAAMetarFetcher()
        for fetcher in getPlugins(IMetarFetcher, package=plugins):
            count += 1
            temp_fetchers[fetcher.name] = fetcher
        for need_fetcher in enabled_fetchers:
            if need_fetcher not in temp_fetchers:
                self.logger.error(f"No such METAR fetcher: {need_fetcher}")
            else:
                fetchers.append(temp_fetchers[need_fetcher])
        self.fetchers = fetchers
        return count

    def cacheMetar(self) -> None:
        self.logger.info("Fetching METAR")
        warn = []
        for fetcher in self.fetchers:
            try:
                with catch_warnings(record=True) as warn:
                    self.metar_cache = fetcher.fetchAll()
            except NotImplementedError or MetarNotAvailableError:
                pass
            else:
                break
        self.logger.info(
            f"Fetched {len(self.metar_cache)} METARs with {len(warn)} warnings."
        )

    def startCache(self) -> None:
        if self.cron_time is None or not self.cron:
            raise RuntimeError("No cron time specified")
        if self.cron_task is not None and self.cron_task.running:
            raise RuntimeError("Metar cache task already running")
        self.cron_task = LoopingCall(self.cacheMetar)
        self.cron_task.start(self.cron_time)

    def stopCache(self) -> None:
        if self.cron_task is not None and self.cron_task.running:
            self.cron_task.stop()

    def query(self, icao: str) -> Optional["Metar"]:
        if self.cron:
            if self.cron_task is None:
                raise RuntimeError("Metar cache not available")
            return self.metar_cache.get(icao)
        else:
            for fetcher in self.fetchers:
                try:
                    with catch_warnings():
                        return fetcher.fetch(icao)
                except NotImplementedError or MetarNotAvailableError:
                    pass
        return None
