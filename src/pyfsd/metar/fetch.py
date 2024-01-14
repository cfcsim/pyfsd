from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

from metar.Metar import Metar
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.web.client import Agent, readBody
from zope.interface import Attribute, Interface, implementer

from ..define.utils import QuietHTTPConnectionPool

if TYPE_CHECKING:
    from twisted.web.client import Response

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

    def fetch(config: dict, icao: str) -> Deferred[Optional[Metar]]:
        """Fetch the METAR of the specified airport.

        Args:
            config: pyfsd.metar section of PyFSD configure file.
            icao: The ICAO of the airport.

        Returns:
            The METAR of the specified airport.
        """

    def fetchAll(config: dict) -> Deferred[MetarInfoDict]:
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
    agent = Agent(reactor, pool=QuietHTTPConnectionPool(reactor))

    @staticmethod
    def parseMetar(metar_lines: List[str]) -> Metar:
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

    def fetch(self, _: dict, icao: str) -> Deferred[Optional[Metar]]:
        metar_deferred: Deferred[Optional[Metar]] = Deferred()

        def parse(data: bytes, response: "Response") -> None:
            if response.code != 200:
                metar_deferred.errback(None)
            else:
                metar_deferred.callback(
                    self.parseMetar(
                        data.decode("ascii", "backslashreplace").splitlines(),
                    ),
                )

        self.agent.request(
            b"GET",
            b"https://tgftp.nws.noaa.gov/data/observations/metar/stations/%s.TXT"
            % icao.encode(),
        ).addCallback(
            lambda request: readBody(request).addCallback(parse, request),
        ).addErrback(lambda _: metar_deferred.callback(None))

        return metar_deferred

    def fetchAll(self, _: dict) -> Deferred[MetarInfoDict]:
        utc_hour = datetime.now(timezone.utc).hour
        metar_deferred: Deferred[MetarInfoDict] = Deferred()

        def parse(data: bytes, response: "Response") -> None:
            if response.code != 200:
                metar_deferred.errback(MetarNotAvailableError())
                return
            all_metar: MetarInfoDict = {}
            metar_blocks = data.decode("ascii", "backslashreplace").split("\n\n")
            for block in metar_blocks:
                blocklines = block.splitlines()
                if len(blocklines) < 2:
                    continue
                current_metar = self.parseMetar(blocklines)
                if current_metar.station_id is not None:
                    all_metar[current_metar.station_id] = current_metar
            metar_deferred.callback(all_metar)

        self.agent.request(
            b"GET",
            b"https://tgftp.nws.noaa.gov/data/observations/metar/cycles/%02dZ.TXT"
            % utc_hour,
        ).addCallback(
            lambda response: readBody(response).addCallback(parse, response),
        ).addErrback(lambda _: metar_deferred.errback(MetarNotAvailableError()))
        return metar_deferred
