# ruff: noqa: S101
"""PyFSD client protocol."""
from asyncio import CancelledError, create_task, Lock
from asyncio import sleep as asleep
from inspect import isawaitable
from time import time
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Callable,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from structlog import get_logger
from typing_extensions import Concatenate, ParamSpec

from .._version import version as pyfsd_version
from ..define.broadcast import (
    BroadcastChecker,
    all_ATC_checker,
    all_pilot_checker,
    at_checker,
    broadcast_message_checker,
    broadcast_position_checker,
    is_multicast,
)
from ..define.errors import FSDErrors
from ..define.packet import (
    CLIENT_USED_COMMAND,
    FSDClientCommand,
    break_packet,
    make_packet,
)
from ..define.utils import is_callsign_vaild, str_to_float, str_to_int, task_keeper
from ..metar.profile import WeatherProfile
from ..object.client import Client, ClientType
from . import LineProtocol

if TYPE_CHECKING:
    from asyncio import Task, Transport

    from ..factory.client import ClientFactory
    from ..plugin.types import PluginHandledEventResult, PyFSDHandledLineResult

logger = get_logger(__name__)
P = ParamSpec("P")
T = TypeVar("T")
HandleResult = Tuple[bool, bool]  # (packet_ok, has_result)

__all__ = ["ClientProtocol", "check_packet"]

version = pyfsd_version.encode("ascii")


_T_ClientProtocol = TypeVar("_T_ClientProtocol", bound="ClientProtocol")


