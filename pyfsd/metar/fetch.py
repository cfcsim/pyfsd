from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.error import ContentTooShortError, HTTPError, URLError
from urllib.request import urlopen

from metar.Metar import Metar
from zope.interface import Attribute, Interface, implementer

MetarInfoDict = Dict[str, Metar]

__all__ = [
    "MetarInfoDict",
    "MetarNotAvailableError",
    "IMetarFetcher",
    "NOAAMetarFetcher",
]


class MetarNotAvailableError(Exception):
    """Raise when a metar fetcher cannot provide metar."""


class IMetarFetcher(Interface):
    """Metar fetcher.

    Attributes:
        metar_source: Name of the METAR source.
    """

    metar_source: str = Attribute("metar_source", "Name of this fetcher")

    def fetch(config: dict, icao: str) -> Optional[Metar]:
        """Fetch the METAR of the specified airport.

        Args:
            config: pyfsd.metar section of PyFSD configure file.
            icao: The ICAO of the airport.

        Returns:
            The METAR of the specified airport.
        """

    def fetchAll(config: dict) -> MetarInfoDict:
        """Fetch METAR for all airports.

        Args:
            config: pyfsd.metar section of PyFSD configure file.

        Returns:
            All METAR.

        Raises:
            MetarNotAvailableError: Metar not available.
        """


@implementer(IMetarFetcher)
class NOAAMetarFetcher:
    metar_source = "NOAA"

    @staticmethod
    def parseMetar(metar_lines: List[str]) -> Metar:
        try:
            metar_datetime = datetime.fromisoformat(metar_lines[0].replace("/", "-"))
        except ValueError:
            metar_datetime = datetime.utcnow()
        metar = Metar(
            metar_lines[1],
            strict=False,
            month=metar_datetime.month,
            year=metar_datetime.year,
        )
        return metar

    def fetch(self, _, icao: str) -> Optional[Metar]:
        try:
            with urlopen(
                "https://tgftp.nws.noaa.gov/data/observations/metar/stations/"
                f"{icao}.TXT"
            ) as metar_file:
                metar_str = (
                    metar_file.read().decode("ascii", "backslashreplace").splitlines()
                )
                return self.parseMetar(metar_str)
        except (ContentTooShortError, HTTPError, URLError):
            return None

    def fetchAll(self, _) -> MetarInfoDict:
        all_metar: MetarInfoDict = {}
        utc_hour = datetime.now(timezone.utc).hour
        try:
            with urlopen(
                "https://tgftp.nws.noaa.gov/data/observations/metar/cycles/"
                f"{utc_hour:02d}Z.TXT"
            ) as metar_file:
                content = metar_file.read()
                metar_blocks = content.decode("ascii", "backslashreplace").split("\n\n")
                for block in metar_blocks:
                    blocklines = block.splitlines()
                    if len(blocklines) < 2:
                        continue
                    current_metar = self.parseMetar(blocklines)
                    if current_metar.station_id is not None:
                        all_metar[current_metar.station_id] = current_metar
        except (ContentTooShortError, HTTPError, URLError):
            raise MetarNotAvailableError
        return all_metar
