"""Python implemented fsd/wprofile.

Note:
    I don't know what variation means, it was copied from FSD.

Attributes:
    last_update_variation_hour: Last hour that we updated variation.
    variation: ?
    VAR_*: ?
    mrand: Basically a random number generator, used to compatible with FSD's.
"""

import contextlib
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


def check_variation() -> bool:
    """Check and update variation if it's outdated.

    Returns:
        Updated variation or not.
    """
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


def get_variation(num: int, min_: int, max_: int) -> int:
    """Get variation."""
    return (abs(variation[num]) % (max_ - min_ + 1)) + min_


def get_season(month: int, swap: bool) -> int:
    """Get season by month.

    Args:
        month: The month.
        swap: Swap spring and autumn or not.

    Returns:
        season: The season. Note it starts from 0.
    """
    if month in [12, 1, 2]:
        return 2 if swap else 0
    if month in [3, 4, 5]:
        return 1
    if month in [6, 7, 8]:
        return 0 if swap else 2
    if month in [9, 10, 11]:
        return 1
    raise ValueError(f"Invaild month {month}")


@dataclass
class CloudLayer:
    """This dataclass describes a cloud layer."""

    ceiling: int
    floor: int
    coverage: int = 0
    icing: int = 0
    turbulence: int = 0


@dataclass
class WindLayer:
    """This dataclass describes a wind layer.

    Attributes:
        gusting: The wind is gusting or not.
        speed: Windspeed.
        direction: Direction of the wind.
    """

    ceiling: int
    floor: int
    direction: int = 0
    speed: int = 0
    gusting: int = 0
    turbulence: int = 0


@dataclass
class TempLayer:
    """This dataclass describes a temperature layer.

    Attributes:
        temp: The temperature.
    """

    ceiling: int
    temp: int = 0


@dataclass
class WeatherProfile:
    """Profile of weather.

    Attributes:
        creation: Create time of the profile.
        origin: The profile's source, used in multi-server
        metar: The parsed metar.
        name: Metar station.
        season: Season of the metar's time.
        active: The profile is activate or not.
        dew_point: Dew point.
        visibility: Visibility, in MI (maybe)
        barometer: Barometer.
    """

    creation: int
    origin: Optional[str]
    metar: "Metar"
    name: Optional[str] = None
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
        ),
    )
    temps: Tuple[TempLayer, TempLayer, TempLayer, TempLayer] = field(
        default_factory=lambda: (
            TempLayer(100),
            TempLayer(10000),
            TempLayer(18000),
            TempLayer(35000),
        ),
    )
    clouds: Tuple[CloudLayer, CloudLayer] = field(
        default_factory=lambda: (CloudLayer(-1, -1), CloudLayer(-1, -1)),
    )
    tstorm: CloudLayer = field(default_factory=lambda: CloudLayer(-1, -1))

    def __post_init__(self) -> None:
        """Initialize this dataclass from metar."""
        if self.metar.station_id is not None:
            self.name = self.metar.station_id
        self.feed_metar(self.metar)

    def feed_metar(self, metar: "Metar") -> None:
        """Parse metar.

        Note:
            I don't know what does ceiling or floor stands for,
            these code are heavily based on FSD.
        """
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
            with contextlib.suppress(KeyError):
                self.clouds[i].coverage = sky_coverage[sky_status]
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
        """Fix this profile at a point."""
        a1 = position[0]
        a2 = fabs(position[1] / 18)
        season = get_season(datetime.now().month, a1 < 0)
        check_variation()
        lat_var = get_variation(VAR_UPDIRECTION, -25, 25)
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
        lat_var = get_variation(VAR_MIDDIRECTION, 10, 45)
        coriolis_var = get_variation(VAR_MIDCOR, 10, 30)
        self.winds[2].direction = round(
            6 if a1 > 0 else -6 * a1 + lat_var + a2 - coriolis_var,
        )
        self.winds[2].direction = (self.winds[2].direction + 360) % 360

        self.winds[2].speed = int(
            self.winds[3].speed * (get_variation(VAR_MIDSPEED, 500, 800) / 1000.0),
        )
        # ------
        coriolis_var_low = coriolis_var + get_variation(VAR_LOWCOR, 10, 30)
        lat_var = get_variation(VAR_LOWDIRECTION, 10, 45)
        self.winds[1].direction = round(
            6 if a1 > 0 else -6 * a1 + lat_var + a2 - coriolis_var_low,
        )
        self.winds[1].direction = (self.winds[1].direction + 360) % 360

        self.winds[1].speed = (self.winds[0].speed + self.winds[1].speed) // 2
        # ------
        self.temps[3].temp = -57 + get_variation(VAR_UPTEMP, -4, 4)
        self.temps[2].temp = -21 + get_variation(VAR_MIDTEMP, -7, 7)
        self.temps[1].temp = -5 + get_variation(VAR_LOWTEMP, -12, 12)
