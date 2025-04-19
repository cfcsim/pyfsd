"""PyFSD metar manager.

See .MetarManager
"""

from asyncio import CancelledError, create_task
from asyncio import sleep as asleep
from typing import (
    TYPE_CHECKING,
    Literal,
    NoReturn,
    Optional,
    TypedDict,
    TypeVar,
    Union,
)
from warnings import filterwarnings

from structlog import get_logger
from typing_extensions import NotRequired

from pyfsd.define.check_dict import VerifyKeyError, VerifyTypeError

from .fetch import (
    CronFetcher,
    MetarInfoDict,
    OnceFetcher,
    noaa_fetch_all,
    noaa_fetch_once,
)

if TYPE_CHECKING:
    from asyncio import Task

    from .profile import WeatherProfile

logger = get_logger(__name__)
__all__ = ["MetarManager", "suppress_metar_parser_warning"]

CF = TypeVar("CF", bound=CronFetcher)
OF = TypeVar("OF", bound=OnceFetcher)


class PyFSDMetarConfig(TypedDict):
    """PyFSD metar config.

    Attributes:
        mode: Mode to fetch metar. once means fetch at once when client request metar, \
            cron means cache all airports' metar every specified interval.
        fallback_once: If specified airport not found in cron metar, fetch by once \
            or not. Will be ignored if not in cron mode.
        fetchers: Enabled metar fetchers.
        cron_time: The cron mode's specified interval. (see mode)
    """

    mode: Literal["cron", "once"]
    fallback_once: NotRequired[bool]
    fetchers: list
    cron_time: NotRequired[Union[float, int]]


def suppress_metar_parser_warning() -> None:
    """Suppress metar parser's warnings."""
    filterwarnings("ignore", category=RuntimeWarning, module="metar.Metar")


class MetarFetchers(TypedDict):
    """A dict that stores METAR fetchers."""

    cron: dict[str, CronFetcher]
    once: dict[str, OnceFetcher]


class MetarManager:
    """The PyFSD metar manager.

    Attributes:
        fetchers: All registered fetchers.
        used_fetchers: Fetchers that we're going to use.
        metar_cache: Metars fetched in cron mode.
        config: pyfsd.metar section of config.
        cron_time: Interval time between every two cron fetch. None if not in cron mode.
        cron_task: Task to perform cron metar cache.
    """

    fetchers: MetarFetchers
    used_fetchers: MetarFetchers
    metar_cache: MetarInfoDict
    config: Union[dict, PyFSDMetarConfig]
    cron_time: Optional[float]
    cron_task: Optional["Task[NoReturn]"]

    def __init__(self, config: Union[dict, PyFSDMetarConfig]) -> None:
        """Create a MetarManager instance.

        Args:
            config: pyfsd.metar section of config.
        """
        self.fetchers = {
            "cron": {"noaa": noaa_fetch_all},
            "once": {"noaa": noaa_fetch_once},
        }
        self.used_fetchers = {"cron": {}, "once": {}}
        self.cron_time = config.get("cron_time") if config["mode"] == "cron" else None
        self.cron_task = None
        self.config = config
        self.metar_cache = {}

    def register_cron_fetcher(self, name: str, fetcher: CF) -> CF:
        """Register a cron mode fetcher."""
        if name in self.fetchers["cron"]:
            raise RuntimeError(f"cron fetcher '{name}' already exists")
        self.fetchers["cron"][name] = fetcher
        return fetcher

    def register_once_fetcher(self, name: str, fetcher: OF) -> OF:
        """Register a once mode fetcher."""
        if name in self.fetchers["once"]:
            raise RuntimeError(f"once fetcher '{name}' already exists")
        self.fetchers["once"][name] = fetcher
        return fetcher

    def check_fetchers(self) -> None:
        """Check if all specified metar fetchers in config is already here."""
        used: MetarFetchers = {"cron": {}, "once": {}}
        is_once_mode = self.cron_time is None
        has_once_fallback = not is_once_mode and self.config.get("fallback_once", False)
        for need_fetcher in self.config["fetchers"]:
            found = 0
            # once only or cron with once fallback
            if (is_once_mode or has_once_fallback) and need_fetcher in self.fetchers["once"]:
                found += 1
                used["once"][need_fetcher] = self.fetchers["once"][need_fetcher]
            # cron
            if not is_once_mode and need_fetcher in self.fetchers["cron"]:
                found += 1
                used["cron"][need_fetcher] = self.fetchers["cron"][need_fetcher]
            if not found:
                logger.error("No such METAR fetcher: %s", need_fetcher)
        self.used_fetchers = used

    async def cache_metar(self) -> None:
        """Perform a cron fetch.

        Raises:
            RuntimeError: if not in cron mode.
        """
        await logger.ainfo("Fetching METAR")

        for name, fetcher in self.used_fetchers["cron"].items():
            try:
                metars = await fetcher(self.config)
            # ruff: noqa: PERF203
            except (VerifyKeyError, VerifyTypeError) as err:
                await logger.aerror(
                    f"Metar fetcher {name} doesn't work because {err!s}"
                )
            except CancelledError:
                raise
            # ruff: noqa: BLE001
            except BaseException:
                await logger.aexception("Exception raised when caching metar")
            else:
                if metars is not None:
                    await logger.ainfo(f"Fetched {len(metars)} metars.")
                    self.metar_cache = metars
                    return
                continue
        await logger.aerror("No metar was fetched. All metar fetcher failed.")

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
                raise RuntimeError("***BUG: cron_time is None")
            while True:
                await self.cache_metar()
                await asleep(self.cron_time)

        self.cron_task = create_task(runner(), name="cron_metar_fetcher")
        return self.cron_task

    async def fetch_once(
        self,
        icao: str,
        *,
        ignore_case: bool = True,
    ) -> "WeatherProfile | None":
        """Try to fetch metar from fetchers by MetarFetcher.fetch.

        Args:
            icao: ICAO of the airport.
            ignored_sources: Ignored metar sources, won't be used in this fetch.
            ignore_case: Ignore ICAO case.

        Returns:
            The parsed Metar or None if nothing fetched.
        """
        if ignore_case:
            icao = icao.upper()

        for name, fetcher in self.used_fetchers["once"].items():
            try:
                metar = await fetcher(self.config, icao)
                if metar is not None:
                    return metar
            except CancelledError:
                raise
            except (VerifyKeyError, VerifyTypeError) as err:
                await logger.aerror(
                    f"Metar fetcher {name} doesn't work because {err!s}"
                )
            except BaseException:
                await logger.aexception("Exception raised when fetching metar")
        return None

    async def fetch(
        self, icao: str, *, ignore_case: bool = True
    ) -> "WeatherProfile | None":
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
