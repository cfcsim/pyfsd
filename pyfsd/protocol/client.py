from threading import Lock
from time import time
from typing import TYPE_CHECKING, List, Optional, Tuple

from twisted.internet import reactor
from twisted.internet.interfaces import ITransport
from twisted.logger import Logger
from twisted.protocols.basic import LineReceiver

from .._version import __version__

# from ..config import config
from ..define.broadcast import (
    BroadcastChecker,
    allATCChecker,
    allPilotChecker,
    atChecker,
    broadcastMessageChecker,
    broadcastPositionChecker,
    isMulticast,
)
from ..define.errors import FSDErrors
from ..define.packet import FSDCLIENTPACKET, breakPacket, concat, makePacket
from ..define.utils import isCallsignVaild, joinLines, strToFloat, strToInt
from ..metar.profile import WeatherProfile
from ..object.client import Client, ClientType

if TYPE_CHECKING:
    from constantly import ValueConstant  # type: ignore[import]
    from metar.Metar import Metar
    from twisted.internet.base import DelayedCall

    from ..factory.client import FSDClientFactory

__all__ = ["FSDClientProtocol"]

version = __version__.encode("ascii")


class FSDClientProtocol(LineReceiver):
    factory: "FSDClientFactory"
    transport: ITransport
    timeoutKiller: "DelayedCall"
    logger: Logger
    client: Optional[Client] = None
    line_lock: Lock

    def __init__(self) -> None:
        self.logger = Logger()
        self.client = None
        self.line_lock = Lock()

    def connectionMade(self):
        self.timeoutKiller = reactor.callLater(800, self.timeout)  # type: ignore
        self.logger.info(
            "New connection from {ip}.",
            ip=self.transport.getPeer().host,  # type: ignore[attr-defined]
        )
        self.factory.triggerEvent("newConnectionEstablished", (self,), {})

    def sendLines(
        self, *lines: bytes, auto_newline: bool = True, togerher: bool = True
    ) -> None:
        if togerher:
            self.transport.write(  # type: ignore
                joinLines(*lines, newline=auto_newline)  # type: ignore
            )
        else:
            for line in lines:
                self.transport.write(  # type: ignore
                    (line + b"\r\n") if auto_newline else line  # type: ignore
                )

    def sendError(self, errno: int, env: bytes = b"", fatal: bool = False) -> None:
        assert errno > 0 and errno <= 13
        err_bytes = FSDErrors.error_names[errno].encode("ascii")
        self.sendLine(
            makePacket(
                concat(FSDCLIENTPACKET.ERROR, b"server"),
                self.client.callsign if self.client is not None else b"unknown",
                f"{errno:03d}".encode(),  # = str(errno).rjust(3, "0")
                env,
                err_bytes,
            )
        )
        if fatal:
            self.transport.loseConnection()

    def timeout(self) -> None:
        self.sendLine(b"# Timeout")
        self.transport.loseConnection()

    def sendMotd(self) -> None:
        assert self.client is not None
        motd_lines: List[bytes] = [
            b"#TMserver:%s:PyFSD %s" % (self.client.callsign, version)
        ]
        for line in self.factory.motd:
            motd_lines.append(
                # AnyStr | ValueConstant(not yet typed == Any) doesn't work in mypy,
                # ignore it temporary
                makePacket(  # type: ignore[arg-type]
                    concat(FSDCLIENTPACKET.MESSAGE, b"server"),
                    self.client.callsign,
                    line,
                )
            )
        self.sendLines(*motd_lines)

    def multicast(
        self,
        to_limiter: str,
        *lines: bytes,
        custom_at_checker: Optional[BroadcastChecker] = None,
    ) -> None:
        assert self.client is not None
        if to_limiter == "*":
            # No check_func specified, why? -- Default checker is lambda: True
            self.factory.broadcast(*lines, from_client=self.client)
        elif to_limiter == "*A":
            self.factory.broadcast(
                *lines, check_func=allATCChecker, from_client=self.client
            )
        elif to_limiter == "*P":
            self.factory.broadcast(
                *lines, check_func=allPilotChecker, from_client=self.client
            )
        elif to_limiter.startswith("@"):
            self.factory.broadcast(
                *lines,
                from_client=self.client,
                check_func=custom_at_checker
                if custom_at_checker is not None
                else atChecker,
            )
        else:
            raise NotImplementedError

    def unicast(
        self, callsign: bytes, *lines: bytes, auto_newline: bool = True
    ) -> None:
        self.factory.sendTo(callsign, *lines, auto_newline=auto_newline)

    def handleCast(
        self,
        packet: Tuple[bytes, ...],
        command: "ValueConstant",
        require_param: int = 2,
        multicast_able: bool = True,
        custom_at_checker: Optional[BroadcastChecker] = None,
    ) -> None:
        packet_len: int = len(packet)
        if packet_len < require_param:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        to_callsign = packet[1]
        maycast_tocs = to_callsign.decode("ascii", "replace")
        to_packet = makePacket(
            concat(command, self.client.callsign),
            to_callsign,
            *packet[2:] if packet_len > 2 else [b""],
        )
        if isMulticast(maycast_tocs):
            if multicast_able:
                self.multicast(
                    maycast_tocs,
                    # Mypy bug, to_packet is bytes
                    to_packet,  # type: ignore[arg-type]
                    custom_at_checker=custom_at_checker,
                )
        else:
            self.factory.sendTo(
                to_callsign,
                # Mypy bug, to_packet is bytes
                to_packet,  # type: ignore[arg-type]
            )

    def handleAddClient(
        self, packet: Tuple[bytes, ...], client_type: ClientType
    ) -> None:
        if self.client is not None:
            self.sendError(FSDErrors.ERR_REGISTERED)
            return
        if client_type == "PILOT":
            if len(packet) < 8:
                self.sendError(FSDErrors.ERR_SYNTAX)
                return
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
            sim_type_int = strToInt(sim_type, default_value=0)
        else:
            if len(packet) < 7:
                self.sendError(FSDErrors.ERR_SYNTAX)
                return
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
            req_rating_int = strToInt(req_rating, default_value=0)
        protocol_int = strToInt(protocol, default_value=-1)
        if not isCallsignVaild(callsign):
            self.sendError(FSDErrors.ERR_CSINVALID, fatal=True)
            return
        if callsign in self.factory.clients:
            self.sendError(FSDErrors.ERR_CSINUSE)
            return
        if not protocol_int == 9:
            self.sendError(FSDErrors.ERR_REVISION, fatal=True)
            return

        try:
            cid_str = cid.decode("utf-8")
            pwd_str = password.decode("utf-8")
        except UnicodeDecodeError:
            self.sendError(FSDErrors.ERR_CIDINVALID, env=cid, fatal=True)
            return

        def onResult(result):
            rating: int = result[1].rating
            if rating == 0:
                self.sendError(FSDErrors.ERR_CSSUSPEND, fatal=True)
            else:
                if rating < req_rating_int:
                    self.sendError(
                        FSDErrors.ERR_LEVEL,
                        env=req_rating,
                        fatal=True,
                    )
                else:
                    onSuccess()

        def onFail(_):
            self.sendError(FSDErrors.ERR_CIDINVALID, env=cid, fatal=True)

        def onSuccess():
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
                    # two times of req_rating --- not a typo
                    makePacket(
                        concat(FSDCLIENTPACKET.ADD_PILOT, callsign),
                        b"SERVER",
                        cid,
                        b"",
                        req_rating,
                        req_rating,
                        sim_type,
                    ),
                    from_client=client,
                )
            else:
                self.factory.broadcast(
                    makePacket(
                        concat(FSDCLIENTPACKET.ADD_ATC, callsign),
                        b"SERVER",
                        realname,
                        cid,
                        b"",
                        req_rating,
                    ),
                    from_client=client,
                )
            self.sendMotd()
            self.logger.info(
                "New client {callsign} ({cid}) from {ip}.",
                callsign=callsign.decode(errors="backslashreplace"),
                cid=cid_str,
                ip=self.transport.getPeer().host,  # type: ignore[attr-defined]
            )
            self.factory.triggerEvent("newClientCreated", (self,), {})

        self.factory.login(cid_str, pwd_str).addCallback(onResult).addErrback(onFail)

    def handleRemoveClient(self, packet: Tuple[bytes, ...]) -> None:
        if len(packet) == 0:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        self.transport.loseConnection()

    def handlePlan(self, packet: Tuple[bytes, ...]) -> None:
        if len(packet) < 17:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
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
        tascruise_int = strToInt(tascruise, default_value=0)
        dep_time_int = strToInt(dep_time, default_value=0)
        act_dep_time_int = strToInt(act_dep_time, default_value=0)
        hrs_enroute_int = strToInt(hrs_enroute, default_value=0)
        min_enroute_int = strToInt(min_enroute, default_value=0)
        hrs_fuel_int = strToInt(hrs_fuel, default_value=0)
        min_fuel_int = strToInt(min_fuel, default_value=0)
        self.client.updatePlan(
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
            makePacket(  # type: ignore[arg-type]
                concat(FSDCLIENTPACKET.PLAN, self.client.callsign),
                b"*A",
                b"",
            )
            if plan_type is None
            else makePacket(
                concat(FSDCLIENTPACKET.PLAN, self.client.callsign),
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
            check_func=allATCChecker,
            from_client=self.client,
        )

    def handlePilotPositionUpdate(self, packet: Tuple[bytes, ...]) -> None:
        if len(packet) < 10:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if self.client is None:
            return
        if self.client.callsign != packet[1]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
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
        transponder_int = strToInt(transponder, default_value=0)
        lat_float = strToFloat(lat, default_value=0.0)
        lon_float = strToFloat(lon, default_value=0.0)
        altitdue_int = strToInt(altitdue, default_value=0)
        pbh_int = strToInt(pbh, default_value=0) & 0xFFFFFFFF
        groundspeed_int = strToInt(groundspeed, default_value=0)
        flags_int = strToInt(flags, default_value=0)
        if (
            lat_float > 90.0
            or lat_float < -90.0
            or lon_float > 180.0
            or lon_float < -180.0
        ):
            self.logger.debug(
                "Invaild position: "
                + self.client.callsign.decode(errors="replace")
                + f" with {lat_float}, {lon_float}"
            )
        self.client.updatePilotPosition(
            mode,
            transponder_int,
            lat_float,
            lon_float,
            altitdue_int,
            groundspeed_int,
            pbh_int,
            flags_int,
        )
        self.timeoutKiller.reset(800)
        self.factory.broadcast(
            makePacket(  # type: ignore[arg-type]
                concat(FSDCLIENTPACKET.PILOT_POSITION, mode),
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
            check_func=broadcastPositionChecker,
            from_client=self.client,
        )

    def handleATCPositionUpdate(self, packet: Tuple[bytes, ...]) -> None:
        if len(packet) < 8:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        (
            frequency,
            facility_type,
            visual_range,
            _,
            lat,
            lon,
            altitdue,
        ) = packet[1:8]
        lat_float = strToFloat(lat, default_value=0.0)
        lon_float = strToFloat(lon, default_value=0.0)
        frequency_int = strToInt(frequency, default_value=0)
        facility_type_int = strToInt(facility_type, default_value=0)
        visual_range_int = strToInt(visual_range, default_value=0)
        altitdue_int = strToInt(altitdue, default_value=0)
        if (
            lat_float > 90.0
            or lat_float < -90.0
            or lon_float > 180.0
            or lon_float < -180.0
        ):
            self.logger.debug(
                "Invaild position: "
                + self.client.callsign.decode(errors="replace")
                + f" with {lat_float}, {lon_float}"
            )
        self.client.updateATCPosition(
            frequency_int,
            facility_type_int,
            visual_range_int,
            lat_float,
            lon_float,
            altitdue_int,
        )
        self.timeoutKiller.reset(800)
        self.factory.broadcast(
            makePacket(  # type: ignore[arg-type]
                concat(FSDCLIENTPACKET.ATC_POSITION, self.client.callsign),
                frequency,
                facility_type,
                visual_range,
                b"%d" % self.client.rating,
                b"%.5f" % lat_float,
                b"%.5f" % lon_float,
                altitdue,
            ),
            check_func=broadcastPositionChecker,
            from_client=self.client,
        )

    def handleServerPing(self, packet: Tuple[bytes, ...]) -> None:
        packet_len: int = len(packet)
        if packet_len < 2:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        self.sendLine(
            makePacket(
                concat(FSDCLIENTPACKET.PONG, b"server"),
                self.client.callsign,
                *packet[2:] if packet_len > 2 else [b""],
            )
        )

    def handleWeather(self, packet: Tuple[bytes, ...]) -> None:
        if len(packet) < 3:
            self.sendError(FSDErrors.ERR_SYNTAX)
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return

        def sendMetar(metar: Optional["Metar"]) -> None:
            assert self.client is not None
            if metar is None:
                self.sendError(FSDErrors.ERR_NOWEATHER, packet[2])
            else:
                packets = []
                profile = WeatherProfile(int(time()), None, metar)
                profile.fix(self.client.position)

                temps: List[bytes] = []
                for temp in profile.temps:
                    temps.append(b"%d:%d" % (temp.ceiling, temp.temp))
                packets.append(
                    makePacket(
                        concat(FSDCLIENTPACKET.TEMP_DATA, b"server"),
                        self.client.callsign,
                        *temps,
                        b"%d" % profile.barometer,
                    )
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
                        )
                    )
                packets.append(
                    makePacket(
                        concat(FSDCLIENTPACKET.WIND_DATA, b"server"),
                        self.client.callsign,
                        *winds,
                    )
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
                        )
                    )
                packets.append(
                    makePacket(
                        concat(FSDCLIENTPACKET.CLOUD_DATA, b"server"),
                        self.client.callsign,
                        *clouds,
                        b"%.2f" % profile.visibility,
                    )
                )

                # Mypy bug
                self.sendLines(*packets)  # type: ignore

        self.factory.fetch_metar(packet[2].decode("ascii", "ignore")).addCallback(
            sendMetar
        )

    def handleAcars(self, packet: Tuple[bytes, ...]) -> None:
        if len(packet) < 3:
            self.sendError(FSDErrors.ERR_SYNTAX)
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        if packet[2].upper() == "METAR" and len(packet) > 3:

            def sendMetar(metar: Optional["Metar"]) -> None:
                assert self.client is not None
                if metar is None:
                    self.sendError(FSDErrors.ERR_NOWEATHER, packet[3])
                else:
                    self.sendLine(
                        makePacket(
                            concat(FSDCLIENTPACKET.REPLY_ACARS, b"server"),
                            self.client.callsign,
                            b"METAR",
                            metar.code.encode("ascii"),
                        )
                    )

            self.factory.fetch_metar(packet[3].decode(errors="ignore")).addCallback(
                sendMetar
            )

    def handleCq(self, packet: Tuple[bytes, ...]) -> None:
        # Behavior may differ from FSD.
        if len(packet) < 3:
            self.sendError(FSDErrors.ERR_SYNTAX)
        if self.client is None:
            return
        if packet[1].upper() != b"SERVER":
            self.handleCast(
                packet, FSDCLIENTPACKET.CQ, require_param=3, multicast_able=True
            )
            return
        elif packet[2].lower() == b"fp":
            if len(packet) < 4:
                self.sendError(FSDErrors.ERR_SYNTAX)
            callsign = packet[3]
            if (client := self.factory.clients.get(callsign)) is None:
                self.sendError(FSDErrors.ERR_NOSUCHCS, env=callsign)
                return
            if (plan := client.flight_plan) is None:
                self.sendError(FSDErrors.ERR_NOFP)
                return
            if not self.client.type == "ATC":
                return
            self.sendLine(
                makePacket(
                    FSDCLIENTPACKET.PLAN,
                    callsign,
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
                )
            )
        elif packet[2].upper() == b"RN":
            # This part won't execute except a client named 'server'
            callsign = packet[1]
            if (client := self.factory.clients.get(callsign)) is not None:
                self.sendLine(
                    makePacket(
                        FSDCLIENTPACKET.CR,
                        callsign,
                        self.client.callsign,
                        b"RN",
                        client.realname,
                        b"USER",
                        b"%d" % client.rating,
                    )
                )

    def handleKill(self, packet: Tuple[bytes, ...]) -> None:
        if len(packet) < 3:
            self.sendError(FSDErrors.ERR_SYNTAX)
        if self.client is None:
            return
        _, callsign_kill, reason = packet[:3]
        if callsign_kill not in self.factory.clients:
            self.sendError(FSDErrors.ERR_NOSUCHCS, env=callsign_kill)
            return
        if self.client.rating < 11:
            self.sendLine(
                makePacket(
                    concat(FSDCLIENTPACKET.MESSAGE, b"server"),
                    self.client.callsign,
                    b"You are not allowed to kill users!",
                )
            )
        else:
            self.sendLine(
                makePacket(
                    concat(FSDCLIENTPACKET.MESSAGE, b"server"),
                    self.client.callsign,
                    b"Attempting to kill %s" % callsign_kill,
                )
            )
            self.factory.sendTo(
                callsign_kill,
                makePacket(  # type: ignore[arg-type]
                    concat(FSDCLIENTPACKET.KILL, b"SERVER"), callsign_kill, reason
                ),
            )
            self.factory.clients[callsign_kill].transport.loseConnection()

    def lineReceived(self, byte_line: bytes) -> None:
        with self.line_lock:
            # Acquire without lock it (nearly)
            pass

        def resultHandler(prevented: bool) -> None:
            if not prevented:
                with self.line_lock:
                    self.lineReceived_impl(byte_line)

        self.factory.triggerEvent(
            "lineReceivedFromClient", (self, byte_line), {}
        ).addCallback(resultHandler)

    def lineReceived_impl(self, byte_line: bytes) -> None:
        if len(byte_line) == 0:
            return
        command, packet = breakPacket(byte_line, FSDCLIENTPACKET.client_used_command)
        if command == FSDCLIENTPACKET.ADD_ATC or command == FSDCLIENTPACKET.ADD_PILOT:
            self.handleAddClient(
                packet, "ATC" if command == FSDCLIENTPACKET.ADD_ATC else "PILOT"
            )
        elif command == FSDCLIENTPACKET.PLAN:
            self.handlePlan(packet)
        elif (
            command == FSDCLIENTPACKET.REMOVE_ATC
            or command == FSDCLIENTPACKET.REMOVE_PILOT
        ):
            self.handleRemoveClient(packet)
        elif command == FSDCLIENTPACKET.PILOT_POSITION:
            self.handlePilotPositionUpdate(packet)
        elif command == FSDCLIENTPACKET.ATC_POSITION:
            self.handleATCPositionUpdate(packet)
        elif command == FSDCLIENTPACKET.PONG:
            assert command is not None, "Why FSDCLIENTPACKET.PONG is None???"
            self.handleCast(packet, command, require_param=2, multicast_able=True)
        elif command == FSDCLIENTPACKET.PING:
            assert command is not None, "Why FSDCLIENTPACKET.PING is None???"
            if len(packet) > 1 and packet[1].lower() == "server":
                self.handleServerPing(packet)
            else:
                self.handleCast(packet, command, require_param=2, multicast_able=True)
        elif command is FSDCLIENTPACKET.MESSAGE:
            assert command is not None, "Why FSDCLIENTPACKET.MESSAGE is None???"
            self.handleCast(
                packet,
                command=command,
                require_param=3,
                multicast_able=True,
                custom_at_checker=broadcastMessageChecker,
            )
        elif (
            command == FSDCLIENTPACKET.REQUEST_HANDOFF
            or command == FSDCLIENTPACKET.AC_HANDOFF
        ):
            assert command is not None, "Why FSDCLIENTPACKET.*_HANDOFF is None???"
            self.handleCast(packet, command, require_param=3, multicast_able=False)
        elif command == FSDCLIENTPACKET.SB or command == FSDCLIENTPACKET.PC:
            assert command is not None, "Why FSDCLIENTPACKET.SB/PC is None???"
            self.handleCast(packet, command, require_param=2, multicast_able=False)
        elif command == FSDCLIENTPACKET.WEATHER:
            self.handleWeather(packet)
        elif command == FSDCLIENTPACKET.REQUEST_COMM:
            assert command is not None, "Why FSDCLIENTPACKET.REQUEST_COMM is None???"
            self.handleCast(packet, command, require_param=2, multicast_able=False)
        elif command == FSDCLIENTPACKET.REPLY_COMM:
            assert command is not None, "Why FSDCLIENTPACKET.REPLY_COMM is None???"
            self.handleCast(packet, command, require_param=3, multicast_able=False)
        elif command == FSDCLIENTPACKET.REQUEST_ACARS:
            self.handleAcars(packet)
        elif command == FSDCLIENTPACKET.CR:
            assert command is not None, "Why FSDCLIENTPACKET.CR is None???"
            self.handleCast(packet, command, require_param=4, multicast_able=False)
        elif command == FSDCLIENTPACKET.CQ:
            self.handleCq(packet)
        elif command == FSDCLIENTPACKET.KILL:
            self.handleKill(packet)
        else:
            self.sendError(FSDErrors.ERR_SYNTAX)

    def connectionLost(self, _=None) -> None:
        if self.timeoutKiller.active():
            self.timeoutKiller.cancel()
        host: str = self.transport.getPeer().host  # type: ignore[attr-defined]
        if self.client is not None:
            self.logger.info(
                f"{host} ({self.client.callsign.decode(errors='replace')}) "
                "disconnected."
            )
            self.factory.broadcast(
                makePacket(  # type: ignore[arg-type]
                    concat(FSDCLIENTPACKET.REMOVE_ATC, self.client.callsign)
                    if self.client.type == "ATC"
                    else concat(FSDCLIENTPACKET.REMOVE_PILOT, self.client.callsign),
                    self.client.cid.encode(),
                ),
                from_client=self.client,
            )
            self.factory.triggerEvent("clientDisconnected", (self, self.client), {})
            del self.factory.clients[self.client.callsign]
            self.client = None
        else:
            self.logger.info(f"{host} disconnected.")
