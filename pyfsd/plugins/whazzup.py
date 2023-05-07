from datetime import datetime
from typing import TYPE_CHECKING, Optional

from twisted.plugin import IPlugin
from zope.interface import implementer

from ..plugin import BasePyFSDPlugin

if TYPE_CHECKING:
    from ..service import PyFSDService


@implementer(IPlugin)
class WhazzupGenerator(BasePyFSDPlugin):
    # Most whazzup ver.3 (vatsim)
    pyfsd: Optional["PyFSDService"] = None

    def beforeStart(self, pyfsd: "PyFSDService") -> None:
        self.pyfsd = pyfsd

    def generateWhazzup(self) -> dict:
        assert self.pyfsd is not None, "PyFSD not started."
        assert self.pyfsd.client_factory is not None, "Client factory not started."
        whazzup = {"pilot": [], "controllers": []}
        utc_now = datetime.utcnow()
        whazzup["general"] = {
            "version": 3,
            "reload": 1,
            "update": utc_now.strftime("%Y%m%d%H%M%S"),
            "update_timestamp": utc_now.strftime("%Y-%m-%dT%H:%M:%S.%f0Z"),
        }
        for client in self.pyfsd.client_factory.clients.values():
            client_info = {
                "cid": client.cid,
                "name": client.realname,
                "callsign": client.callsign,
                "logon_time": datetime.fromtimestamp(client.start_time).strftime(
                    "%Y-%m-%dT%H:%M:%S.%f0Z"
                ),
                "rating": client.rating,
                "last_updated": client.last_updated,
            }
            if client.position_ok:
                lat, lon = client.position
                client_info["latitude"] = lat
                client_info["longitude"] = lon
                if client.type == "PILOT":
                    client_info["altitude"] = client.altitude
                    client_info["pbh"] = client.pbh

            if client.type == "PILOT":
                client_info["groundspeed"] = client.ground_speed
                client_info["transponder"] = f"{client.transponder:04d}"

            whazzup["pilot" if client.type == "PILOT" else "controllers"].append(
                client_info
            )
