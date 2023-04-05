from typing import TYPE_CHECKING, Iterable, Optional

from twisted.application.service import Service
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread

from .manager import MetarManager

if TYPE_CHECKING:
    from metar.Metar import Metar


class MetarService(Service):
    metar_manager: MetarManager

    def __init__(
        self, cron_time: Optional[float], enabled_fetchers: Iterable[str]
    ) -> None:
        self.metar_manager = MetarManager(cron_time, enabled_fetchers)

    def startService(self):
        if self.metar_manager.cron:
            self.metar_manager.startCache(in_thread=True)
        super().startService()

    def query(self, icao: str) -> Deferred[Optional["Metar"]]:
        if self.metar_manager.cron:
            return Deferred().callback(self.metar_manager.query(icao))
        else:
            return deferToThread(self.metar_manager.query, icao)
