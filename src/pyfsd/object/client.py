"""Client object's dataclasses."""
from dataclasses import dataclass, field
from math import sqrt
from time import time
from typing import TYPE_CHECKING, Literal, Optional, Tuple

if TYPE_CHECKING:
    from asyncio import Transport

__all__ = ["Position", "FlightPlan", "Client", "ClientType"]

Position = Tuple[float, float]
ClientType = Literal["ATC", "PILOT"]


@dataclass
class FlightPlan:
    """This dataclass describes a flight plan.

    Attributes:
      type: b"I" => IFR, b"V" => VFR
    """

    revision: int
    type: bytes  # noqa: A003
    aircraft: bytes
    tascruise: int
    dep_airport: bytes
    dep_time: int
    act_dep_time: int
    alt: bytes
    dest_airport: bytes
    hrs_enroute: int
    min_enroute: int
    hrs_fuel: int
    min_fuel: int
    alt_airport: bytes
    remarks: bytes
    route: bytes


@dataclass
class Client:
    """This dataclass stores a client."""

    type: ClientType  # noqa: A003
    callsign: bytes
    rating: int
    cid: str
    protocol: int
    realname: bytes
    sim_type: int
    transport: "Transport"
    position: Position = (0, 0)
    transponder: int = 0
    altitude: int = 0
    ground_speed: int = 0
    frequency: int = 0
    facility_type: int = 0
    visual_range: int = 40
    flags: int = 0
    pbh: int = 0
    flight_plan: Optional[FlightPlan] = None
    sector: Optional[bytes] = None
    ident_flag: Optional[bytes] = None
    start_time: int = field(default_factory=lambda: int(time()))
    last_updated: int = field(default_factory=lambda: int(time()))

    @property
    def position_ok(self) -> bool:
        """The position is vaild or not."""
        return self.position != (0, 0) and self.altitude < 100000

    @property
    def frequency_ok(self) -> bool:
        """The frequency is vaild or not."""
        return self.frequency != 0 and self.frequency < 100000

    def update_plan(
        self,
        plan_type: bytes,
        aircraft: bytes,
        tascruise: int,
        dep_airport: bytes,
        dep_time: int,
        act_dep_time: int,
        alt: bytes,
        dest_airport: bytes,
        hrs_enroute: int,
        min_enroute: int,
        hrs_fuel: int,
        min_fuel: int,
        alt_airport: bytes,
        remarks: bytes,
        route: bytes,
    ) -> int:
        """Update flight plan."""
        revision: int
        revision = self.flight_plan.revision + 1 if self.flight_plan is not None else 0
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
        return revision

    def update_pilot_position(
        self,
        mode: bytes,
        transponder: int,
        lat: float,
        lon: float,
        altitdue: int,
        groundspeed: int,
        pbh: int,
        flags: int,
    ) -> None:
        """Update pilot position."""
        self.ident_flag = mode
        self.transponder = transponder
        self.position = (lat, lon)
        self.altitude = altitdue
        self.ground_speed = groundspeed
        self.pbh = pbh
        self.flags = flags
        self.last_updated = int(time())

    def update_ATC_position(  # noqa: N802
        self,
        frequency: int,
        facility_type: int,
        visual_range: int,
        lat: float,
        lon: float,
        altitude: int,
    ) -> None:
        """Update ATC position."""
        self.frequency = frequency
        self.facility_type = facility_type
        self.visual_range = visual_range
        self.position = (lat, lon)
        self.altitude = altitude
        self.last_updated = int(time())

    def get_range(self) -> int:
        """Get visual range."""
        if self.type == "PILOT":
            altitude: int
            if self.altitude is None or self.altitude < 0:
                altitude = 0
            else:
                altitude = self.altitude
            return int(10 + 1.414 * sqrt(altitude))
        if self.facility_type == 2 or self.facility_type == 3:
            # CLR_DEL or GROUND
            return 5
        if self.facility_type == 4:
            # TOWER
            return 30
        if self.facility_type == 5:
            # APP/DEP
            return 100
        if self.facility_type == 6:
            # CENTER
            return 400
        if self.facility_type == 1 or self.facility_type == 7:
            # FSS or MONITOR
            return 1500
        # Unknown
        return 40
