from re import compile
from typing import TYPE_CHECKING, Iterable, Union

# Not yet typed
from haversine import Unit, haversine  # type: ignore[import]

if TYPE_CHECKING:
    from ..object.client import Position

__all__ = [
    "strToInt",
    "strToFloat",
    "isCallsignVaild",
    "calcDistance",
    "joinLines",
]
__invaild_char_regex = compile("[!@#$%*:& \t]")


def strToInt(string: str, default_value: int = 0) -> int:
    try:
        return int(string)
    except ValueError:
        return default_value


def strToFloat(string: str, default_value: float = 0.0) -> float:
    try:
        return float(string)
    except ValueError:
        return default_value


def calcDistance(
    from_position: "Position", to_position: "Position", unit=Unit.NAUTICAL_MILES
) -> float:
    return haversine(from_position, to_position, unit=unit)


def isCallsignVaild(callsign: str) -> bool:
    global __invaild_char_regex
    if len(callsign) < 2 or len(callsign) > 12:
        return False
    if __invaild_char_regex.search(callsign) is not None:
        return False
    return True


def joinLines(*lines: str, newline: bool = True) -> str:
    if newline:
        return "\r\n".join(lines) + "\r\n"
    else:
        return "".join(lines)


def asciiOnly(string: Union[str, bytes]) -> bool:
    if isinstance(string, str):
        return all(ord(char) < 128 for char in string)
    else:
        return all(char < 128 for char in string)


def assertNoDuplicate(__iterable: Iterable):
    list_val = list(__iterable)
    nodup_list_val = list(set(list_val))

    if len(list_val) != len(nodup_list_val):
        for nodup_val in nodup_list_val:
            list_val.remove(nodup_val)
        raise AssertionError(f"Duplicated value: {list_val}")


def verifyConfigStruct(config: dict, structure: dict, prefix: str = "") -> None:
    def getName(obj) -> str:
        if isinstance(obj, type):
            return obj.__name__
        else:
            return type(obj).__name__

    for key, type_ in structure.items():
        if not (isinstance(type_, dict) or isinstance(type_, type)):
            raise TypeError(f"Invaild type '{type_!r}'")
        if key not in config:
            raise KeyError(f"{prefix}{key}")
        if isinstance(type_, dict):
            if not isinstance(config[key], dict):
                raise TypeError(
                    f"'{prefix}{key}' must be section, not {getName(config[key])}"
                )
            verifyConfigStruct(config[key], type_, prefix=f"{prefix}{key}.")
        elif isinstance(type_, type):
            if not isinstance(config[key], type_):
                raise TypeError(
                    f"'{prefix}{key}' must be {getName(type_)}"
                    f", not {getName(config[key])}"
                )