# Notice: here comes a bunch of type annotation.
def check_packet(
    require_parts: int,
    callsign_position: int = 0,
    check_callsign: bool = True,
    need_login: bool = True,
) -> Callable[
    [
        Callable[
            Concatenate[_T_ClientProtocol, Tuple[bytes, ...], P],
            Union[Awaitable[HandleResult], HandleResult],
        ]
    ],
    Callable[
        Concatenate[_T_ClientProtocol, Tuple[bytes, ...], P], Awaitable[HandleResult]
    ],
]:
    """Create a decorator to auto check packet format and ensure awaitable.

    Designed for ClientProtocol's handlers.

    Args:
        require_parts: How many parts required.
            For example, #AA1012:gamecss:mentally broken
                         [0    ] [1    ] [2            ] => 3 parts
        callsign_position: Which part contains callsign, used when (need_login and
            check_callsign).
            For example, #AA1012:gamecss:mentally broken
                         [0, cs] [1    ] [2            ] => parts[0] contains callsign.
        need_login: Need self.client is not None (logined) or not.
        check_callsign: Check packet[callsign_position] == self.client.callsign or not.

    Example:
        @check_packet
    """

    def decorator(
        func: Callable[
            Concatenate[_T_ClientProtocol, Tuple[bytes, ...], P],
            Union[Awaitable[HandleResult], HandleResult],
        ],
    ) -> Callable[
        Concatenate[_T_ClientProtocol, Tuple[bytes, ...], P],
        Awaitable[HandleResult],
    ]:
        async def realfunc(
            self: _T_ClientProtocol,
            packet: Tuple[bytes, ...],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> HandleResult:
            if len(packet) < require_parts:
                self.send_error(FSDErrors.ERR_SYNTAX)
                return (False, False)
            if need_login:
                if self.client is None:
                    return (False, False)
                if check_callsign and self.client.callsign != packet[callsign_position]:
                    self.send_error(FSDErrors.ERR_SRCINVALID, env=packet[0])
                    return (False, False)
            result = func(self, packet, *args, **kwargs)
            if isawaitable(result):
                return await cast(Awaitable[HandleResult], result)
            return cast(HandleResult, result)

        return realfunc

    return decorator


class ClientProtocol(LineProtocol):
    """PyFSD client protocol.

    Attributes:
        factory: The client protocol factory.
        timeout_killer: Helper to disconnect when timeout.
        transport: Asyncio transport.
        client: The client info. None before `#AA` or `#AP` to create new client.
        tasks: Processing handle_line tasks.
    """

    factory: "ClientFactory"
    timeout_killer_task: "Task[None]"
    transport: "Transport"
    tasks: Set["Task"]
    client: Optional[Client]
    lock = Lock()

    def __init__(self, factory: "ClientFactory") -> None:
        """Create a ClientProtocol instance."""
        self.factory = factory
        self.tasks = set()
        self.client = None
        # timeout_killer_task and transport will be initialized in connection_made.

    def add_task(self, task: "Task") -> None:
        """Store a task's strong reference to keep it away from disappear."""
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def reset_timeout_killer(self) -> None:
        """Reset timeout killer."""

        async def timeout_killer() -> None:
            try:
                await asleep(800)
            except CancelledError:
                pass
            else:
                self.send_line(b"# Timeout")
                self.transport.close()

        if hasattr(self, "timeout_killer_task"):
            self.timeout_killer_task.cancel()
        self.timeout_killer_task = create_task(timeout_killer())

    def connection_made(self, transport: "Transport") -> None:  # type: ignore[override]
        """Initialize something after the connection is made."""
        super().connection_made(transport)
        ip = self.transport.get_extra_info("peername")[0]
        if ip in self.factory.blacklist:
            logger.info(f"Kicking {ip}")
            self.transport.close()
            return

        self.reset_timeout_killer()
        logger.info(f"New connection from {ip}.")
        task_keeper.add(
            create_task(
                self.factory.plugin_manager.trigger_event(
                    "new_connection_established", (self,), {}
                )
            )
        )

    def send_error(self, errno: int, env: bytes = b"", fatal: bool = False) -> None:
        """Send an error to client.

        $ERserver:(callsign):(errno):(env):error_text

        Args:
            errno: The error to be sent.
            env: The error env.
            fatal: Disconnect after the error is sent or not.
        """
        if errno < 0 or errno > 13:
            raise ValueError("Invaild errno")
        err_bytes = FSDErrors.error_names[errno].encode("ascii")
        self.send_lines(
            make_packet(
                FSDClientCommand.ERROR + b"server",
                self.client.callsign if self.client is not None else b"unknown",
                f"{errno:03d}".encode(),  # = str(errno).rjust(3, "0")
                env,
                err_bytes,
            ),
        )
        if fatal:
            self.transport.close()

    def send_motd(self) -> None:
        """Send motd to client."""
        if not self.client:
            raise RuntimeError("No client registered.")
        motd_lines: List[bytes] = [
            b"#TMserver:%s:PyFSD %s" % (self.client.callsign, version),
        ]
        for line in self.factory.motd:
            motd_lines.append(
                make_packet(
                    FSDClientCommand.MESSAGE + b"server",
                    self.client.callsign,
                    line,
                ),
            )
        self.send_lines(*motd_lines)

    def multicast(
        self,
        to_limiter: str,
        *lines: bytes,
        custom_at_checker: Optional[BroadcastChecker] = None,
    ) -> bool:
        """Multicast lines.

        Args:
            to_limiter: Dest limiter. * means every client, *A means every ATC,
                *P means every pilots, @ means in a range (see at_checker)
            lines: lines to be sent.
            custom_at_checker: Custom checker used when to_limiter is @.

        Returns:
            Lines sent to at least client or not.

        Raises:
            NotImplementedError: When an unsupported to_limiter specified.
        """
        if self.client is None:
            raise RuntimeError("No client registered.")
        if to_limiter == "*":
            # Default checker is lambda: True, so send to all client
            return self.factory.broadcast(*lines, from_client=self.client)
        if to_limiter == "*A":
            return self.factory.broadcast(
                *lines,
                check_func=all_ATC_checker,
                from_client=self.client,
            )
        if to_limiter == "*P":
            return self.factory.broadcast(
                *lines,
                check_func=all_pilot_checker,
                from_client=self.client,
            )
        if to_limiter.startswith("@"):
            return self.factory.broadcast(
                *lines,
                from_client=self.client,
                check_func=custom_at_checker
                if custom_at_checker is not None
                else at_checker,
            )
        raise NotImplementedError

    def handle_cast(
        self,
        packet: Tuple[bytes, ...],
        command: FSDClientCommand,
        require_parts: int = 2,
        multicast_able: bool = True,
        custom_at_checker: Optional[BroadcastChecker] = None,
    ) -> HandleResult:
        """Handle a (multi/uni)cast request.

        Args:
            packet: format: (command)(self_callsign):(to_callsign):(multicast content)
                Note that to_callsign could be multicast sign (*A, *P, etc.)
                if multicast_able.
            command: The packet's command.
            require_parts: How many parts required.
                For example, #AA1012:gamecss:happy lunar new year
                             [0    ] [1    ] [2                 ] => 3 parts
            multicast_able: to_callsign can be multicast sign or not.
                if not multicast_able and to_callsign is multicast sign, this function
                will send nothing and exit with False, False.
            custom_at_checker: Custom checker used when to_callsign is '@'.
        """
        # Check common things first
        packet_len: int = len(packet)
        if packet_len < require_parts:
            self.send_error(FSDErrors.ERR_SYNTAX)
            return False, False
        if self.client is None:
            return False, False
        if self.client.callsign != packet[0]:
            self.send_error(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return False, False

        to_callsign = packet[1]
        # We'll only check if it's a multicast sign, so decode is acceptable
        to_callsign_str = to_callsign.decode("ascii", "replace")
        # Prepare packet to be sent.
        to_packet = make_packet(
            command + self.client.callsign,
            to_callsign,
            *packet[2:] if packet_len > 2 else [b""],
        )

        if is_multicast(to_callsign_str):
            if multicast_able:
                return True, self.multicast(
                    to_callsign_str,
                    to_packet,
                    custom_at_checker=custom_at_checker,
                )
            # Not allowed to multicast, so packet_ok is False
            return False, False
        return True, self.factory.send_to(
            to_callsign,
            to_packet,
        )

    @check_packet(7, need_login=False)
    async def handle_add_client(
        self,
        packet: Tuple[bytes, ...],
        client_type: ClientType,
    ) -> HandleResult:
        """Handle add client request.

        Args:
            packet: The packet.
            client_type: Type of client, ATC or PILOT
        """
        if self.client is not None:
            self.send_error(FSDErrors.ERR_REGISTERED)
            return False, False
        if client_type == "PILOT":
            if len(packet) < 8:
                self.send_error(FSDErrors.ERR_SYNTAX)
                return False, False
            (
                callsign,
                _,
                cid,
                password,
                req_rating,
                protocol,
                sim_type,
                realname,
            ) = packet[:8]
            sim_type_int = str_to_int(sim_type, default_value=0)
        else:
            (
                callsign,
                _,
                realname,
                cid,
                password,
                req_rating,
                protocol,
            ) = packet[:7]
            sim_type_int = -1
        if len(req_rating) == 0:
            req_rating_int = 1
        else:
            req_rating_int = str_to_int(req_rating, default_value=0)
        protocol_int = str_to_int(protocol, default_value=-1)
        if not is_callsign_vaild(callsign):
            self.send_error(FSDErrors.ERR_CSINVALID, fatal=True)
            return False, False
        if protocol_int != 9:
            self.send_error(FSDErrors.ERR_REVISION, fatal=True)
            return False, False
        try:
            cid_str = cid.decode("utf-8")
            pwd_str = password.decode("utf-8")
        except UnicodeDecodeError:
            self.send_error(FSDErrors.ERR_CIDINVALID, env=cid, fatal=True)
            return False, False

        if callsign in self.factory.clients:
            self.send_error(FSDErrors.ERR_CSINUSE)
            return True, False

        rating = await self.factory.check_auth(cid_str, pwd_str)
        if rating is None:
            self.send_error(FSDErrors.ERR_CIDINVALID, env=cid, fatal=True)
            return True, False
        if rating == 0:
            self.send_error(FSDErrors.ERR_CSSUSPEND, fatal=True)
            return True, False
        if rating < req_rating_int:
            self.send_error(
                FSDErrors.ERR_LEVEL,
                env=req_rating,
                fatal=True,
            )
            return True, False
        client = Client(
            client_type,
            callsign,
            req_rating_int,
            cid_str,
            protocol_int,
            realname,
            sim_type_int,
            self.transport,
        )
        self.factory.clients[callsign] = client
        self.client = client
        if client_type == "PILOT":
            self.factory.broadcast(
                # two times of req_rating... FSD does :(
                make_packet(
                    FSDClientCommand.ADD_PILOT + callsign,
                    b"SERVER",
                    cid,
                    b"",
                    req_rating,
                    req_rating,
                    b"%d" % sim_type_int,
                ),
                from_client=client,
            )
        else:
            self.factory.broadcast(
                make_packet(
                    FSDClientCommand.ADD_ATC + callsign,
                    b"SERVER",
                    realname,
                    cid,
                    b"",
                    req_rating,
                ),
                from_client=client,
            )
        self.send_motd()
        await logger.ainfo(
            "New client %s (%s) from %s.",
            callsign.decode(errors="backslashreplace"),
            cid_str,
            self.transport.get_extra_info("peername")[0],
        )
        await self.factory.plugin_manager.trigger_event(
            "new_client_created", (self,), {}
        )
        return True, True

    @check_packet(1, check_callsign=False)
    def handle_remove_client(self, _: Tuple[bytes, ...]) -> HandleResult:
        """Handle remove client request."""
        assert self.client is not None
        self.transport.close()
        return True, True

    @check_packet(17)
    def handle_plan(self, packet: Tuple[bytes, ...]) -> HandleResult:
        """Handle plan update request."""
        assert self.client is not None
        (
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
        ) = packet[2:17]
        plan_type = plan_type[0:1]
        tascruise_int = str_to_int(tascruise, default_value=0)
        dep_time_int = str_to_int(dep_time, default_value=0)
        act_dep_time_int = str_to_int(act_dep_time, default_value=0)
        hrs_enroute_int = str_to_int(hrs_enroute, default_value=0)
        min_enroute_int = str_to_int(min_enroute, default_value=0)
        hrs_fuel_int = str_to_int(hrs_fuel, default_value=0)
        min_fuel_int = str_to_int(min_fuel, default_value=0)
        self.client.update_plan(
            plan_type,
            aircraft,
            tascruise_int,
            dep_airport,
            dep_time_int,
            act_dep_time_int,
            alt,
            dest_airport,
            hrs_enroute_int,
            min_enroute_int,
            hrs_fuel_int,
            min_fuel_int,
            alt_airport,
            remarks,
            route,
        )
        self.factory.broadcast(
            # Another FSD quirk: truncated if plan_type is empty
            make_packet(
                FSDClientCommand.PLAN + self.client.callsign,
                b"*A",
                b"",
            )
            if len(plan_type) == 0
            else make_packet(
                FSDClientCommand.PLAN + self.client.callsign,
                b"*A",
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
            ),
            check_func=all_ATC_checker,
            from_client=self.client,
        )
        return True, True

    @check_packet(10, callsign_position=1)
    def handle_pilot_position_update(
        self,
        packet: Tuple[bytes, ...],
    ) -> HandleResult:
        """Handle pilot position update request."""
        assert self.client is not None
        (
            mode,
            _,
            transponder,
            _,
            lat,
            lon,
            altitdue,
            groundspeed,
            pbh,
            flags,
        ) = packet[:10]
        transponder_int = str_to_int(transponder, default_value=0)
        lat_float = str_to_float(lat, default_value=0.0)
        lon_float = str_to_float(lon, default_value=0.0)
        altitdue_int = str_to_int(altitdue, default_value=0)
        pbh_int = str_to_int(pbh, default_value=0) & 0xFFFFFFFF  # Simulate unsigned
        groundspeed_int = str_to_int(groundspeed, default_value=0)
        flags_int = str_to_int(flags, default_value=0)
        if (
            lat_float > 90.0
            or lat_float < -90.0
            or lon_float > 180.0
            or lon_float < -180.0
        ):
            logger.debug(
                "Invaild position: "
                + self.client.callsign.decode(errors="replace")
                + f" with {lat_float}, {lon_float}",
            )
        self.client.update_pilot_position(
            mode,
            transponder_int,
            lat_float,
            lon_float,
            altitdue_int,
            groundspeed_int,
            pbh_int,
            flags_int,
        )
        self.reset_timeout_killer()
        self.factory.broadcast(
            make_packet(
                FSDClientCommand.PILOT_POSITION + mode,
                self.client.callsign,
                transponder,
                b"%d" % self.client.rating,
                b"%.5f" % lat_float,
                b"%.5f" % lon_float,
                altitdue,
                groundspeed,
                pbh,
                flags,
            ),
            check_func=broadcast_position_checker,
            from_client=self.client,
        )
        return True, True

    @check_packet(8)
    def handle_ATC_position_update(  # noqa: N802
        self,
        packet: Tuple[bytes, ...],
    ) -> HandleResult:
        """Handle ATC position update request."""
        assert self.client is not None
        (
            frequency,
            facility_type,
            visual_range,
            _,
            lat,
            lon,
            altitdue,
        ) = packet[1:8]
        lat_float = str_to_float(lat, default_value=0.0)
        lon_float = str_to_float(lon, default_value=0.0)
        frequency_int = str_to_int(frequency, default_value=0)
        facility_type_int = str_to_int(facility_type, default_value=0)
        visual_range_int = str_to_int(visual_range, default_value=0)
        altitdue_int = str_to_int(altitdue, default_value=0)
        if (
            lat_float > 90.0
            or lat_float < -90.0
            or lon_float > 180.0
            or lon_float < -180.0
        ):
            logger.debug(
                "Invaild position: "
                + self.client.callsign.decode(errors="replace")
                + f" with {lat_float}, {lon_float}",
            )
        self.client.update_ATC_position(
            frequency_int,
            facility_type_int,
            visual_range_int,
            lat_float,
            lon_float,
            altitdue_int,
        )
        self.reset_timeout_killer()
        self.factory.broadcast(
            make_packet(
                FSDClientCommand.ATC_POSITION + self.client.callsign,
                frequency,
                facility_type,
                visual_range,
                b"%d" % self.client.rating,
                b"%.5f" % lat_float,
                b"%.5f" % lon_float,
                altitdue,
            ),
            check_func=broadcast_position_checker,
            from_client=self.client,
        )
        return True, True

    @check_packet(2)
    def handle_server_ping(self, packet: Tuple[bytes, ...]) -> HandleResult:
        """Handle server ping request."""
        assert self.client is not None
        self.send_line(
            make_packet(
                FSDClientCommand.PONG + b"server",
                self.client.callsign,
                *packet[2:] if len(packet) > 2 else [b""],
            ),
        )
        return True, True

    @check_packet(3)
    async def handle_weather(
        self,
        packet: Tuple[bytes, ...],
    ) -> HandleResult:
        """Handle weather request."""
        assert self.client is not None
        metar = await self.factory.metar_manager.fetch(
            packet[2].decode("ascii", "ignore")
        )
        if not metar:
            self.send_error(FSDErrors.ERR_NOWEATHER, packet[2])
            return True, False
        packets = []
        profile = WeatherProfile(int(time()), None, metar)
        profile.fix(self.client.position)

        temps: List[bytes] = []
        for temp in profile.temps:
            temps.append(b"%d:%d" % (temp.ceiling, temp.temp))
        packets.append(
            make_packet(
                FSDClientCommand.TEMP_DATA + b"server",
                self.client.callsign,
                *temps,
                b"%d" % profile.barometer,
            ),
        )

        winds: List[bytes] = []
        for wind in profile.winds:
            winds.append(
                b"%d:%d:%d:%d:%d:%d"
                % (
                    wind.ceiling,
                    wind.floor,
                    wind.direction,
                    wind.speed,
                    wind.gusting,
                    wind.turbulence,
                ),
            )
        packets.append(
            make_packet(
                FSDClientCommand.WIND_DATA + b"server",
                self.client.callsign,
                *winds,
            ),
        )

        clouds: List[bytes] = []
        for cloud in (*profile.clouds, profile.tstorm):
            clouds.append(
                b"%d:%d:%d:%d:%d"
                % (
                    cloud.ceiling,
                    cloud.floor,
                    cloud.coverage,
                    cloud.icing,
                    cloud.turbulence,
                ),
            )
        packets.append(
            make_packet(
                FSDClientCommand.CLOUD_DATA + b"server",
                self.client.callsign,
                *clouds,
                b"%.2f" % profile.visibility,
            ),
        )

        self.send_lines(*packets)
        return True, True

    @check_packet(3)
    async def handle_acars(
        self,
        packet: Tuple[bytes, ...],
    ) -> HandleResult:
        """Handle acars request."""
        assert self.client is not None

        if packet[2].upper() == b"METAR" and len(packet) > 3:
            metar = await self.factory.metar_manager.fetch(
                packet[3].decode(errors="ignore")
            )

            if metar is None:
                self.send_error(FSDErrors.ERR_NOWEATHER, packet[3])
                return True, False

            self.send_line(
                make_packet(
                    FSDClientCommand.REPLY_ACARS + b"server",
                    self.client.callsign,
                    b"METAR",
                    metar.code.encode("ascii"),
                ),
            )
            return True, True
        return True, True  # yep

    @check_packet(3)
    def handle_CQ(self, packet: Tuple[bytes, ...]) -> HandleResult:  # noqa: N802
        """Handle $CQ request."""
        # Behavior may differ from FSD.
        assert self.client is not None
        if packet[1].upper() != b"SERVER":
            # Multicast a message.
            return self.handle_cast(
                packet,
                FSDClientCommand.CQ,
                require_parts=3,
                multicast_able=True,
            )
        if packet[2].lower() == b"fp":
            # Get flight plan.
            if len(packet) < 4:
                self.send_error(FSDErrors.ERR_SYNTAX)
                return True, False
            callsign = packet[3]
            if (client := self.factory.clients.get(callsign)) is None:
                self.send_error(FSDErrors.ERR_NOSUCHCS, env=callsign)
                return True, False
            if (plan := client.flight_plan) is None:
                self.send_error(FSDErrors.ERR_NOFP)
                return True, False
            if self.client.type != "ATC":
                return False, False
            self.send_line(
                make_packet(
                    FSDClientCommand.PLAN + callsign,
                    self.client.callsign,
                    plan.type,
                    plan.aircraft,
                    b"%d" % plan.tascruise,
                    plan.dep_airport,
                    b"%d" % plan.dep_time,
                    b"%d" % plan.act_dep_time,
                    plan.alt,
                    plan.dest_airport,
                    b"%d" % plan.hrs_enroute,
                    b"%d" % plan.min_enroute,
                    b"%d" % plan.hrs_fuel,
                    b"%d" % plan.min_fuel,
                    plan.alt_airport,
                    plan.remarks,
                    plan.route,
                ),
            )
        elif packet[2].upper() == b"RN":
            # XXX: Implemention maybe incorrect
            # Get realname?
            callsign = packet[1]
            if (client := self.factory.clients.get(callsign)) is not None:
                self.send_line(
                    make_packet(
                        FSDClientCommand.CR + callsign,
                        self.client.callsign,
                        b"RN",
                        client.realname,
                        b"USER",
                        b"%d" % client.rating,
                    ),
                )
                return True, True
            return True, False
        return True, True

    @check_packet(3, check_callsign=False)
    def handle_kill(self, packet: Tuple[bytes, ...]) -> HandleResult:
        """Handle kill request."""
        assert self.client is not None
        _, callsign_kill, reason = packet[:3]
        if callsign_kill not in self.factory.clients:
            self.send_error(FSDErrors.ERR_NOSUCHCS, env=callsign_kill)
            return True, False
        if self.client.rating < 11:
            self.send_line(
                make_packet(
                    FSDClientCommand.MESSAGE + b"server",
                    self.client.callsign,
                    b"You are not allowed to kill users!",
                ),
            )
            return True, False
        self.send_line(
            make_packet(
                FSDClientCommand.MESSAGE + b"server",
                self.client.callsign,
                b"Attempting to kill %s" % callsign_kill,
            ),
        )
        self.factory.send_to(
            callsign_kill,
            make_packet(FSDClientCommand.KILL + b"SERVER", callsign_kill, reason),
        )
        self.factory.clients[callsign_kill].transport.close()
        return True, True

    def line_received(self, line: bytes) -> None:
        """Handle a line."""

        async def handle() -> None:
            result: Union["PyFSDHandledLineResult", "PluginHandledEventResult"]
            # First try to let plugins to process
            plugin_result = await self.factory.plugin_manager.trigger_event(
                "line_received_from_client",
                (self, line),
                {},
                prevent_able=True,
            )
            if plugin_result is None:  # Not handled by plugin
                packet_ok, has_result = await self.handle_line(line)
                result = cast(
                    "PyFSDHandledLineResult",
                    {
                        "handled_by_plugin": False,
                        "success": packet_ok and has_result,
                        "packet": line,
                        "packet_ok": packet_ok,
                        "has_result": has_result,
                    },
                )
            else:
                result = plugin_result

            await self.factory.plugin_manager.trigger_event(
                "audit_line_from_client",
                (self, line, result),
                {},
            )

        async def do_after_before_done() -> None:
            """Wait last task done then handle this."""
            async with self.lock:
                await handle()

        self.add_task(create_task(do_after_before_done()))

    async def handle_line(
        self,
        byte_line: bytes,
    ) -> HandleResult:
        """Handle a line."""
        if len(byte_line) == 0:
            return True, True
        command, packet = break_packet(byte_line, CLIENT_USED_COMMAND)
        if command is None:
            self.send_error(FSDErrors.ERR_SYNTAX)
            return False, False
        if command is FSDClientCommand.ADD_ATC or command is FSDClientCommand.ADD_PILOT:
            return await self.handle_add_client(
                packet,
                "ATC" if command is FSDClientCommand.ADD_ATC else "PILOT",
            )
        if command is FSDClientCommand.PLAN:
            return await self.handle_plan(packet)
        if (
            command is FSDClientCommand.REMOVE_ATC
            or command is FSDClientCommand.REMOVE_PILOT
        ):
            return await self.handle_remove_client(packet)
        if command is FSDClientCommand.PILOT_POSITION:
            return await self.handle_pilot_position_update(packet)
        if command is FSDClientCommand.ATC_POSITION:
            return await self.handle_ATC_position_update(packet)
        if command is FSDClientCommand.PONG:
            return self.handle_cast(
                packet,
                command,
                require_parts=2,
                multicast_able=True,
            )
        if command is FSDClientCommand.PING:
            if len(packet) > 1 and packet[1].lower() == b"server":
                return await self.handle_server_ping(packet)
            return self.handle_cast(
                packet,
                command,
                require_parts=2,
                multicast_able=True,
            )

        if command is FSDClientCommand.MESSAGE:
            return self.handle_cast(
                packet,
                command=command,
                require_parts=3,
                multicast_able=True,
                custom_at_checker=broadcast_message_checker,
            )
        if (
            command is FSDClientCommand.REQUEST_HANDOFF
            or command is FSDClientCommand.AC_HANDOFF
        ):
            return self.handle_cast(
                packet,
                command,
                require_parts=3,
                multicast_able=False,
            )
        if command is FSDClientCommand.SB or command is FSDClientCommand.PC:
            return self.handle_cast(
                packet,
                command,
                require_parts=2,
                multicast_able=False,
            )
        if command is FSDClientCommand.WEATHER:
            return await self.handle_weather(packet)
        if command is FSDClientCommand.REQUEST_COMM:
            return self.handle_cast(
                packet,
                command,
                require_parts=2,
                multicast_able=False,
            )
        if command is FSDClientCommand.REPLY_COMM:
            return self.handle_cast(
                packet,
                command,
                require_parts=3,
                multicast_able=False,
            )
        if command is FSDClientCommand.REQUEST_ACARS:
            return await self.handle_acars(packet)
        if command is FSDClientCommand.CR:
            return self.handle_cast(
                packet,
                command,
                require_parts=4,
                multicast_able=False,
            )
        if command is FSDClientCommand.CQ:
            return await self.handle_CQ(packet)
        if command is FSDClientCommand.KILL:
            return await self.handle_kill(packet)
        self.send_error(FSDErrors.ERR_SYNTAX)
        return False, False

    def connection_lost(self, _: Optional[BaseException] = None) -> None:  # pyright: ignore
        """Handle connection lost."""
        if hasattr(self, "timeout_killer_task"):
            self.timeout_killer_task.cancel()

        if self.client is not None:
            logger.info(
                f"{self.transport.get_extra_info('peername')[0]} "
                f"({self.client.callsign.decode(errors='replace')}) "
                "disconnected.",
            )
            for pending_task in self.tasks:
                pending_task.cancel()
            self.factory.broadcast(
                make_packet(
                    (
                        FSDClientCommand.REMOVE_ATC
                        if self.client.type == "ATC"
                        else FSDClientCommand.REMOVE_PILOT
                    )
                    + self.client.callsign,
                    self.client.cid.encode(),
                ),
                from_client=self.client,
            )
            del self.factory.clients[self.client.callsign]
            task_keeper.add(
                create_task(
                    self.factory.plugin_manager.trigger_event(
                        "client_disconnected",
                        (self, self.client),
                        {},
                    )
                )
            )
            self.client = None
        else:
            logger.info(f"{self.transport.get_extra_info('peername')[0]} disconnected.")
