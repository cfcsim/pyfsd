from typing import TYPE_CHECKING, List, Optional
from weakref import ReferenceType, ref

from twisted.internet.interfaces import ITransport
from twisted.internet.task import LoopingCall
from twisted.logger import Logger
from twisted.protocols.basic import LineReceiver

from ..config import config
from ..define.errors import FSDErrors
from ..define.packet import FSDClientPacket
from ..define.utils import (
    broadcastCheckerFrom,
    broadcastPositionChecker,
    createBroadcastClientTypeChecker,
    isCallsignVaild,
    strToFloat,
    strToInt,
)
from ..object.client import Client, ClientType

if TYPE_CHECKING:
    from ..factory.client import FSDClientFactory

__all__ = ["FSDClientProtocol"]


_motd: List[str] = config.get("pyfsd", "motd").splitlines()


class FSDClientProtocol(LineReceiver):
    factory: "FSDClientFactory"
    transport: ITransport
    timeoutKiller: LoopingCall
    logger: Logger = Logger()
    this_client: ReferenceType[Client] = lambda _: None  # type: ignore

    def __init__(self, factory: "FSDClientFactory") -> None:
        self.factory = factory

    def connectionMade(self):
        self.timeoutKiller = LoopingCall(self.timeout)
        self.timeoutKiller.start(800, now=False).addCallback(self._cancelTimeoutLoop)
        self.logger.info("New connection from {ip}.", ip=self.transport.getPeer().host)

    def _cancelTimeoutLoop(self, _) -> None:
        if self.timeoutKiller.running:
            self.timeoutKiller.stop()

    def send(self, *lines: str, auto_newline: bool = True) -> None:
        buffer: str = ""
        tail = "\r\n" if auto_newline else ""
        for line in lines:
            buffer += f"{line}{tail}"
        self.transport.write(buffer.encode())  # type: ignore

    def sendError(self, errno: int, env: str = "", fatal: bool = False) -> None:
        assert not (errno < 0 and errno <= 13)
        this_client = self.this_client()
        err_str = FSDErrors.error_names[errno]
        self.send(
            FSDClientPacket.makePacket(
                FSDClientPacket.ERROR + "server",
                this_client.callsign if this_client is not None else "unknown",
                str(errno).rjust(3, "0"),
                env,
                err_str,
            )
        )
        if fatal:
            self.transport.loseConnection()

    #    def isThisClient(self, callsign: str) -> bool:
    #        if (this_client := self.this_client()) is None:
    #            return False
    #        if this_client.callsign != callsign:
    #            self.sendError(FSDErrors.ERR_SRCINVALID, env=callsign)
    #            return False
    #        return True

    def timeout(self) -> None:
        self.send("# Timeout")
        self.logger.info(
            f"{self.transport.getPeer().host} disconnected because timeout."
        )
        self.transport.loseConnection()

    def sendMotd(self) -> None:
        assert (this_client := self.this_client()) is not None
        motd_lines: List[str] = [f"#TMserver:{this_client.callsign}:PyFSD Development"]
        for line in _motd:
            motd_lines.append(
                FSDClientPacket.makePacket(
                    FSDClientPacket.MESSAGE + "server", this_client.callsign, line
                )
            )
        self.send(*motd_lines)

    def handleAddClient(self, packet: List[str], client_type: ClientType) -> None:
        req_rating: int
        protocol: int
        sim_type: Optional[int]
        if self.this_client() is not None:
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
                req_rating_str,
                protocol_str,
                sim_type_str,
                realname,
            ) = packet[:8]
            sim_type = strToInt(sim_type_str, default_value=0)
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
                req_rating_str,
                protocol_str,
            ) = packet[:7]
            sim_type = -1
        req_rating = strToInt(req_rating_str, default_value=0)
        protocol = strToInt(protocol_str, default_value=-1)
        if not isCallsignVaild(callsign):
            self.sendError(FSDErrors.ERR_CSINVALID, fatal=True)
            return
        if callsign in self.factory.clients:
            self.sendError(FSDErrors.ERR_CSINUSE)
            return
        if not protocol == 9:
            self.sendError(FSDErrors.ERR_REVISION, fatal=True)
            return
        # TODO: Auth
        # level < 0 ==> kill
        # level == 0 ==> raise FSDErrors.ERR_CSSUSPEND
        # level < req_rating ==> raise FSDErrors.ERR_LEVEL, env=req_rating and kill
        client = Client(
            client_type,
            callsign,
            req_rating,
            cid,
            protocol,
            realname,
            sim_type,
            self.transport,
        )
        self.factory.clients[callsign] = client
        self.this_client = ref(self.factory.clients[callsign])
        if client_type == "PILOT":
            self.factory.broadcast(
                # two times of req_rating --- not a typo
                FSDClientPacket.makePacket(
                    FSDClientPacket.ADD_PILOT + callsign,
                    "SERVER",
                    cid,
                    "",
                    req_rating,
                    req_rating,
                    sim_type,
                ),
                from_client=client,
            )
        else:
            self.factory.broadcast(
                FSDClientPacket.makePacket(
                    FSDClientPacket.ADD_ATC + callsign,
                    "SERVER",
                    realname,
                    cid,
                    "",
                    req_rating,
                ),
                from_client=client,
            )
        self.sendMotd()
        self.logger.info(
            "New client {callsign} from {ip}.",
            callsign=callsign,
            ip=self.transport.getPeer().host,
        )

    def handleRemoveClient(self, packet: List[str]) -> None:
        if len(packet) == 0:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if (this_client := self.this_client()) is None:
            return
        if this_client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        self.transport.loseConnection()

    def handlePlan(self, packet: List[str]) -> None:
        if len(packet) < 17:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if (this_client := self.this_client()) is None:
            return
        if this_client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        (
            plan_type,
            aircraft,
            tascruise_str,
            dep_airport,
            dep_time_str,
            act_dep_time_str,
            alt,
            dest_airport,
            hrs_enroute_str,
            min_enroute_str,
            hrs_fuel_str,
            min_fuel_str,
            alt_airport,
            remarks,
            route,
        ) = packet[2:17]
        tascruise = strToInt(tascruise_str, default_value=0)
        dep_time = strToInt(dep_time_str, default_value=0)
        act_dep_time = strToInt(act_dep_time_str, default_value=0)
        hrs_enroute = strToInt(hrs_enroute_str, default_value=0)
        min_enroute = strToInt(min_enroute_str, default_value=0)
        hrs_fuel = strToInt(hrs_fuel_str, default_value=0)
        min_fuel = strToInt(min_fuel_str, default_value=0)
        this_client.updatePlan(
            plan_type,  # type: ignore
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
        self.factory.broadcast(
            FSDClientPacket.makePacket(
                FSDClientPacket.PLAN + this_client.callsign,
                "*A",
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
            check_func=createBroadcastClientTypeChecker(to_type="ATC"),
        )

    def handlePilotPositionUpdate(self, packet: List[str]) -> None:
        if len(packet) < 10:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if (this_client := self.this_client()) is None:
            return
        if this_client.callsign != packet[1]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        (
            mode,
            _,
            transponder_str,
            _,
            lat_str,
            lon_str,
            altitdue_str,
            groundspeed_str,
            pbh_str,
            flags_str,
        ) = packet[:10]
        transponder = strToInt(transponder_str, default_value=0)
        lat = strToFloat(lat_str, default_value=0.0)
        lon = strToFloat(lon_str, default_value=0.0)
        altitdue = strToInt(altitdue_str, default_value=0)
        pbh = strToInt(pbh_str, default_value=0) & 0xFFFFFFFF
        groundspeed = strToInt(groundspeed_str, default_value=0)
        flags = strToInt(flags_str, default_value=0)
        if lat > 90.0 or lat < -90.0 or lon > 180.0 or lon < -180.0:
            self.logger.debug(
                f"Invaild position: {this_client.callsign} with {lat}, {lon}"
            )
        this_client.updatePilotPosition(
            mode, transponder, lat, lon, altitdue, groundspeed, pbh, flags
        )
        self.factory.broadcast(
            FSDClientPacket.makePacket(
                FSDClientPacket.PILOT_POSITION + mode,
                this_client.callsign,
                transponder,
                this_client.rating,
                "%.5f" % lat,
                "%.5f" % lon,
                altitdue,
                groundspeed,
                pbh,
                flags,
            ),
            check_func=broadcastPositionChecker,
        )

    def handleATCPositionUpdate(self, packet: List[str]) -> None:
        if len(packet) < 8:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if (this_client := self.this_client()) is None:
            return
        if this_client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        (
            frequency_str,
            facility_type_str,
            visual_range_str,
            _,
            lat_str,
            lon_str,
            altitdue_str,
        ) = packet[1:8]
        frequency = strToInt(frequency_str, default_value=0)
        facility_type = strToInt(facility_type_str, default_value=0)
        visual_range = strToInt(visual_range_str, default_value=0)
        lat = strToFloat(lat_str, default_value=0.0)
        lon = strToFloat(lon_str, default_value=0.0)
        altitdue = strToInt(altitdue_str, default_value=0)
        if lat > 90.0 or lat < -90.0 or lon > 180.0 or lon < -180.0:
            self.logger.debug(
                f"Invaild position: {this_client.callsign} with {lat}, {lon}"
            )
        this_client.updateATCPosition(
            frequency, facility_type, visual_range, lat, lon, altitdue
        )
        self.factory.broadcast(
            FSDClientPacket.makePacket(
                FSDClientPacket.ATC_POSITION + this_client.callsign,
                frequency,
                facility_type,
                visual_range,
                this_client.rating,
                "%.5f" % lat,
                "%.5f" % lon,
                altitdue,
            ),
            check_func=broadcastPositionChecker,
        )

    def handlePing(self, packet: List[str], is_ping: bool = True) -> None:
        packet_len: int = len(packet)
        if packet_len < 2:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if (this_client := self.this_client()) is None:
            return
        if this_client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        to_callsign = packet[1]
        if to_callsign.lower() == "server" and is_ping:
            self.send(
                FSDClientPacket.makePacket(
                    FSDClientPacket.PONG + "server",
                    this_client.callsign,
                    *packet[2:] if packet_len > 2 else [""],
                )
            )
            return
        to_checker = broadcastCheckerFrom(to_callsign)
        to_packet = FSDClientPacket.makePacket(
            FSDClientPacket.PING + this_client.callsign
            if is_ping
            else FSDClientPacket.PONG + this_client.callsign,
            to_callsign,
            *packet[2:] if packet_len > 2 else [""],
        )
        if to_checker is not None:
            self.factory.broadcast(
                to_packet, check_func=to_checker, from_client=this_client
            )
        else:
            try:
                self.factory.sendTo(to_callsign, to_packet)
            except KeyError:
                ...

    def handleMessage(self, packet: List[str]) -> None:
        packet_len: int = len(packet)
        if packet_len < 3:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if (this_client := self.this_client()) is None:
            return
        if this_client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        to_callsign = packet[1]
        to_checker = broadcastCheckerFrom(to_callsign)
        to_packet = FSDClientPacket.makePacket(
            FSDClientPacket.MESSAGE + this_client.callsign,
            to_callsign,
            *packet[2:],
        )
        if to_checker is not None:
            self.factory.broadcast(
                to_packet, check_func=to_checker, from_client=this_client
            )
        else:
            try:
                self.factory.sendTo(to_callsign, to_packet)
            except KeyError:
                ...

    def handleKill(self, packet: List[str]) -> None:
        if len(packet) < 3:
            self.sendError(FSDErrors.ERR_SYNTAX)
        if (this_client := self.this_client()) is None:
            return
        _, callsign_kill, reason = packet[:3]
        if callsign_kill not in self.factory.clients:
            self.sendError(FSDErrors.ERR_NOSUCHCS, env=callsign_kill)
            return
        if this_client.rating < 11:
            self.send(
                FSDClientPacket.makePacket(
                    FSDClientPacket.MESSAGE + "server",
                    this_client.callsign,
                    "You are not allowed to kill users!",
                )
            )
        else:
            self.send(
                FSDClientPacket.makePacket(
                    FSDClientPacket.MESSAGE + "server",
                    this_client.callsign,
                    f"Attempting to kill {callsign_kill}",
                )
            )
            self.factory.sendTo(
                callsign_kill,
                FSDClientPacket.makePacket(
                    FSDClientPacket.KILL + "SERVER", callsign_kill, reason
                ),
            )
            self.factory.clients[callsign_kill].transport.loseConnection()

    # def connectionMade(self): ...

    def lineReceived(self, byte_line: bytes) -> None:
        try:
            line: str = byte_line.decode()
        except UnicodeDecodeError:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if not line:
            return
        command, packet = FSDClientPacket.breakPacket(line)
        if command == FSDClientPacket.ADD_ATC or command == FSDClientPacket.ADD_PILOT:
            self.handleAddClient(
                packet, "ATC" if command == FSDClientPacket.ADD_ATC else "PILOT"
            )
        elif command == FSDClientPacket.PLAN:
            self.handlePlan(packet)
        elif (
            command == FSDClientPacket.REMOVE_ATC
            or command == FSDClientPacket.REMOVE_PILOT
        ):
            self.handleRemoveClient(packet)
        elif command == FSDClientPacket.PILOT_POSITION:
            self.handlePilotPositionUpdate(packet)
        elif command == FSDClientPacket.ATC_POSITION:
            self.handleATCPositionUpdate(packet)
        elif command == FSDClientPacket.PONG or command == FSDClientPacket.PING:
            self.handlePing(packet, is_ping=command == FSDClientPacket.PING)
        elif command == FSDClientPacket.MESSAGE:
            self.handleMessage(packet)
        elif command == FSDClientPacket.REQUEST_HANDOFF:
            ...
        elif command == FSDClientPacket.AC_HANDOFF:
            ...
        elif command == FSDClientPacket.SB:
            ...
        elif command == FSDClientPacket.PC:
            ...
        elif command == FSDClientPacket.WEATHER:
            ...
        elif command == FSDClientPacket.REQUEST_COMM:
            ...
        elif command == FSDClientPacket.REPLY_COMM:
            ...
        elif command == FSDClientPacket.REQUEST_ACARS:
            ...
        elif command == FSDClientPacket.CR:
            ...
        elif command == FSDClientPacket.CQ:
            ...
        elif command == FSDClientPacket.KILL:
            self.handleKill(packet)
        else:
            self.sendError(FSDErrors.ERR_SYNTAX)

    def connectionLost(self, _) -> None:
        self._cancelTimeoutLoop(None)
        host: str = self.transport.getPeer().host
        if (this_client := self.this_client()) is not None:
            self.logger.info(f"{host} ({this_client.callsign}) disconnected.")
            self.factory.broadcast(
                FSDClientPacket.makePacket(
                    FSDClientPacket.REMOVE_ATC + this_client.callsign
                    if this_client.type == "ATC"
                    else FSDClientPacket.REMOVE_PILOT + this_client.callsign,
                    this_client.cid,
                )
            )
            del self.factory.clients[this_client.callsign]
        else:
            self.logger.info(f"{host} disconnected.")

    def dataReceived(self, data) -> None:
        self.timeoutKiller.reset()
        super().dataReceived(data)
