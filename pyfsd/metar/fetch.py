from datetime import datetime, timezone
from typing import Dict, List, Optional, cast
from urllib.error import ContentTooShortError, HTTPError, URLError
from urllib.request import urlopen

from chardet import detect
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
    name = Attribute("Name of fetcher")

    def fetch(icao: str) -> Optional[Metar]:
        """Fetch the METAR of the specified airport."""
        pass

    def fetchAll() -> MetarInfoDict:
        """Fetch METAR for all airports."""
        pass


@implementer(IMetarFetcher)
class NOAAMetarFetcher:
    name = "NOAA"

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

    def fetch(self, icao: str) -> Optional[Metar]:
        try:
            with urlopen(
                "https://tgftp.nws.noaa.gov/data/observations/metar/stations/"
                f"{icao}.TXT"
            ) as metar_file:
                try:
                    metar_str = metar_file.read().decode().splitlines()
                except UnicodeDecodeError:
                    return None
                return self.parseMetar(metar_str)
        except ContentTooShortError or HTTPError or URLError:
            return None

    def fetchAll(self) -> MetarInfoDict:
        all_metar: MetarInfoDict = {}
        utc_hour = datetime.now(timezone.utc).hour
        try:
            with urlopen(
                "https://tgftp.nws.noaa.gov/data/observations/metar/cycles/"
                f"{utc_hour:02d}Z.TXT"
            ) as metar_file:
                content = metar_file.read()
                try:
                    metar_blocks = content.decode().split("\n\n")
                except UnicodeDecodeError as err:
                    print(UnicodeDecodeError.__name__ + ":", str(err))
                    print(detect(content))
                    with open("err_metar.txt", "wb") as ef:
                        ef.write(content)
                    raise MetarNotAvailableError
                for block in metar_blocks:
                    blocklines = block.splitlines()
                    if len(blocklines) < 2:
                        continue
                    current_metar = self.parseMetar(blocklines)
                    all_metar[cast(str, current_metar.station_id)] = current_metar
        except ContentTooShortError or HTTPError or URLError:
            raise MetarNotAvailableError
        return all_metar
