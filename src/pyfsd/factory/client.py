"""Protocol factory -- client."""
# from ..protocol.client import ClientProtocol
from asyncio import create_task
from asyncio import sleep as asleep
from hashlib import sha256
from random import randint
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    NoReturn,
    Optional,
    Tuple,
    cast,
)

from argon2 import PasswordHasher, exceptions
from sqlalchemy import select, update

from ..db_tables import users_table
from ..define.packet import FSDClientCommand, join_lines, make_packet
from ..protocol.client import ClientProtocol

if TYPE_CHECKING:
    from asyncio import Task

    from sqlalchemy.ext.asyncio import AsyncEngine

    from ..define.broadcast import BroadcastChecker
    from ..metar.manager import MetarManager
    from ..object.client import Client
    from ..plugin.manager import PyFSDPluginManager

__all__ = ["ClientFactory"]


class ClientFactory:
    """Factory of ClientProtocol.

    Attributes:
        clients: All clients, Dict[callsign(bytes), Client]
        heartbeat_task: Task to send heartbeat to clients.
        motd: The Message Of The Day.
        metar_manager: The metar manager.
        plugin_manager: The PyFSD plugin manager.
        db_engine: Async sqlalchemy engine.
        password_hasher: Argon2 password hasher.
    """

    clients: Dict[bytes, "Client"]
    heartbeat_task: "Task[NoReturn] | None"
    metar_manager: "MetarManager"
    plugin_manager: "PyFSDPluginManager"
    db_engine: "AsyncEngine"
    motd: List[bytes]
    password_hasher: "PasswordHasher"

    def __init__(
        self,
        motd: bytes,
        metar_manager: "MetarManager",
        plugin_manager: "PyFSDPluginManager",
        db_engine: "AsyncEngine",
    ) -> None:
        """Create a ClientFactory instance."""
        self.clients = {}
        self.heartbeat_task = None
        self.motd = motd.splitlines()
        self.metar_manager = metar_manager
        self.plugin_manager = plugin_manager
        self.db_engine = db_engine
        self.password_hasher = PasswordHasher()

    def get_heartbeat_task(self) -> "Task[NoReturn]":
        """Get heartbeat task."""
        if self.heartbeat_task is not None:
            return self.heartbeat_task

        async def heartbeater() -> NoReturn:
            while True:
                await asleep(70)
                self.heartbeat()

        self.heartbeat_task = create_task(heartbeater())
        return self.heartbeat_task

    def heartbeat(self) -> None:
        """Send heartbeat to clients."""
        random_int: int = randint(-214743648, 2147483647)  # noqa: S311
        self.broadcast(
            make_packet(
                FSDClientCommand.WIND_DELTA + "SERVER",
                "*",
                f"{random_int % 11 - 5}",
                f"{random_int % 21 - 10}",
            ).encode("ascii"),
        )

    def __call__(self) -> ClientProtocol:
        """Create a ClientProtocol instance."""
        return ClientProtocol(self)

    def broadcast(
        self,
        *lines: bytes,
        check_func: "BroadcastChecker" = lambda _, __: True,
        auto_newline: bool = True,
        from_client: Optional["Client"] = None,
    ) -> bool:
        """Broadcast a message.

        Args:
            lines: Lines to be broadcasted.
            check_func: Function to check if message should be sent to a client.
            auto_newline: Auto put newline marker between lines or not.
            from_client: Where the message from.

        Return:
            Lines sent to at least client or not.
        """
        have_one = False
        data = join_lines(*lines, newline=auto_newline)
        for client in self.clients.values():
            if client == from_client:
                continue
            if not check_func(from_client, client):
                continue
            have_one = True
            if not client.transport.is_closing():
                client.transport.write(data)
        return have_one

    def send_to(
        self, callsign: bytes, *lines: bytes, auto_newline: bool = True
    ) -> bool:
        """Send lines to a specified client.

        Args:
            callsign: The client's callsign.
            lines: Lines to be broadcasted.
            auto_newline: Auto put newline marker between lines or not.

        Returns:
            Is there a client called {callsign} (and is message sent or not).
        """
        data = join_lines(*lines, newline=auto_newline)
        try:
            self.clients[callsign].transport.write(data)
            return True
        except KeyError:
            return False

    async def check_auth(self, username: str, password: str) -> Optional[int]:
        """Check if password and username is correct."""

        async def update_hashed() -> None:
            async with self.db_engine.begin() as conn:
                await conn.execute(
                    update(users_table)
                    .where(users_table.c.callsign == username)
                    .values(password=new_hashed)
                )

        async with self.db_engine.begin() as conn:
            infos = tuple(
                await conn.execute(
                    select(users_table.c.password, users_table.c.rating).where(
                        users_table.c.callsign == username
                    )
                )
            )
        if len(infos) == 0:
            return None
        if len(infos) != 1:
            raise RuntimeError(f"Repeated callsign in users database: {username}")
        hashed, rating = cast(Tuple[str, int], infos[0])
        # --------- Helper to convert sha256 into argon2
        if len(hashed) == 64:
            if sha256(password.encode()).hexdigest() == hashed:
                # Now we have plain password, convert it into argon2
                new_hashed = self.password_hasher.hash(password)
                await update_hashed()
                return rating
            return None
        # --------- Delete this part later!
        try:
            self.password_hasher.verify(hashed, password)
        except exceptions.VerifyMismatchError:
            return None
        if self.password_hasher.check_needs_rehash(hashed):
            await update_hashed()
        return rating
