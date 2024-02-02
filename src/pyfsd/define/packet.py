"""Utilies to deal with FSD packet.

Attributes:
    CLIENT_USED_COMMAND: All possibly command can be issued by user in protocol 9.
    SPLIT_SIGN: FSD client packet's split sign.
"""
from collections.abc import Sequence
from enum import Enum
from typing import (
    AnyStr,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from .utils import ascii_only

__all__ = [
    "make_packet",
    "break_packet",
    "join_lines",
    "FSDClientCommand",
    "CLIENT_USED_COMMAND",
    "CompatibleString",
    "SPLIT_SIGN",
]

_T_str = TypeVar("_T_str", str, bytes, "CompatibleString")


class CompatibleString:
    """Helper to deal with bytes and str.

    Too hard to describe, please see examples section.

    Examples::
        str1 = CompatibleString("1234")
        assert str1 + "test" == "1234test"
        assert str1 + b"test" == b"1234test"
        assert str1 + CompatibleString("test") == CompatibleString("1234test")
        assert "1" in str1
        assert b"2" in str1
        assert CompatibleString("3") in str1

    Attributes:
        string: The original ascii-only str.
    """

    string: str

    def __init__(self, value: str) -> None:
        """Create a CompatibleString instance.

        Args:
            value: The original ascii-only str.

        Raises:
            ValueError: When the value contains non-ascii characters.
        """
        if not ascii_only(value):
            raise ValueError("String can only contain ASCII characters")
        self.string = value

    def __str__(self) -> str:
        """Return str(self)."""
        return str(self.string)

    def __repr__(self) -> str:
        """Return the canonical string representation."""
        return f'CompatibleString("{self.string}")'

    def __int__(self) -> int:
        """Return int(self.string)."""
        return int(self.string)

    def __float__(self) -> float:
        """Return float(self.string)."""
        return float(self.string)

    def __complex__(self) -> complex:
        """Return complex(self.string)."""
        return complex(self.string)

    def __bytes__(self) -> bytes:
        """Convert this CompatibleString into bytes."""
        return self.string.encode()

    def __hash__(self) -> int:
        """Return hash(self.string)."""
        return hash(self.string)

    def __getnewargs__(self) -> Tuple[str]:
        """Return self.string in tuple, for pickle."""
        return (self.string[:],)

    def __eq__(self, value: object) -> bool:
        """Return self == value.

        Args:
            value: str, bytes or CompatibleString.
        """
        if isinstance(value, CompatibleString):
            return self.string == value.string
        if isinstance(value, str):
            return self.string == value
        if isinstance(value, bytes):
            return self.string.encode() == value
        return NotImplemented

    def __lt__(self, value: object) -> bool:
        """Return self < value.

        Args:
            value: str, bytes or CompatibleString.
        """
        if isinstance(value, CompatibleString):
            return self.string < value.string
        if isinstance(value, str):
            return self.string < value
        if isinstance(value, bytes):
            return self.string.encode() < value
        return NotImplemented

    def __le__(self, value: object) -> bool:
        """Return self <= value.

        Args:
            value: str, bytes or CompatibleString.
        """
        if isinstance(value, CompatibleString):
            return self.string <= value.string
        if isinstance(value, str):
            return self.string <= value
        if isinstance(value, bytes):
            return self.string.encode() <= value
        return NotImplemented

    def __gt__(self, value: object) -> bool:
        """Return self > value.

        Args:
            value: str, bytes or CompatibleString.
        """
        if isinstance(value, CompatibleString):
            return self.string > value.string
        if isinstance(value, str):
            return self.string > value
        if isinstance(value, bytes):
            return self.string.encode() > value
        return NotImplemented

    def __ge__(self, value: object) -> bool:
        """Return self >= value.

        Args:
            value: str, bytes or CompatibleString.
        """
        if isinstance(value, CompatibleString):
            return self.string >= value.string
        if isinstance(value, str):
            return self.string >= value
        if isinstance(value, bytes):
            return self.string.encode() >= value
        return NotImplemented

    def __contains__(self, part: object) -> bool:
        """Return part in self.

        Args:
            part: str, bytes or CompatibleString.
        """
        if isinstance(part, CompatibleString):
            return part.string in self.string
        if isinstance(part, str):
            return part in self.string
        if isinstance(part, bytes):
            return part in self.string.encode()
        raise TypeError(
            "'in <CompatibleString>' requires string or bytes or "
            f"CompatibleString as left operand, not {type(part).__name__}"
        )

    def __len__(self) -> int:
        """Return len(self)."""
        return len(self.string)

    def __getitem__(self, index: Union[int, slice]) -> "CompatibleString":
        """Return self[index]."""
        return self.__class__(self.string[index])

    def __add__(self, other: _T_str) -> _T_str:
        """Return self+other.

        Args:
            other: str, bytes or CompatibleString.
        """
        if isinstance(other, CompatibleString):
            return CompatibleString(self.string + other.string)
        if isinstance(other, str):
            return self.string + other
        if isinstance(other, bytes):
            return self.string.encode() + other
        return NotImplemented

    def __radd__(self, other: _T_str) -> _T_str:
        """Return other+self.

        Args:
            other: str, bytes or CompatibleString.
        """
        if isinstance(other, CompatibleString):
            return CompatibleString(other.string + self.string)
        if isinstance(other, str):
            return other + self.string
        if isinstance(other, bytes):
            return other + self.string.encode()
        return NotImplemented

    def __mul__(self, n: int) -> "CompatibleString":
        """Return self * n."""
        return self.__class__(self.string * n)

    def __rmul__(self, n: int) -> "CompatibleString":
        """Return n * self."""
        return self.__class__(self.string * n)

    def __mod__(self, args: Union[tuple, object]) -> "CompatibleString":
        """Return self % args."""
        return self.__class__(self.string % args)

    def __rmod__(self, template: _T_str) -> _T_str:
        """Return template % self."""
        # Useless?
        if isinstance(template, CompatibleString):
            # ????
            return template % self
        if isinstance(template, str):
            return template % self.string
        if isinstance(template, bytes):
            return template % self.string.encode()
        return NotImplemented

    def as_type(self, type_: Type[AnyStr]) -> AnyStr:
        """Convert this CompatibleString into specified type.

        Args:
            type_: literally str or bytes.
        """
        if type_ is str:
            return self.string  # type: ignore[return-value]
        if type_ is bytes:
            return self.string.encode()  # type: ignore[return-value]
        raise TypeError(f"Invaild string type: {type_}")


Sequence.register(CompatibleString)  # pyright: ignore
SPLIT_SIGN = CompatibleString(":")


class FSDClientCommand(CompatibleString, Enum):
    """FSD client command."""
    # __init__ = Enum.__init__  # type: ignore[assignment]
    ADD_ATC = "#AA"
    REMOVE_ATC = "#DA"
    ADD_PILOT = "#AP"
    REMOVE_PILOT = "#DP"
    REQUEST_HANDOFF = "$HO"
    MESSAGE = "#TM"
    REQUEST_WEATHER = "#RW"
    PILOT_POSITION = "@"
    ATC_POSITION = "%"
    PING = "$PI"
    PONG = "$PO"
    AC_HANDOFF = "$HA"
    PLAN = "$FP"
    SB = "#SB"
    PC = "#PC"
    WEATHER = "#WX"
    CLOUD_DATA = "#CD"
    WIND_DATA = "#WD"
    TEMP_DATA = "#TD"
    REQUEST_COMM = "$C?"
    REPLY_COMM = "$CI"
    REQUEST_ACARS = "$AX"
    REPLY_ACARS = "$AR"
    ERROR = "$ER"
    CQ = "$CQ"
    CR = "$CR"
    KILL = "$!!"
    WIND_DELTA = "#DL"


def make_packet(*parts: Union[AnyStr, FSDClientCommand]) -> AnyStr:
    """Join parts together and add split sign between every two parts."""
    result = CompatibleString("")
    for part in parts:
        result += part + SPLIT_SIGN  # type: ignore[assignment]
    if isinstance(result, FSDClientCommand):
        raise ValueError("Must have str or bytes item")
    return cast(AnyStr, result[:-1])


@overload
def break_packet(
    packet: AnyStr,
    possibly_commands: Iterable[AnyStr],
) -> Tuple[Optional[AnyStr], Tuple[AnyStr, ...]]:
    ...


@overload
def break_packet(
    packet: AnyStr,
    possibly_commands: Iterable[FSDClientCommand],
) -> Tuple[Optional[FSDClientCommand], Tuple[AnyStr, ...]]:
    ...


@overload
def break_packet(
    packet: AnyStr,
    possibly_commands: Iterable[Union[AnyStr, FSDClientCommand]],
) -> Tuple[Optional[Union[AnyStr, FSDClientCommand]], Tuple[AnyStr, ...]]:
    ...


def break_packet(
    packet: AnyStr,
    possibly_commands: Iterable[Union[AnyStr, FSDClientCommand]],
) -> Tuple[Optional[Union[AnyStr, FSDClientCommand]], Tuple[AnyStr, ...]]:
    """Break a packet into command and parts.

    #APzzz1:zzz3:zzz4
    [^][^^^^^^^^^^^^]
    command     parts

    Args:
        packet: The original packet.
        possibly_commands: All possibly commands. This function will check if packet
        starts with one of possibly commands then split it out.

    Returns:
        tuple[command or None, tuple[every_part, ...]]
    """
    packet_type = type(packet)
    command: Optional[Union[AnyStr, FSDClientCommand]] = None
    splited_packet: List[AnyStr]
    for possibly_command in possibly_commands:
        command_str: AnyStr
        if isinstance(possibly_command, FSDClientCommand):
            command_str = possibly_command.as_type(packet_type)
        else:
            command_str = possibly_command
        if packet.startswith(command_str):
            command = possibly_command
            break
    splited_packet = packet.split(SPLIT_SIGN.as_type(packet_type))  # pyright: ignore
    if command is not None:
        splited_packet[0] = splited_packet[0][len(command) :]
    return (command, tuple(splited_packet))


def join_lines(*lines: AnyStr, newline: bool = True) -> AnyStr:
    r"""Join lines together.

    Args:
        lines: The lines.
        newline: Append '\r\n' to every line or not.

    Returns:
        The result.
    """
    result = CompatibleString("")
    split_sign = CompatibleString("\r\n")
    for line in lines:
        # Ignore type errors. Just let it raise.
        result += line + split_sign if newline else line  # type: ignore[assignment]
    return cast(AnyStr, result)


CLIENT_USED_COMMAND = [
    FSDClientCommand.ADD_ATC,
    FSDClientCommand.REMOVE_ATC,
    FSDClientCommand.ADD_PILOT,
    FSDClientCommand.REMOVE_PILOT,
    FSDClientCommand.REQUEST_HANDOFF,
    FSDClientCommand.PILOT_POSITION,
    FSDClientCommand.ATC_POSITION,
    FSDClientCommand.PING,
    FSDClientCommand.PONG,
    FSDClientCommand.MESSAGE,
    FSDClientCommand.AC_HANDOFF,
    FSDClientCommand.PLAN,
    FSDClientCommand.SB,
    FSDClientCommand.PC,
    FSDClientCommand.WEATHER,
    FSDClientCommand.REQUEST_COMM,
    FSDClientCommand.REPLY_COMM,
    FSDClientCommand.REQUEST_ACARS,
    FSDClientCommand.CQ,
    FSDClientCommand.CR,
    FSDClientCommand.KILL,
]
