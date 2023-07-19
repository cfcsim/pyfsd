"""Python implemented fsd/wprofile
May delete later. """

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import fabs, pi, sin
from typing import TYPE_CHECKING, Optional, Tuple

from ..define.simulation import Int32MRand

if TYPE_CHECKING:
    from metar.Metar import Metar

    from ..object.client import Position

last_update_variation_hour = -1
variation = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
mrand = Int32MRand()

VAR_UPDIRECTION = 0
VAR_MIDCOR = 1
VAR_LOWCOR = 2
VAR_MIDDIRECTION = 3
VAR_MIDSPEED = 4
VAR_LOWDIRECTION = 5
VAR_LOWSPEED = 6
VAR_UPTEMP = 7
VAR_MIDTEMP = 8
VAR_LOWTEMP = 9


def updateVariationIfOutdated() -> bool:
    global variation

    now = datetime.now(timezone.utc)
    if now.hour - last_update_variation_hour > 0:
        mrand.srand(now.hour * (now.year - 1900) * now.month)
        variation = (
            mrand(),
            mrand(),
            mrand(),
            mrand(),
            mrand(),
            mrand(),
            mrand(),
            mrand(),
            mrand(),
            mrand(),
        )
        return True
    return False


def getVariation(num: int, min_: int, max_: int) -> int:
    return (abs(variation[num]) % (max_ - min_ + 1)) + min_


def getSeason(month: int, swap: bool) -> int:
    if month in [11, 0, 1]:
        return 2 if swap else 0
    elif month in [2, 3, 4]:
        return 1
    elif month in [5, 6, 7]:
        return 0 if swap else 2
    elif month in [8, 9, 10]:
        return 1
    else:
        raise ValueError(f"Invaild month {month}")


@dataclass
class CloudLayer:
    ceiling: int
    floor: int
    coverage: int = 0
    icing: int = 0
    turbulence: int = 0


@dataclass
class WindLayer:
    ceiling: int
    floor: int
    direction: int = 0
    speed: int = 0
    gusting: int = 0
    turbulence: int = 0


@dataclass
class TempLayer:
    ceiling: int
    temp: int = 0


