from html.parser import HTMLParser
from typing import NoReturn, Optional
from urllib.error import ContentTooShortError, HTTPError, URLError
from urllib.request import urlopen

from metar.Metar import Metar
from twisted.plugin import IPlugin
from zope.interface import implementer

from ..metar.fetch import IMetarFetcher


class MetarPageParser(HTMLParser):
    metar_text: Optional[str] = None

    def handle_data(self, data: str) -> None:
        if self.lasttag == "code":
            self.metar_text = data


@implementer(IPlugin, IMetarFetcher)
class AWCMetarFetcher:
    name = "aviationweather"

    def fetch(self, icao: str) -> Optional[Metar]:
        try:
            with urlopen(
                f"https://aviationweather.gov/metar/data?ids={icao}"
                "&format=raw&date=0&hours=0"
            ) as html_file:
                parser = MetarPageParser()
                parser.feed(html_file.read().decode())
                if parser.metar_text is None:
                    return None
                else:
                    return Metar(parser.metar_text, strict=False)
        except ContentTooShortError or HTTPError or URLError:
            return None

    def fetchAll(self) -> NoReturn:
        raise NotImplementedError


fetcher = AWCMetarFetcher()
