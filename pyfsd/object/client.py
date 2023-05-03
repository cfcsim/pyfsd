from dataclasses import dataclass, field
from math import sqrt
from time import time
from typing import Literal, Optional, Tuple
from weakref import ReferenceType

from twisted.internet.interfaces import ITransport

__all__ = ["Position", "FlightPlan", "Client", "ClientType", "ClientInfo"]

Position = Tuple[float, float]
ClientType = Literal["ATC", "PILOT"]


@dataclass
class FlightPlan:
    revision: int
    type: Literal["I", "V"]
    aircraft: str
    tascruise: int
    dep_airport: str
    dep_time: int
    act_dep_time: int
    alt: str
    dest_airport: str
    hrs_enroute: int
    min_enroute: int
    hrs_fuel: int
    min_fuel: int
    alt_airport: str
    remarks: str
    route: str


@dataclass
class Client:
    type: ClientType
    callsign: str
    rating: int
    cid: str
    protocol: int
    realname: str
    sim_type: Optional[int]
    transport: ITransport
    position: Position = (0, 0)
    transponder: int = 0
    altitude: int = 0
    ground_speed: int = 0
    frequency: int = 0
    facility_type: int = 0
    visual_range: int = 40
    position_ok: bool = False
    flags: Optional[int] = None
    flight_plan: Optional[FlightPlan] = None
    pbh: Optional[int] = None
    sector: Optional[str] = None
    ident_flag: Optional[str] = None
    start_time: int = field(default_factory=lambda: int(time()))

    def updatePlan(
        self,
        plan_type: Literal["I", "V"],
        aircraft: str,
        tascruise: int,
        dep_airport: str,
        dep_time: int,
        act_dep_time: int,
        alt: str,
        dest_airport: str,
        hrs_enroute: int,
        min_enroute: int,
        hrs_fuel: int,
        min_fuel: int,
        alt_airport: str,
        remarks: str,
        route: str,
    ):
        revision: int
        if self.flight_plan is not None:
            revision = self.flight_plan.revision + 1
        else:
            revision = 0
        self.flight_plan = FlightPlan(
            revision,
            plan_type,
            aircraft,
            tascruise,
            dep_airport,
            dep_time,
            act_dep_time,
            alt,
            dest_airport,
            hrs_enroute,
            min_enroute,
            hrs_fuel,
            min_fuel,
            alt_airport,
            remarks,
            route,
        )

    def updatePilotPosition(
        self,
        mode: str,
        transponder: int,
        lat: float,
        lon: float,
        altitdue: int,
        groundspeed: int,
        pbh: int,
        flags: int,
    ) -> None:
        self.ident_flag = mode
        self.transponder = transponder
        self.position = (lat, lon)
        self.altitude = altitdue
        self.ground_speed = groundspeed
        self.pbh = pbh
        self.flags = flags
        self.position_ok = True

    def updateATCPosition(
        self,
        frequency: int,
        facility_type: int,
        visual_range: int,
        lat: float,
        lon: float,
        altitude: int,
    ) -> None:
        self.frequency = frequency
        self.facility_type = facility_type
        self.visual_range = visual_range
        self.position = (lat, lon)
        self.altitude = altitude
        self.position_ok = True

    def getRange(self) -> int:
        if self.type == "PILOT":
            altitude: int
            if self.altitude is None or self.altitude < 0:
                altitude = 0
            else:
                altitude = self.altitude
            return int(10 + 1.414 * sqrt(altitude))
        else:
            if self.facility_type == 2 or self.facility_type == 3:
                # CLR_DEL or GROUND
                return 5
            elif self.facility_type == 4:
                # TOWER
                return 30
            elif self.facility_type == 5:
                # APP/DEP
                return 100
            elif self.facility_type == 6:
                # CENTER
                return 400
            elif self.facility_type == 1 or self.facility_type == 7:
                # FSS or MONITOR
                return 1500
            else:
                # Unknown
                return 40


ClientInfo = Tuple[str, ReferenceType[Client]]
