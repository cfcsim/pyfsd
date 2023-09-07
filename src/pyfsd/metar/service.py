from typing import TYPE_CHECKING

from twisted.application.service import Service

from .manager import MetarManager

if TYPE_CHECKING:
    from metar.Metar import Metar
    from twisted.internet.defer import Deferred


class MetarService(Service):
    metar_manager: MetarManager

    def __init__(self, config: dict) -> None:
        self.metar_manager = MetarManager(config)

    def startService(self) -> None:
        if self.metar_manager.cron:
            self.metar_manager.startCache()
        super().startService()

    def query(self, icao: str) -> "Deferred[Metar | None]":
        return self.metar_manager.query(icao)
