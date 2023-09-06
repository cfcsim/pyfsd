from typing import TYPE_CHECKING, Optional

from twisted.application.service import Service
from twisted.internet.defer import Deferred, succeed
from twisted.internet.threads import deferToThread

from .manager import MetarManager

if TYPE_CHECKING:
    from metar.Metar import Metar


class MetarService(Service):
    metar_manager: MetarManager

    def __init__(self, config: dict) -> None:
        self.metar_manager = MetarManager(config)

    def startService(self) -> None:
        if self.metar_manager.cron:
            self.metar_manager.startCache()
        super().startService()

    def query(self, icao: str) -> Deferred[Optional["Metar"]]:
        return self.metar_manager.query(icao)
