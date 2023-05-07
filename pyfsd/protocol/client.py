from typing import TYPE_CHECKING, List, Optional

from twisted.internet import reactor
from twisted.internet.interfaces import ITransport
from twisted.logger import Logger
from twisted.protocols.basic import LineReceiver

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
from ..define.packet import FSDClientPacket
from ..define.utils import isCallsignVaild, joinLines, strToFloat, strToInt
from ..object.client import Client, ClientType

if TYPE_CHECKING:
    from metar.Metar import Metar
    from twisted.internet.base import DelayedCall

    from ..factory.client import FSDClientFactory

__all__ = ["FSDClientProtocol"]


class FSDClientProtocol(LineReceiver):
    factory: "FSDClientFactory"
    transport: ITransport
    timeoutKiller: "DelayedCall"
    logger: Logger = Logger()
    client: Optional[Client] = None

    def connectionMade(self):
        self.timeoutKiller = reactor.callLater(800, self.timeout)  # type: ignore
        self.logger.info("New connection from {ip}.", ip=self.transport.getPeer().host)

    def send(self, *lines: str, auto_newline: bool = True) -> None:
        self.transport.write(
            joinLines(*lines, newline=auto_newline).encode()  # type: ignore
        )

    def sendError(self, errno: int, env: str = "", fatal: bool = False) -> None:
        assert not (errno < 0 and errno <= 13)
        err_str = FSDErrors.error_names[errno]
        self.send(
            FSDClientPacket.makePacket(
                FSDClientPacket.ERROR + "server",
                self.client.callsign if self.client is not None else "unknown",
                f"{errno:03d}",  # = str(errno).rjust(3, "0")
                env,
                err_str,
            )
        )
        if fatal:
            self.transport.loseConnection()

    def timeout(self) -> None:
        self.send("# Timeout")
        self.transport.loseConnection()

    def sendMotd(self) -> None:
        assert self.client is not None
        motd_lines: List[str] = [f"#TMserver:{self.client.callsign}:PyFSD Development"]
        for line in self.factory.motd:
            motd_lines.append(
                FSDClientPacket.makePacket(
                    FSDClientPacket.MESSAGE + "server", self.client.callsign, line
                )
            )
        self.send(*motd_lines)

    def multicast(
        self,
        to_limit: str,
        *lines: str,
        custom_at_checker: Optional[BroadcastChecker] = None,
    ) -> None:
        assert self.client is not None
        if to_limit == "*":
            self.factory.broadcast(*lines, from_client=self.client)
        elif to_limit == "*A":
            self.factory.broadcast(
                *lines, check_func=allATCChecker, from_client=self.client
            )
        elif to_limit == "*P":
            self.factory.broadcast(
                *lines, check_func=allPilotChecker, from_client=self.client
            )
        elif to_limit.startswith("@"):
            self.factory.broadcast(
                *lines,
                from_client=self.client,
                check_func=custom_at_checker
                if custom_at_checker is not None
                else atChecker,
            )
        else:
            raise NotImplementedError

    def unicast(self, callsign: str, *lines: str) -> None:
        self.factory.sendTo(callsign, *lines)

    def handleCast(
        self,
        packet: List[str],
        command: str,
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
        to_packet = FSDClientPacket.makePacket(
            command + self.client.callsign,
            to_callsign,
            *packet[2:] if packet_len > 2 else [""],
        )
        if isMulticast(to_callsign):
            if multicast_able:
                self.multicast(
                    to_callsign, to_packet, custom_at_checker=custom_at_checker
                )
        else:
            self.factory.sendTo(to_callsign, to_packet)

    def handleAddClient(self, packet: List[str], client_type: ClientType) -> None:
        req_rating: int
        protocol: int
        sim_type: Optional[int]
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
        if len(req_rating_str) == 0:
            req_rating = 1
        else:
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

        def onResult(result):
            rating: int = result[1].rating
            if rating == 0:
                self.sendError(FSDErrors.ERR_CSSUSPEND, fatal=True)
            else:
                if rating < req_rating:
                    self.sendError(FSDErrors.ERR_LEVEL, env=f"{req_rating}", fatal=True)
                else:
                    onSuccess()

        def onFail(_):
            self.sendError(FSDErrors.ERR_CIDINVALID, env=cid, fatal=True)

        def onSuccess():
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
            self.client = client
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

        self.factory.login(cid, password).addCallback(onResult).addErrback(onFail)

    def handleRemoveClient(self, packet: List[str]) -> None:
        if len(packet) == 0:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        self.transport.loseConnection()

    def handlePlan(self, packet: List[str]) -> None:
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
        plan_type = plan_type[0] if len(plan_type) > 0 else None
        tascruise = strToInt(tascruise_str, default_value=0)
        dep_time = strToInt(dep_time_str, default_value=0)
        act_dep_time = strToInt(act_dep_time_str, default_value=0)
        hrs_enroute = strToInt(hrs_enroute_str, default_value=0)
        min_enroute = strToInt(min_enroute_str, default_value=0)
        hrs_fuel = strToInt(hrs_fuel_str, default_value=0)
        min_fuel = strToInt(min_fuel_str, default_value=0)
        self.client.updatePlan(
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
                FSDClientPacket.PLAN + self.client.callsign,
                "*A",
                "",
            )
            if plan_type is None
            else FSDClientPacket.makePacket(
                FSDClientPacket.PLAN + self.client.callsign,
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
            check_func=allATCChecker,
            from_client=self.client,
        )

    def handlePilotPositionUpdate(self, packet: List[str]) -> None:
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
                f"Invaild position: {self.client.callsign} with {lat}, {lon}"
            )
        self.client.updatePilotPosition(
            mode, transponder, lat, lon, altitdue, groundspeed, pbh, flags
        )
        self.timeoutKiller.reset(800)
        self.factory.broadcast(
            FSDClientPacket.makePacket(
                FSDClientPacket.PILOT_POSITION + mode,
                self.client.callsign,
                transponder,
                self.client.rating,
                "%.5f" % lat,
                "%.5f" % lon,
                altitdue,
                groundspeed,
                pbh,
                flags,
            ),
            check_func=broadcastPositionChecker,
            from_client=self.client,
        )

    def handleATCPositionUpdate(self, packet: List[str]) -> None:
        if len(packet) < 8:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
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
                f"Invaild position: {self.client.callsign} with {lat}, {lon}"
            )
        self.client.updateATCPosition(
            frequency, facility_type, visual_range, lat, lon, altitdue
        )
        self.timeoutKiller.reset(800)
        self.factory.broadcast(
            FSDClientPacket.makePacket(
                FSDClientPacket.ATC_POSITION + self.client.callsign,
                frequency,
                facility_type,
                visual_range,
                self.client.rating,
                "%.5f" % lat,
                "%.5f" % lon,
                altitdue,
            ),
            check_func=broadcastPositionChecker,
            from_client=self.client,
        )

    def handleServerPing(self, packet: List[str]) -> None:
        packet_len: int = len(packet)
        if packet_len < 2:
            self.sendError(FSDErrors.ERR_SYNTAX)
            return
        if self.client is None:
            return
        if self.client.callsign != packet[0]:
            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
            return
        self.send(
            FSDClientPacket.makePacket(
                FSDClientPacket.PONG + "server",
                self.client.callsign,
                *packet[2:] if packet_len > 2 else [""],
            )
        )

    # Hard to implement
    #    def handleWeather(self, packet: List[str]) -> None:
    #        if len(packet) < 3:
    #            self.sendError(FSDErrors.ERR_SYNTAX)
    #        if self.client is None:
    #            return
    #        if self.client.callsign != packet[0]:
    #            self.sendError(FSDErrors.ERR_SRCINVALID, env=packet[0])
    #            return
    #
    #        def sendMetar(metar: Optional["Metar"]) -> None:
    #            assert self.client is not None
    #            if metar is None:
    #                self.sendError(FSDErrors.ERR_NOWEATHER, packet[3])
    #            else:
    #                packets = []
    #
    #        self.factory.fetch_metar(packet[3]).addCallback(sendMetar)

    def handleAcars(self, packet: List[str]) -> None:
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
                    self.send(
                        FSDClientPacket.makePacket(
                            FSDClientPacket.REPLY_ACARS + "server",
                            self.client.callsign,
                            "METAR",
                            metar.code,
                        )
                    )

            self.factory.fetch_metar(packet[3]).addCallback(sendMetar)

    def handleCq(self, packet: List[str]) -> None:
        # Behavior may differ from FSD.
        if len(packet) < 3:
            self.sendError(FSDErrors.ERR_SYNTAX)
        if self.client is None:
            return
        if packet[1].upper() != "SERVER":
            self.handleCast(
                packet, FSDClientPacket.CQ, require_param=3, multicast_able=True
            )
            return
        elif packet[2].lower() == "fp":
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
            self.send(
                FSDClientPacket.makePacket(
                    FSDClientPacket.PLAN,
                    callsign,
                    self.client.callsign,
                    plan.type,
                    plan.aircraft,
                    plan.tascruise,
                    plan.dep_airport,
                    plan.dep_time,
                    plan.act_dep_time,
                    plan.alt,
                    plan.dest_airport,
                    plan.hrs_enroute,
                    plan.min_enroute,
                    plan.hrs_fuel,
                    plan.min_fuel,
                    plan.alt_airport,
                    plan.remarks,
                    plan.route,
                )
            )
        elif packet[2].upper() == "RN":
            # This part won't execute except a client named 'server'
            callsign = packet[1]
            if (client := self.factory.clients.get(callsign)) is not None:
                self.send(
                    FSDClientPacket.makePacket(
                        FSDClientPacket.CR,
                        callsign,
                        self.client.callsign,
                        "RN",
                        client.realname,
                        "USER",
                        client.rating,
                    )
                )

    def handleKill(self, packet: List[str]) -> None:
        if len(packet) < 3:
            self.sendError(FSDErrors.ERR_SYNTAX)
        if self.client is None:
            return
        _, callsign_kill, reason = packet[:3]
        if callsign_kill not in self.factory.clients:
            self.sendError(FSDErrors.ERR_NOSUCHCS, env=callsign_kill)
            return
        if self.client.rating < 11:
            self.send(
                FSDClientPacket.makePacket(
                    FSDClientPacket.MESSAGE + "server",
                    self.client.callsign,
                    "You are not allowed to kill users!",
                )
            )
        else:
            self.send(
                FSDClientPacket.makePacket(
                    FSDClientPacket.MESSAGE + "server",
                    self.client.callsign,
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
        elif command == FSDClientPacket.PONG:
            self.handleCast(packet, command, require_param=2, multicast_able=True)
        elif command == FSDClientPacket.PING:
            if len(packet) > 1 and packet[1].lower() == "server":
                self.handleServerPing(packet)
            else:
                self.handleCast(packet, command, require_param=2, multicast_able=True)
        elif command == FSDClientPacket.MESSAGE:
            self.handleCast(
                packet,
                command=command,
                require_param=3,
                multicast_able=True,
                custom_at_checker=broadcastMessageChecker,
            )
        elif (
            command == FSDClientPacket.REQUEST_HANDOFF
            or command == FSDClientPacket.AC_HANDOFF
        ):
            self.handleCast(packet, command, require_param=3, multicast_able=False)
        elif command == FSDClientPacket.SB or command == FSDClientPacket.PC:
            self.handleCast(packet, command, require_param=2, multicast_able=False)
        elif command == FSDClientPacket.WEATHER:
            ...
        elif command == FSDClientPacket.REQUEST_COMM:
            self.handleCast(packet, command, require_param=2, multicast_able=False)
        elif command == FSDClientPacket.REPLY_COMM:
            self.handleCast(packet, command, require_param=3, multicast_able=False)
        elif command == FSDClientPacket.REQUEST_ACARS:
            self.handleAcars(packet)
        elif command == FSDClientPacket.CR:
            self.handleCast(packet, command, require_param=4, multicast_able=False)
        elif command == FSDClientPacket.CQ:
            self.handleCq(packet)
        elif command == FSDClientPacket.KILL:
            self.handleKill(packet)
        else:
            self.sendError(FSDErrors.ERR_SYNTAX)

    def connectionLost(self, _) -> None:
        if self.timeoutKiller.active():
            self.timeoutKiller.cancel()
        host: str = self.transport.getPeer().host
        if self.client is not None:
            self.logger.info(f"{host} ({self.client.callsign}) disconnected.")
            self.factory.broadcast(
                FSDClientPacket.makePacket(
                    FSDClientPacket.REMOVE_ATC + self.client.callsign
                    if self.client.type == "ATC"
                    else FSDClientPacket.REMOVE_PILOT + self.client.callsign,
                    self.client.cid,
                ),
                from_client=self.client,
            )
            del self.client
        else:
            self.logger.info(f"{host} disconnected.")