@dataclass
class WeatherProfile:
    creation: int
    origin: Optional[str]
    metar: "Metar"
    name: Optional[str] = None
    raw_code: Optional[str] = None
    season: int = 0
    active: bool = False
    dew_point: int = 0
    visibility: float = 15.0
    barometer: int = 2950
    winds: Tuple[WindLayer, WindLayer, WindLayer, WindLayer] = field(
        default_factory=lambda: (
            WindLayer(-1, -1),
            WindLayer(10400, 2500),
            WindLayer(22600, 10400),
            WindLayer(90000, 20700),
        )
    )
    temps: Tuple[TempLayer, TempLayer, TempLayer, TempLayer] = field(
        default_factory=lambda: (
            TempLayer(100),
            TempLayer(10000),
            TempLayer(18000),
            TempLayer(35000),
        )
    )
    clouds: Tuple[CloudLayer, CloudLayer] = field(
        default_factory=lambda: (CloudLayer(-1, -1), CloudLayer(-1, -1))
    )
    tstorm: CloudLayer = field(default_factory=lambda: CloudLayer(-1, -1))

    def __post_init__(self) -> None:
        if self.metar.station_id is not None:
            self.name = self.metar.station_id
        self.feedMetar(self.metar)

    def activate(self) -> None:
        self.active = True

    def feedMetar(self, metar: "Metar") -> None:
        """Warning: Lots of unreadable code"""
        # Wind
        if metar.wind_speed is not None and metar.wind_dir is not None:
            if metar.wind_gust is not None:
                self.winds[0].gusting = 1
            self.winds[0].speed = int(metar.wind_speed.value())
            self.winds[0].ceiling = 2500
            self.winds[0].floor = 0
            self.winds[0].direction = int(metar.wind_dir.value())
        # Visibility
        if metar.vis is not None:
            vis = metar.vis.value("M")
            if vis == 10000:
                self.visibility = 15
                if "9999" not in metar.code:
                    self.clouds[1].ceiling = 26000
                    self.clouds[1].floor = 24000
                    self.clouds[1].icing = 0
                    self.clouds[1].turbulence = 0
                    self.clouds[1].coverage = 1
            elif "M1/4SM" in metar.code:
                self.visibility = 0.15
            else:
                self.visibility = metar.vis.value("MI")
        # Runway visual range: nothing
        # Weather: nothing
        # Sky
        sky_coverage = {
            "SKC": 0,
            "CLR": 0,
            "VV": 8,
            "FEW": 1,
            "SCT": 3,
            "BKN": 5,
            "OVC": 8,
        }
        for i, sky in enumerate(metar.sky[:2]):
            sky_status, distance, _ = sky
            try:
                self.clouds[i].coverage = sky_coverage[sky_status]
            except KeyError:
                pass
            if distance is not None:
                self.clouds[i].floor = int(distance.value())
        if len(metar.sky) >= 2:
            if self.clouds[1].floor > self.clouds[0].floor:
                self.clouds[0].ceiling = (
                    self.clouds[0].floor
                    + (self.clouds[1].floor - self.clouds[0].floor) // 2
                )
                self.clouds[1].ceiling = self.clouds[1].floor + 3000
            else:
                self.clouds[1].ceiling = (
                    self.clouds[1].floor
                    + (self.clouds[0].floor - self.clouds[1].floor) // 2
                )
                self.clouds[0].ceiling = self.clouds[0].floor + 3000
            self.clouds[0].turbulence = (
                self.clouds[0].ceiling - self.clouds[0].floor
            ) // 175
            self.clouds[1].turbulence = (
                self.clouds[1].ceiling - self.clouds[1].floor
            ) // 175
        elif len(metar.sky) == 1:
            self.clouds[0].ceiling = self.clouds[0].floor + 3000
            self.clouds[0].turbulence = 17
        # Temp
        if metar.temp is not None and metar.dewpt is not None:
            temp: int = int(metar.temp.value())
            self.temps[0].temp = temp
            self.dew_point = int(metar.dewpt.value())
            if -10 < temp < 10:
                if self.clouds[0].ceiling < 12000:
                    self.clouds[0].icing = 1
                if self.clouds[1].ceiling < 12000:
                    self.clouds[1].icing = 1
        # Barometer
        if metar.press is not None:
            self.barometer = round(metar.press.value("IN") * 100)
        else:
            self.barometer = 2992
        # Visibility fix: nothing

    def fix(self, position: "Position") -> None:
        a1 = position[0]
        a2 = fabs(position[1] / 18)
        season = getSeason(int(a1), a1 < 0)
        updateVariationIfOutdated()
        lat_var = getVariation(VAR_UPDIRECTION, -25, 25)
        self.winds[3].direction = round(6 if a1 > 0 else -6 * a1 + lat_var + a2)
        self.winds[3].direction = (self.winds[3].direction + 360) % 360

        max_velocity = 0
        if season == 0:
            max_velocity = 120
        elif season == 1:
            max_velocity = 80
        elif season == 2:
            max_velocity = 50

        self.winds[3].speed = round(fabs(sin(a1 * pi / 180.0)) * max_velocity)
        # ------
        lat_var = getVariation(VAR_MIDDIRECTION, 10, 45)
        coriolis_var = getVariation(VAR_MIDCOR, 10, 30)
        self.winds[2].direction = round(
            6 if a1 > 0 else -6 * a1 + lat_var + a2 - coriolis_var
        )
        self.winds[2].direction = (self.winds[2].direction + 360) % 360

        self.winds[2].speed = int(
            (self.winds[3].speed * (getVariation(VAR_MIDSPEED, 500, 800) / 1000.0))
        )
        # ------
        coriolis_var_low = coriolis_var + getVariation(VAR_LOWCOR, 10, 30)
        lat_var = getVariation(VAR_LOWDIRECTION, 10, 45)
        self.winds[1].direction = round(
            6 if a1 > 0 else -6 * a1 + lat_var + a2 - coriolis_var_low
        )
        self.winds[1].direction = (self.winds[1].direction + 360) % 360

        self.winds[1].speed = (self.winds[0].speed + self.winds[1].speed) // 2
        # ------
        self.temps[3].temp = -57 + getVariation(VAR_UPTEMP, -4, 4)
        self.temps[2].temp = -21 + getVariation(VAR_MIDTEMP, -7, 7)
        self.temps[1].temp = -5 + getVariation(VAR_LOWTEMP, -12, 12)
