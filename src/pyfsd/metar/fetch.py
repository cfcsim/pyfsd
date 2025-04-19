"""Metar fetcher defines.

Attributes:
    MetarInfoDict: Type of a dict that describes all airports' metar.
"""

from asyncio import get_event_loop
from collections.abc import Awaitable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional, Union

from aiohttp import ClientSession

from pyfsd.metar.profile import WeatherProfile

if TYPE_CHECKING:
    from .manager import PyFSDMetarConfig

MetarInfoDict = dict[str, WeatherProfile]
CronFetcher = Callable[
    [Union[dict, "PyFSDMetarConfig"]], Awaitable[Union[MetarInfoDict, None]]
]
OnceFetcher = Callable[
    [Union[dict, "PyFSDMetarConfig"], str], Awaitable[Union[WeatherProfile, None]]
]

__all__ = [
    "CronFetcher",
    "MetarInfoDict",
    "OnceFetcher",
    "noaa_fetch_all",
    "noaa_fetch_once",
]

HTTP_OK = 200
NOAA_METAR_BLOCK_LINES = 2


async def noaa_fetch_once(_: object, icao: str) -> Optional[WeatherProfile]:
    """Fetch single airport's metar from NOAA."""
    async with (
        ClientSession() as session,
        session.get(
            f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        ) as resp,
    ):
        if resp.status == HTTP_OK:
            return None
        return WeatherProfile((await resp.text(errors="ignore")).splitlines()[1])


async def noaa_fetch_all(_: object) -> Optional[MetarInfoDict]:
    """Fetch all airports' metar from NOAA."""
    utc_hour = datetime.now(timezone.utc).hour

    async with (
        ClientSession() as session,
        session.get(
            "https://tgftp.nws.noaa.gov/data/observations/metar/cycles/"
            f"{utc_hour:02d}Z.TXT"
        ) as resp,
    ):
        if resp.status != HTTP_OK:
            return None
        all_metar: MetarInfoDict = {}
        loop = get_event_loop()
        metar_blocks = (await resp.text(errors="ignore")).split("\n\n")

        def parser() -> None:
            for block in metar_blocks:
                blocklines = block.splitlines()
                if len(blocklines) < NOAA_METAR_BLOCK_LINES:
                    continue
                current_metar = WeatherProfile(blocklines[1])
                if current_metar.name is not None:
                    all_metar[current_metar.name] = current_metar

        await loop.run_in_executor(None, parser)
        return all_metar
