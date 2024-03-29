"""Metar fetcher defines.

Attributes:
    MetarInfoDict: Type of a dict that describes all airports' metar.
"""
from abc import ABC, abstractmethod
from asyncio import get_event_loop
from datetime import datetime, timezone
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Union

from aiohttp import ClientSession
from metar.Metar import Metar

if TYPE_CHECKING:
    from .manager import PyFSDMetarConfig

MetarInfoDict = Dict[str, Metar]

__all__ = [
    "MetarInfoDict",
    "MetarFetcher",
    "NOAAMetarFetcher",
]


class MetarFetcher(ABC):
    """Metar fetcher.

    Attributes:
        metar_source: Name of the METAR source.
    """

    metar_source: ClassVar[str]

    @abstractmethod
    async def fetch(
        self, config: Union[dict, "PyFSDMetarConfig"], icao: str
    ) -> Optional[Metar]:
        """Fetch the METAR of the specified airport.

        Args:
            config: pyfsd.metar section of PyFSD configure file.
            icao: The ICAO of the airport.

        Returns:
            The METAR of the specified airport. None if fetch failed.

        Raises:
            NotImplemented: When fetch a single airport isn't supported.
        """

    @abstractmethod
    async def fetch_all(
        self, config: Union[dict, "PyFSDMetarConfig"]
    ) -> Optional[MetarInfoDict]:
        """Fetch METAR for all airports.

        Args:
            config: pyfsd.metar section of PyFSD configure file.

        Returns:
            All METAR. None if fetch failed.

        Raises:
            NotImplemented: When fetch all isn't supported.
        """


class NOAAMetarFetcher(MetarFetcher):
    """Fetch metar from NOAA (tgftp.nws.noaa.gov)."""

    metar_source = "NOAA"

    @staticmethod
    def parse_metar(metar_lines: List[str]) -> Metar:
        """Parse a metar block from NOAA.

        Args:
            metar_lines: Metar block, splitted into lines.

        Returns:
            The parsed metar.
        """
        try:
            metar_datetime = datetime.fromisoformat(metar_lines[0].replace("/", "-"))
        except ValueError:
            metar_datetime = datetime.utcnow()
        return Metar(
            metar_lines[1],
            strict=False,
            month=metar_datetime.month,
            year=metar_datetime.year,
        )

    async def fetch(self, config: object, icao: str) -> Optional[Metar]:
        """Fetch single airport's metar."""
        async with ClientSession() as session, session.get(
            f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        ) as resp:
            if resp.status != 200:
                return None
            return self.parse_metar((await resp.text(errors="ignore")).splitlines())

    async def fetch_all(self, config: object) -> Optional[MetarInfoDict]:
        """Fetch all airports' metar."""
        utc_hour = datetime.now(timezone.utc).hour

        async with ClientSession() as session, session.get(
            "https://tgftp.nws.noaa.gov/data/observations/metar/cycles/"
            f"{utc_hour:02d}Z.TXT"
        ) as resp:
            if resp.status != 200:
                return None
            all_metar: MetarInfoDict = {}
            loop = get_event_loop()
            metar_blocks = (await resp.text(errors="ignore")).split("\n\n")

            def parser() -> None:
                for block in metar_blocks:
                    blocklines = block.splitlines()
                    if len(blocklines) < 2:
                        continue
                    current_metar = self.parse_metar(blocklines)
                    if current_metar.station_id is not None:
                        all_metar[current_metar.station_id] = current_metar

            await loop.run_in_executor(None, parser)
            return all_metar
