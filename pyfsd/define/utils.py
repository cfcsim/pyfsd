from re import compile
from typing import TYPE_CHECKING, AnyStr, Callable, Iterable, Tuple, Type, Union, cast

# Not yet typed
from haversine import Unit, haversine

if TYPE_CHECKING:
    from constantly import ValueConstant

    from ..object.client import Position

__all__ = [
    "constToAnyStr",
    "strToInt",
    "strToFloat",
    "isCallsignVaild",
    "calcDistance",
    "joinLines",
    "verifyConfigStruct",
    "asciiOnly",
    "assertNoDuplicate",
    "iterCallable",
    "MRand",
    "MayExist",
    "LiteralValue",
    "UnionType",
]
__str_invaild_char_regex = compile("[!@#$%*:& \t]")
__bytes_invaild_char_regex = compile(b"[!@#$%*:& \t]")


def constToAnyStr(
    type_: Type[AnyStr],
    value: "ValueConstant",
    encoding: str = "ascii",
    errors: str = "strict",
) -> AnyStr:
    if type_ is str:
        return cast(AnyStr, value.value)
    elif type_ is bytes:
        return cast(AnyStr, value.value.encode(encoding, errors))
    else:
        raise TypeError


def strToInt(string: Union[str, bytes], default_value: int = 0) -> int:
    try:
        return int(string)
    except ValueError:
        return default_value


def strToFloat(string: Union[str, bytes], default_value: float = 0.0) -> float:
    try:
        return float(string)
    except ValueError:
        return default_value


def calcDistance(
    from_position: "Position", to_position: "Position", unit: Unit = Unit.NAUTICAL_MILES
) -> float:
    return cast(float, haversine(from_position, to_position, unit=unit))


def isCallsignVaild(callsign: Union[str, bytes]) -> bool:
    global __str_invaild_char_regex, __bytes_invaild_char_regex
    if len(callsign) < 2 or len(callsign) > 12:
        return False
    if (  # type: ignore[attr-defined]
        __str_invaild_char_regex
        if type(callsign) is str
        else __bytes_invaild_char_regex
    ).search(
        callsign  # pyright: ignore
    ) is not None:
        return False
    return True


def joinLines(*lines: AnyStr, newline: bool = True) -> AnyStr:
    # How terrible! but I think it'll be faster than before.
    result: AnyStr = cast(AnyStr, None)
    split_sign: AnyStr
    for line in lines:
        if result is None:
            result = (line_type := type(line))()
            if line_type is str:
                split_sign = cast(AnyStr, "\r\n")
            elif line_type is bytes:
                split_sign = cast(AnyStr, b"\r\n")
            else:
                raise TypeError(f"Invaild type {line_type!r}")
        result += line  # pyright: ignore
        if newline:
            result += split_sign  # pyright: ignore
    return result


def asciiOnly(string: Union[str, bytes]) -> bool:
    if isinstance(string, str):
        return all(ord(char) < 128 for char in string)
    else:
        return all(char < 128 for char in string)


def assertNoDuplicate(__iterable: Iterable) -> None:
    list_val = list(__iterable)
    nodup_list_val = list(set(list_val))

    if len(list_val) != len(nodup_list_val):
        for nodup_val in nodup_list_val:
            list_val.remove(nodup_val)
        raise AssertionError(f"Duplicated value: {list_val}")


class UnionType:
    types: Tuple[Union[Type, dict], ...]

    def __init__(self, *args: Union[Type, dict]) -> None:
        have_dict = False
        for arg in args:
            if not isinstance(arg, (type, dict)):
                raise TypeError(
                    "UnionType(arg, ...): arg must be a type or dict. "
                    f"Got {arg!r:.100}."
                )
            elif isinstance(arg, dict):
                assert not have_dict
                have_dict = True
        self.types = args

    def __class_getitem__(cls, *args: Union[Type, dict]) -> "UnionType":
        return cls(*args)

    def __repr__(self) -> str:
        return f"UnionType{self.types!r}"


class LiteralValue:
    values: Tuple[object, ...]

    def __init__(self, *args: object) -> None:
        self.values = args

    def __class_getitem__(cls, *args: object) -> "LiteralValue":
        return cls(*args)

    def __repr__(self) -> str:
        return f"LiteralValue{self.values!r}"


class MayExist:
    type: Union[Type, dict, UnionType, LiteralValue]

    def __init__(self, arg: Union[Type, dict, UnionType, LiteralValue]) -> None:
        if not isinstance(arg, (type, dict, UnionType, LiteralValue)):
            raise TypeError(
                "MayExist(arg): arg must be a type or dict or UnionType or "
                f"LiteralValue. Got {arg!r}."
            )
        self.type = arg

    def __class_getitem__(
        cls, arg: Union[Type, dict, UnionType, LiteralValue]
    ) -> "MayExist":
        return cls(arg)

    def __repr__(self) -> str:
        name = self.type.__name__ if isinstance(self.type, type) else repr(self.type)
        return f"MayExist({name})"


def verifyConfigStruct(config: dict, structure: dict, prefix: str = "") -> None:
    def explainType(obj: object) -> str:
        if isinstance(obj, type):
            return f"literally {obj.__name__}"
        elif isinstance(obj, dict):
            return "section"
        else:
            return type(obj).__name__

    for key, type_ in structure.items():
        try:
            value = config[key]
        except KeyError:
            if isinstance(type_, MayExist):
                continue
            else:
                raise KeyError(f"{prefix}{key}")
        else:
            if isinstance(type_, MayExist):
                type_ = type_.type
        if isinstance(type_, type):
            if not isinstance(value, type_):
                raise TypeError(
                    f"'{prefix}{key}' must be {type_.__name__}"
                    f", not {explainType(value)}"
                )
        elif isinstance(type_, dict):
            if not isinstance(config[key], dict):
                raise TypeError(
                    f"'{prefix}{key}' must be section, not {explainType(value)}"
                )
            verifyConfigStruct(value, type_, prefix=f"{prefix}{key}.")
        elif isinstance(type_, LiteralValue):
            if value not in type_.values:
                raise ValueError(
                    f"'{prefix}{key}' must be literally "
                    + " or ".join(repr(val) for val in type_.values)
                    + f", not {explainType(value)}"
                )
        elif isinstance(type_, UnionType):
            succeed = False
            for may_type in type_.types:
                if isinstance(may_type, type):
                    if isinstance(value, may_type):
                        succeed = True
                        break
                elif isinstance(may_type, dict):
                    if isinstance(value, dict):
                        verifyConfigStruct(value, may_type, prefix=f"{prefix}{key}.")
                        succeed = True
                        break
            if not succeed:
                raise TypeError(
                    f"'{prefix}{key}' must be "
                    + " or ".join(explainType(may_type) for may_type in type_.types)
                    + f", not {explainType(value)}"
                )
        else:
            raise TypeError(f"Invaild type: {explainType(type_)}")


def iterCallable(obj: object, ignore_private: bool = True) -> Iterable[Callable]:
    for attr_name in dir(obj):
        if ignore_private and attr_name.startswith("_"):
            continue
        attr = getattr(obj, attr_name)
        if hasattr(attr, "__call__"):
            yield attr


class MRand:
    mrandseed: int = 0

    def __call__(self) -> int:
        self.mrandseed ^= 0x22591D8C
        part1 = (self.mrandseed << 1) & 0xFFFFFFFF
        part2 = self.mrandseed >> 31
        self.mrandseed ^= part1 | part2
        # self.mrandseed &= 0xFFFFFFFF
        return self.mrandseed

    def srand(self, seed: int) -> None:
        self.mrandseed = seed
