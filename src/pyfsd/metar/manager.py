"""PyFSD metar manager.

See .MetarManager
"""
from asyncio import create_task
from asyncio import sleep as asleep
from typing import (
    TYPE_CHECKING,
    Dict,
    Iterable,
    List,
    NoReturn,
    Optional,
    Tuple,
)
from warnings import filterwarnings

from loguru import logger

from .. import plugins
from ..plugin.collect import iter_submodule_plugins
from .fetch import (
    MetarFetcher,
    MetarInfoDict,
    NOAAMetarFetcher,
)

if TYPE_CHECKING:
    from asyncio import Task

    from metar.Metar import Metar

__all__ = ["suppress_metar_parser_warning", "MetarManager"]


def suppress_metar_parser_warning() -> None:
    """Suppress metar parser's warnings."""
    filterwarnings("ignore", category=RuntimeWarning, module="metar.Metar")


class MetarManager:
    """The PyFSD metar manager.

    Note:
        Mode explain:
        cron: Fetch all airports' metar (cached).
        once: Fetch specified airport's metar.

    Attributes:
        fetchers: All fetchers.
        metar_cache: Metars fetched in cron mode.
        config: pyfsd.metar section of config.
        cron_time: Interval time between every two cron fetch. None if not in cron mode.
    """

    fetchers: Tuple[MetarFetcher, ...]
    metar_cache: MetarInfoDict
    config: dict
    cron_time: Optional[float]
    cron_task: "Task[NoReturn] | None"

    def __init__(self, config: dict) -> None:
        """Create a MetarManager instance.

        Args:
            config: pyfsd.metar section of config.
        """
        self.cron_time = config["cron_time"] if config["mode"] == "cron" else None
        self.cron_task = None
        self.config = config
        self.metar_cache = {}
        self.pick_fetchers(config["fetchers"])

    def pick_fetchers(self, enabled_fetchers: Iterable[str]) -> int:
        """Try to pick all specified metar fetchers according config.

        Args:
            enabled_fetchers: Fetchers(name) to be load.

        Returns:
            How much fetchers were loaded.
        """
        count = 1
        temp_fetchers: Dict[str, MetarFetcher] = {
            NOAAMetarFetcher.metar_source: NOAAMetarFetcher()
        }
        fetchers: List[MetarFetcher] = []
        for fetcher in iter_submodule_plugins(
            plugins,
            MetarFetcher,  # type: ignore[type-abstract]
            error_handler=logger.exception,
        ):
            count += 1
            temp_fetchers[fetcher.metar_source] = fetcher
        for need_fetcher in enabled_fetchers:
            if need_fetcher not in temp_fetchers:
                logger.error(f"No such METAR fetcher: {need_fetcher}")
            else:
                fetchers.append(temp_fetchers[need_fetcher])
        self.fetchers = tuple(fetchers)
        return count

    async def cache_metar(self) -> None:
        """Perform a cron fetch.

        Raises:
            RuntimeError: if not in cron mode.
        """
        logger.info("Fetching METAR")

        for fetcher in self.fetchers:
            try:
                metars = await fetcher.fetch_all(self.config)
            except NotImplementedError:
                continue
            else:
                if metars is not None:
                    logger.info(f"Fetched {len(metars)} metars.")
                    self.metar_cache = metars
                    return
                continue
        logger.error("No metar was fetched. All metar fetcher failed.")

    def get_cron_task(self) -> "Task[NoReturn]":
        """Get cron fetching task.

        Raises:
            RuntimeError: if not in cron mode.
        """
        if self.cron_time is None:
            raise RuntimeError("Not in cron mode")
        if self.cron_task is not None:
            return self.cron_task

        async def runner() -> NoReturn:
            if self.cron_time is None:
                raise RuntimeError("***BUG cron_time become None")
            while True:
                await self.cache_metar()
                await asleep(self.cron_time)

        self.cron_task = create_task(runner(), name="cron_metar_fetcher")
        return self.cron_task

    async def fetch_once(
        self,
        icao: str,
        ignored_sources: Iterable[str] = (),
        ignore_case: bool = True,
    ) -> "Metar | None":
        """Try to fetch metar from fetchers by MetarFetcher.fetch.

        Args:
            icao: ICAO of the airport.
            ignored_sources: Ignored metar sources, won't be used in this fetch.
            ignore_case: Ignore ICAO case.

        Returns:
            The parsed Metar or None if nothing fetched.
        """
        ignored_sources_tuple = tuple(ignored_sources)
        if ignore_case:
            icao = icao.upper()

        for fetcher in self.fetchers:
            if fetcher.metar_source in ignored_sources_tuple:
                continue
            try:
                metar = await fetcher.fetch(self.config, icao)
                if metar is not None:
                    return metar
            except NotImplementedError:
                continue
        return None

    async def fetch(self, icao: str, ignore_case: bool = True) -> Optional["Metar"]:
        """Try to fetch metar.

        If in cron mode, we'll try to get metar from cron cache.
        If specified airport not found in cache and config['fallback_once'],
        we'll try to fetch by MetarFetcher.fetch.

        Args:
            icao: ICAO of the airport.
            ignore_case: Ignore ICAO case.
        """
        if ignore_case:
            icao = icao.upper()

        fallback_once = self.config.get("fallback_once", None)

        if self.cron_time is not None:
            if icao in self.metar_cache:
                return self.metar_cache[icao]
            if fallback_once:
                # Already uppercased
                return await self.fetch_once(icao, ignore_case=False)
            return None
        return await self.fetch_once(icao, ignore_case=False)
