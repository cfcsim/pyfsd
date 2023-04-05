from typing import TYPE_CHECKING, Callable, Optional

from twisted.application.internet import TCPServer
from twisted.application.service import Service

from .define.utils import verifyConfigStruct

# from .auth import CredentialsChecker, Realm
from .factory.client import FSDClientFactory
from .metar.service import MetarService

# from twisted.cred.portal import Portal
# from twisted.internet import reactor
# from twisted.internet.endpoints import TCP4ServerEndpoint


if TYPE_CHECKING:
    from metar.Metar import Metar


class PyFSDService(Service):
    client_factory: Optional[FSDClientFactory] = None
    fetch_metar: Callable[[str], Optional["Metar"]]
    config: dict

    def __init__(self, config: dict) -> None:
        self.config = config
        self.checkConfig()

    def checkConfig(self) -> None:
        verifyConfigStruct(
            self.config,
            {
                "pyfsd": {
                    "database_name": str,
                    "client": {"port": int, "motd": str, "blacklist": list},
                    "metar": {"mode": str, "fetchers": list},
                }
            },
        )
        if self.config["pyfsd"]["metar"]["mode"] == "cron":
            verifyConfigStruct(
                self.config["pyfsd"]["metar"], {"cron_time": int}, prefix="pyfsd.metar"
            )

    def getClientService(self) -> TCPServer:
        self.client_factory = FSDClientFactory(
            None,
            self.config["pyfsd"]["client"]["blacklist"],
            self.config["pyfsd"]["client"]["motd"].splitlines(),
        )
        return TCPServer(
            int(self.config["pyfsd"]["client"]["port"]), self.client_factory
        )

    def getMetarService(self) -> MetarService:
        metar_service = MetarService(
            self.config["pyfsd"]["metar"]["cron_time"]
            if self.config["pyfsd"]["metar"]["mode"] == "cron"
            else None,
            self.config["pyfsd"]["metar"]["fetchers"],
        )
        self.fetch_metar = metar_service.metar_manager.query
        return metar_service
