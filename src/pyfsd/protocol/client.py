from threading import Lock
from time import time
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple, Type

from twisted.cred.error import UnauthorizedLogin
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import ITransport
from twisted.logger import Logger
from twisted.protocols.basic import LineReceiver

from .._version import version as pyfsd_version
from ..auth import IUserInfo

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
    from constantly import ValueConstant
    from metar.Metar import Metar
    from twisted.internet.base import DelayedCall
    from twisted.python.failure import Failure

    from ..auth import UserInfo
    from ..factory.client import FSDClientFactory
    from ..plugin import (
        PluginHandledEventResult,
        PyFSDHandledLineResult,
        ToHandledByPyFSDEventResult,
    )

__all__ = ["FSDClientProtocol"]

version = pyfsd_version.encode("ascii")
SUCCESS_RESULT: "PyFSDHandledLineResult" = {
    "handled_by_plugin": False,
    "success": True,
    "packet_ok": True,
    "has_result": True,
}
ALL_FAILED_RESULT: "PyFSDHandledLineResult" = {
    "handled_by_plugin": False,
    "success": False,
    "packet_ok": False,
    "has_result": False,
}
FAILED_WITHOUT_PACKET_RESULT: "PyFSDHandledLineResult" = {
    "handled_by_plugin": False,
    "success": False,
    "packet_ok": True,
    "has_result": False,
}


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

    def connectionMade(self) -> None:
        self.timeoutKiller = reactor.callLater(800, self.timeout)  # type: ignore
        self.logger.info(
            "New connection from {ip}.",
            ip=self.transport.getPeer().host,  # type: ignore[attr-defined]
        )
        self.factory.defer_event(
            "newConnectionEstablished", (self,), {}, False, False, True
        )

    def sendLines(
        self, *lines: bytes, auto_newline: bool = True, togerher: bool = True
    ) -> None:
        if togerher:
            self.transport.write(  # pyright: ignore
                joinLines(*lines, newline=auto_newline)  # pyright: ignore
            )
        else:
            for line in lines:
                self.transport.write(  # pyright: ignore
                    (line + b"\r\n") if auto_newline else line  # pyright: ignore
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

    def checkPacket(
        self,
        packet: Tuple[bytes, ...],
        require_param: int,
        callsign_position: int = 0,
        need_login: bool = True,
    ) -> "PyFSDHandledLineResult | None":
        if len(packet) < require_param:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return ALL_FAILED_RESULT
        if need_login:
            if self.client is None:
                return ALL_FAILED_RESULT
            if self.client.callsign != packet[callsign_position]:
                self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
                return ALL_FAILED_RESULT
        return None

    def multicast(
        self,
        to_limiter: str,
        *lines: bytes,
        custom_at_checker: Optional[BroadcastChecker] = None,
    ) -> bool:
        assert self.client is not None
        if to_limiter == "*":
            # Default checker is lambda: True, so send to all client
            return self.factory.broadcast(*lines, from_client=self.client)
        elif to_limiter == "*A":
            return self.factory.broadcast(
                *lines, check_func=allATCChecker, from_client=self.client
            )
        elif to_limiter == "*P":
            return self.factory.broadcast(
                *lines, check_func=allPilotChecker, from_client=self.client
            )
        elif to_limiter.startswith("@"):
            return self.factory.broadcast(
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
    ) -> bool:
        return self.factory.sendTo(callsign, *lines, auto_newline=auto_newline)

    def handleCast(
        self,
        packet: Tuple[bytes, ...],
        command: "ValueConstant",
        require_param: int = 2,
        multicast_able: bool = True,
        custom_at_checker: Optional[BroadcastChecker] = None,
    ) -> "PyFSDHandledLineResult":
        packet_len: int = len(packet)
        if (error := self.checkPacket(packet, require_param)) is not None:
            return error
        # This won't happen because checkPacket function checked it.
        assert self.client is not None
        to_callsign = packet[1]
        maycast_tocs = to_callsign.decode("ascii", "replace")
        to_packet = makePacket(
            concat(command, self.client.callsign),
            to_callsign,
            *packet[2:] if packet_len > 2 else [b""],
        )
        packet_ok = True
        if isMulticast(maycast_tocs):
            if multicast_able:
                success = self.multicast(
                    maycast_tocs,
                    # Mypy bug, to_packet is bytes
                    to_packet,  # type: ignore[arg-type]
                    custom_at_checker=custom_at_checker,
                )
            else:
                success = False
                packet_ok = False
        else:
            success = self.factory.sendTo(
                to_callsign,
                # Mypy bug, to_packet is bytes
                to_packet,  # type: ignore[arg-type]
            )
        return {
            "handled_by_plugin": False,
            "success": success and packet_ok,
            "packet_ok": packet_ok,
            "has_result": success,
        }

    def handleAddClient(
        self, packet: Tuple[bytes, ...], client_type: ClientType
    ) -> "Deferred[PyFSDHandledLineResult] | PyFSDHandledLineResult":
        if (
            error := self.checkPacket(
                packet, 8 if client_type == "PILOT" else 7, need_login=False
            )
        ) is not None:
            return error
        if self.client is not None:
            self.sendError(FSDErrors.ERR_REGISTERED)
            return ALL_FAILED_RESULT
        if client_type == "PILOT":
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
            return ALL_FAILED_RESULT
        if protocol_int != 9:
            self.sendError(FSDErrors.ERR_REVISION, fatal=True)
            return ALL_FAILED_RESULT
        try:
            cid_str = cid.decode("utf-8")
            pwd_str = password.decode("utf-8")
        except UnicodeDecodeError:
            self.sendError(FSDErrors.ERR_CIDINVALID, env=cid, fatal=True)
            return ALL_FAILED_RESULT

        if callsign in self.factory.clients:
            self.sendError(FSDErrors.ERR_CSINUSE)
            return FAILED_WITHOUT_PACKET_RESULT

        result_deferred: "Deferred[PyFSDHandledLineResult]" = Deferred()

        def onResult(
            result: Tuple[Type[IUserInfo], "UserInfo", Callable[[], None]]
        ) -> None:
            interface, userinfo, _ = result
            assert interface is IUserInfo or IUserInfo in interface.__bases__
            if userinfo.rating == 0:
                self.sendError(FSDErrors.ERR_CSSUSPEND, fatal=True)
                result_deferred.callback(FAILED_WITHOUT_PACKET_RESULT)

            else:
                if userinfo.rating < req_rating_int:
                    self.sendError(
                        FSDErrors.ERR_LEVEL,
                        env=req_rating,
                        fatal=True,
                    )
                    result_deferred.callback(FAILED_WITHOUT_PACKET_RESULT)
                else:
                    onSuccess()

        def onFail(f: "Failure") -> None:
            if not isinstance(f.value, UnauthorizedLogin):
                self.logger.failure("Exception threw while authorizing", failure=f)
            self.sendError(FSDErrors.ERR_CIDINVALID, env=cid, fatal=True)
            result_deferred.callback(FAILED_WITHOUT_PACKET_RESULT)

        def onSuccess() -> None:
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
                    # mypy bug
                    makePacket(  # type: ignore[arg-type]
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
                    makePacket(  # type: ignore[arg-type]
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
            self.factory.defer_event(
                "newClientCreated", (self,), {}, False, False, True
            )
            result_deferred.callback(SUCCESS_RESULT)

        self.factory.login(cid_str, pwd_str).addCallback(onResult).addErrback(onFail)
        return result_deferred

    def handleRemoveClient(self, packet: Tuple[bytes, ...]) -> "PyFSDHandledLineResult":
        if (error := self.checkPacket(packet, 1)) is not None:
            return error
        # This won't happen because checkPacket function checked it.
        assert self.client is not None
        self.transport.loseConnection()
        return SUCCESS_RESULT

    def handlePlan(self, packet: Tuple[bytes, ...]) -> "PyFSDHandledLineResult":
        if (error := self.checkPacket(packet, 17)) is not None:
            return error
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
        return SUCCESS_RESULT

    def handlePilotPositionUpdate(
        self, packet: Tuple[bytes, ...]
    ) -> "PyFSDHandledLineResult":
        if (error := self.checkPacket(packet, 10, callsign_position=1)) is not None:
            return error
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
        return SUCCESS_RESULT

    def handleATCPositionUpdate(
        self, packet: Tuple[bytes, ...]
    ) -> "PyFSDHandledLineResult":
        if (error := self.checkPacket(packet, 8)) is not None:
            return error
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
        return SUCCESS_RESULT

    def handleServerPing(self, packet: Tuple[bytes, ...]) -> "PyFSDHandledLineResult":
        if (error := self.checkPacket(packet, 2)) is not None:
            return error
        assert self.client is not None
        self.sendLine(
            makePacket(
                concat(FSDCLIENTPACKET.PONG, b"server"),
                self.client.callsign,
                *packet[2:] if len(packet) > 2 else [b""],
            )
        )
        return SUCCESS_RESULT

    def handleWeather(
        self, packet: Tuple[bytes, ...]
    ) -> "Deferred[PyFSDHandledLineResult] | PyFSDHandledLineResult":
        if (error := self.checkPacket(packet, 3)) is not None:
            return error
        assert self.client is not None
        deferred: Deferred["PyFSDHandledLineResult"] = Deferred()

        def errback(failure: "Failure") -> None:
            deferred.callback(FAILED_WITHOUT_PACKET_RESULT)
            self.logger.failure("Exception threw while fetching METAR", failure=failure)

        def sendMetar(metar: Optional["Metar"]) -> None:
            assert self.client is not None
            if metar is None:
                self.sendError(FSDErrors.ERR_NOWEATHER, packet[2])
                deferred.callback(FAILED_WITHOUT_PACKET_RESULT)
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
                deferred.callback(SUCCESS_RESULT)

        self.factory.fetch_metar(packet[2].decode("ascii", "ignore")).addCallback(
            sendMetar
        ).addErrback(errback)
        return deferred

    def handleAcars(
        self, packet: Tuple[bytes, ...]
    ) -> "Deferred[PyFSDHandledLineResult] | PyFSDHandledLineResult":
        if (error := self.checkPacket(packet, 3)) is not None:
            return error
        assert self.client is not None

        if packet[2].upper() == b"METAR" and len(packet) > 3:
            deferred: Deferred["PyFSDHandledLineResult"] = Deferred()

            def errback(failure: "Failure") -> None:
                deferred.callback(FAILED_WITHOUT_PACKET_RESULT)
                self.logger.failure(
                    "Exception threw while fetching METAR", failure=failure
                )

            def sendMetar(metar: Optional["Metar"]) -> None:
                assert self.client is not None
                if metar is None:
                    self.sendError(FSDErrors.ERR_NOWEATHER, packet[3])
                    deferred.callback(FAILED_WITHOUT_PACKET_RESULT)
                else:
                    self.sendLine(
                        makePacket(
                            concat(FSDCLIENTPACKET.REPLY_ACARS, b"server"),
                            self.client.callsign,
                            b"METAR",
                            metar.code.encode("ascii"),
                        )
                    )
                    deferred.callback(SUCCESS_RESULT)

            self.factory.fetch_metar(packet[3].decode(errors="ignore")).addCallback(
                sendMetar
            ).addErrback(errback)
            return deferred
        return SUCCESS_RESULT  # yep

    def handleCq(self, packet: Tuple[bytes, ...]) -> "PyFSDHandledLineResult":
        # Behavior may differ from FSD.
        if (error := self.checkPacket(packet, 3)) is not None:
            return error
        assert self.client is not None
        if packet[1].upper() != b"SERVER":
            return self.handleCast(
                packet, FSDCLIENTPACKET.CQ, require_param=3, multicast_able=True
            )
        elif packet[2].lower() == b"fp":
            if len(packet) < 4:
                self.sendError(FSDErrors.ERR_SYNTAX)
                return FAILED_WITHOUT_PACKET_RESULT
            callsign = packet[3]
            if (client := self.factory.clients.get(callsign)) is None:
                self.sendError(FSDErrors.ERR_NOSUCHCS, env=callsign)
                return FAILED_WITHOUT_PACKET_RESULT
            if (plan := client.flight_plan) is None:
                self.sendError(FSDErrors.ERR_NOFP)
                return FAILED_WITHOUT_PACKET_RESULT
            if not self.client.type == "ATC":
                return ALL_FAILED_RESULT
            self.sendLine(
                makePacket(
                    concat(FSDCLIENTPACKET.PLAN, callsign),
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
            # XXX Is the implemention correct?
            callsign = packet[1]
            if (client := self.factory.clients.get(callsign)) is not None:
                self.sendLine(
                    makePacket(
                        concat(FSDCLIENTPACKET.CR, callsign),
                        self.client.callsign,
                        b"RN",
                        client.realname,
                        b"USER",
                        b"%d" % client.rating,
                    )
                )
                return SUCCESS_RESULT
            return FAILED_WITHOUT_PACKET_RESULT
        return SUCCESS_RESULT

    def handleKill(self, packet: Tuple[bytes, ...]) -> "PyFSDHandledLineResult":
        if len(packet) < 3:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return ALL_FAILED_RESULT
        if self.client is None:
            return ALL_FAILED_RESULT
        _, callsign_kill, reason = packet[:3]
        if callsign_kill not in self.factory.clients:
            self.sendError(FSDErrors.ERR_NOSUCHCS, env=callsign_kill)
            return FAILED_WITHOUT_PACKET_RESULT
        if self.client.rating < 11:
            self.sendLine(
                makePacket(
                    concat(FSDCLIENTPACKET.MESSAGE, b"server"),
                    self.client.callsign,
                    b"You are not allowed to kill users!",
                )
            )
            return FAILED_WITHOUT_PACKET_RESULT
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
            return SUCCESS_RESULT

    def lineReceived(self, byte_line: bytes) -> None:
        with self.line_lock:
            # Acquire without lock it (nearly)
            pass

        def resultHandler(
            result: "PluginHandledEventResult | ToHandledByPyFSDEventResult",
        ) -> None:
            if not result["handled_by_plugin"]:
                with self.line_lock:
                    self_result = self.lineReceived_impl(byte_line)

                def postResult(new_result: "PyFSDHandledLineResult") -> None:
                    for handler in result["handlers"]:
                        handler(new_result)
                    self.factory.defer_event(
                        "auditLineFromClient",
                        (self, byte_line, new_result),
                        {},
                        False,
                        False,
                        True,
                    )

                if isinstance(self_result, dict):
                    postResult(self_result)
                else:
                    self_result.addCallback(postResult)
            else:
                self.factory.defer_event(
                    "auditLineFromClient",
                    (self, byte_line, result),
                    {},
                    False,
                    False,
                    True,
                )

        self.factory.defer_event(
            "lineReceivedFromClient", (self, byte_line), {}, False, False, False
        ).addCallback(resultHandler)

    def lineReceived_impl(
        self, byte_line: bytes
    ) -> "Deferred[PyFSDHandledLineResult] | PyFSDHandledLineResult":
        if len(byte_line) == 0:
            return SUCCESS_RESULT
        command, packet = breakPacket(byte_line, FSDCLIENTPACKET.client_used_command)
        if command is None:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return ALL_FAILED_RESULT
        elif command is FSDCLIENTPACKET.ADD_ATC or command is FSDCLIENTPACKET.ADD_PILOT:
            return self.handleAddClient(
                packet, "ATC" if command is FSDCLIENTPACKET.ADD_ATC else "PILOT"
            )
        elif command is FSDCLIENTPACKET.PLAN:
            return self.handlePlan(packet)
        elif (
            command is FSDCLIENTPACKET.REMOVE_ATC
            or command is FSDCLIENTPACKET.REMOVE_PILOT
        ):
            return self.handleRemoveClient(packet)
        elif command is FSDCLIENTPACKET.PILOT_POSITION:
            return self.handlePilotPositionUpdate(packet)
        elif command is FSDCLIENTPACKET.ATC_POSITION:
            return self.handleATCPositionUpdate(packet)
        elif command is FSDCLIENTPACKET.PONG:
            return self.handleCast(
                packet, command, require_param=2, multicast_able=True
            )
        elif command is FSDCLIENTPACKET.PING:
            if len(packet) > 1 and packet[1].lower() == b"server":
                return self.handleServerPing(packet)
            else:
                return self.handleCast(
                    packet, command, require_param=2, multicast_able=True
                )
        elif command is FSDCLIENTPACKET.MESSAGE:
            return self.handleCast(
                packet,
                command=command,
                require_param=3,
                multicast_able=True,
                custom_at_checker=broadcastMessageChecker,
            )
        elif (
            command is FSDCLIENTPACKET.REQUEST_HANDOFF
            or command is FSDCLIENTPACKET.AC_HANDOFF
        ):
            return self.handleCast(
                packet, command, require_param=3, multicast_able=False
            )
        elif command is FSDCLIENTPACKET.SB or command is FSDCLIENTPACKET.PC:
            return self.handleCast(
                packet, command, require_param=2, multicast_able=False
            )
        elif command is FSDCLIENTPACKET.WEATHER:
            return self.handleWeather(packet)
        elif command is FSDCLIENTPACKET.REQUEST_COMM:
            return self.handleCast(
                packet, command, require_param=2, multicast_able=False
            )
        elif command is FSDCLIENTPACKET.REPLY_COMM:
            return self.handleCast(
                packet, command, require_param=3, multicast_able=False
            )
        elif command is FSDCLIENTPACKET.REQUEST_ACARS:
            return self.handleAcars(packet)
        elif command is FSDCLIENTPACKET.CR:
            return self.handleCast(
                packet, command, require_param=4, multicast_able=False
            )
        elif command is FSDCLIENTPACKET.CQ:
            return self.handleCq(packet)
        elif command is FSDCLIENTPACKET.KILL:
            return self.handleKill(packet)
        else:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return ALL_FAILED_RESULT

    def connectionLost(self, _: Optional["Failure"] = None) -> None:
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
            self.factory.defer_event(
                "clientDisconnected", (self, self.client), {}, False, False, True
            )
            del self.factory.clients[self.client.callsign]
            self.client = None
        else:
            self.logger.info(f"{host} disconnected.")
