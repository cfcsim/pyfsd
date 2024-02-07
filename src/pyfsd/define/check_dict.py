"""Tools to perform runtime TypedDict type check.

It can be used to perform config check.
Only TypedDict, Literal, NotRequired, Union, List and Dict are supported.

Example::
    check_simple_type(1, Union[int, str])
    check_dict({ "a": 1 }, TypedDict("A", { "a": int }))
"""
from sys import version_info
from typing import (
    Hashable,
    Iterable,
    Literal,
    Mapping,
    Tuple,
    Type,
    TypeAlias,
    TypedDict,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

if version_info >= (3, 11):
    from typing import NotRequired, is_typeddict  # type: ignore[attr-defined]

    new_get_type_hints = get_type_hints
else:
    from typing_extensions import NotRequired, is_typeddict
    from typing_extensions import (  # type: ignore[assignment]
        get_type_hints as new_get_type_hints,
    )

from .utils import is_empty_iterable

__all__ = [
    "explain_type",
    "VerifyKeyError",
    "VerifyTypeError",
    "check_simple_type",
    "assert_simple_type",
    "lookup_required",
    "check_dict",
    "assert_dict",
]

# Currently we have no choice to make Literal[...] works, so temporaily type it as Any
TypeHint: TypeAlias = object  # Union[TypeAlias, Type]


def explain_type(typ: TypeHint) -> str:
    """Explain a type.

    Args:
        typ: The type to be explained.

    Returns:
        Description of the type.

    Raises:
        TypeError: When a unsupported/invaild type passed.
    """
    if is_typeddict(typ):
        return "dict"
    if type_origin := get_origin(typ):  # elif (t_o is not None)
        if type_origin is Union:
            return " or ".join(explain_type(sub_type) for sub_type in get_args(typ))
        if type_origin is Literal:
            return " or ".join(repr(sub_value) for sub_value in get_args(typ))
        if type_origin in (list, dict):
            return str(typ)[len(typ.__module__) + 1 :]
        msg = f"Unsupported type: {type_origin!r}"
        raise TypeError(msg)
    if isinstance(typ, type):
        return typ.__name__
    msg = f"Invaild type: {typ!r}"
    raise TypeError(msg)


class VerifyTypeError(TypeError):
    """A exception describes a value does not match specified type.

    Attritubes:
        name: The name of this value.
        excepted: The expected type.
        actually: The actually value.
    """

    name: str
    excepted: TypeHint
    actually: object

    def __init__(self, name: str, excepted: TypeHint, actually: object) -> None:
        """Create a VerifyTypeError instance.

        Args:
            name: The name of the value.
            excepted: The expected type.
            actually: The actually value.
        """
        self.name = name
        self.excepted = excepted
        self.actually = actually
        super().__init__(name, excepted, actually)

    def __str__(self) -> str:
        """Format a VerifyTypeError to string.

        Returns:
            The formated string, includes name, expected type and actually value
        """
        return (
            f"'{self.name}' must be {explain_type(self.excepted)}"
            f", not {type(self.actually).__name__}"
        )

    def __eq__(self, other: object) -> bool:
        """Check if another object equals to this ConfigTypeError.

        Returns:
            Equals or not.
        """
        if isinstance(other, VerifyTypeError):
            return (
                self.name == other.name
                and self.excepted == other.excepted
                and self.actually == other.actually
            )
        return NotImplemented


class VerifyKeyError(KeyError):
    """A exception describes a key missing/leftover in a dict.

    Attritubes:
        dict_name: The dict name.
        key: The key name.
        type: Type of error, a missing or leftover key found.
    """

    dict_name: str
    key: Hashable
    type: Literal["missing", "leftover"]  # noqa: A003

    def __init__(
        self, dict_name: str, key: Hashable, type_: Literal["missing", "leftover"]
    ) -> None:
        """Create a VerifyKeyError instance.

        Args:
            dict_name: The dict name.
            key: The key name.
            type_: Type of error, a missing or leftover key found.
        """
        self.dict_name = dict_name
        self.key = key
        self.type = type_
        super().__init__(dict_name, key, type_)

    def __str__(self) -> str:
        """Format a VerifyKeyError to string.

        Returns:
            The formated string, includes name, error type
        """
        return f"{self.dict_name}[{self.key!r}] {self.type}"

    def __eq__(self, other: object) -> bool:
        """Check if another object equals to this ConfigKeyError.

        Returns:
            Equals or not.
        """
        if isinstance(other, VerifyKeyError):
            return self.dict_name == other.dict_name and self.type == other.type
        return NotImplemented


def check_simple_type(
    obj: object,
    typ: TypeHint,
    name: str = "object",
) -> Iterable[VerifyTypeError]:
    """Simple runtime type checker, supports Union, Literal, List, Dict.

    Args:
        obj: The object to be verified.
        typ: The expected type. Union, Literal, List, Dict or runtime checkable type
        name: Name of the object.

    Yields:
        When a type error was detected.

    Raises:
        TypeError: When a unsupported type is specified.
    """
    if type_origin := get_origin(typ):  # elif (t_o is not None)
        if type_origin is Union:
            for sub_type in get_args(typ):
                if is_empty_iterable(check_simple_type(obj, sub_type, name=name)):
                    return
            yield VerifyTypeError(name, typ, obj)
        elif type_origin is Literal:
            if obj not in get_args(typ):
                yield VerifyTypeError(name, typ, obj)
        elif type_origin is list:
            if not isinstance(obj, list):
                yield VerifyTypeError(name, typ, obj)
                return
            for i, val in enumerate(obj):
                yield from check_simple_type(
                    val,
                    get_args(typ)[0],
                    name=f"{name}[{i}]",
                )
        elif type_origin is dict:
            if not isinstance(obj, dict):
                yield VerifyTypeError(name, typ, obj)
                return
            key_type, value_type = get_args(typ)
            for key, value in obj.items():
                # TODO: Better description of key
                yield from check_simple_type(
                    key,
                    key_type,
                    name=f"{name}[{key!r}]",
                )
                yield from check_simple_type(
                    value,
                    value_type,
                    name=f"{name}[{key!r}]",
                )
        else:
            msg = f"Unsupported type: {type_origin!r}"
            raise TypeError(msg)
    elif isinstance(typ, type):
        if not isinstance(obj, typ):
            yield VerifyTypeError(name, typ, obj)
    else:
        msg = f"Invaild type: {typ!r}"
        raise TypeError(msg)


def assert_simple_type(
    obj: object,
    typ: TypeHint,
    name: str = "object",
) -> None:
    """Wrapper of check_simple_type, but raise first error.

    Simple runtime type checker, supports Union, Literal, List, Dict.

    Args:
        obj: The object to be verified.
        typ: The expected type. Union, Literal, List, Dict or runtime checkable type
        name: Name of the object.

    Raises:
        VerifyTypeError: When a type error detected.
        TypeError: When a unsupported type is specified.
    """
    try:
        error = next(iter(check_simple_type(obj, typ, name)))
    except StopIteration:
        pass
    else:
        raise error


DictStructure = Union[
    Type[TypedDict],  # type: ignore[valid-type]
    Mapping,  # It should be Mapping[Hashable, Union[TypeHint, DictStructure]
    # (but it's invariant)
]


def lookup_required(structure: DictStructure) -> Iterable[Hashable]:
    """Yields all required key in a TypedDict.

    Args:
        structure: The type structure, TypedDict or dict.

    Yields:
        Keys that are required. In normal usage, str was yielded.
    """
    if is_typeddict(structure):
        # Python < 3.8 not supported
        # ---------
        # Mypy bug, ignore it
        if not structure.__total__:  # type: ignore[union-attr]
            # Nothing is required
            return
        if hasattr(structure, "__required_keys__"):
            if (
                NotRequired.__module__ == "typing"
            ):  # Python 3.11+, not need to Workaround
                yield from structure.__required_keys__  # type: ignore[union-attr]
                return
            # Python 3.9, 3.10
            type_hints = get_type_hints(structure)
            for may_required_keys in structure.__required_keys__:  # type: ignore[union-attr]
                if get_origin(type_hints[may_required_keys]) is not NotRequired:
                    yield may_required_keys
        else:
            # Python 3.8
            for key, typ in get_type_hints(structure).items():
                if get_origin(typ) is not NotRequired:
                    yield key
    else:
        for may_required_keys, type_ in structure.items():  # type: ignore[union-attr]
            if get_origin(type_) is not NotRequired:
                yield may_required_keys


def check_dict(
    dict_obj: dict,
    structure: DictStructure,
    name: str = "dict",
    allow_unexpected_key: bool = False,
) -> Iterable[Union[VerifyTypeError, VerifyKeyError]]:
    """Check type of a dict accord TypedDict.

    Args:
        dict_obj: The dict to be checked.
        structure: Expected type.
        name: Name of the dict.
        allow_unexpected_key: Allow leftover keys in dict_obj. Example::
            class AType(TypedDict):
                a: int
            check_dict(
                { "a": 114514 }, AType,
                allow_unexpected_key=False
            ) # Okay
            check_dict(
                { "a": 114514, "b": 1919810 }, AType,
                allow_unexpected_key=True
            ) # Okay
            check_dict(
                { "a": 114514, "b": 1919810 }, AType,
                allow_unexpected_key=False
            ) # Not okay

    Yields:
        Detected type error, in VerifyTypeError / VerifyKeyError

    Raises:
        TypeError: When a unsupported/invaild type passed.
    """

    def deal_dict_not_required(
        dic: Mapping,
    ) -> Iterable[Tuple[Hashable, Union[TypeHint, DictStructure]]]:
        for key, typ in dic.items():
            if get_origin(typ) is NotRequired:
                yield key, get_args(typ)[0]
            else:
                yield key, typ

    left_keys = list(dict_obj.keys())
    required_keys = tuple(lookup_required(structure))
    # New get_type_hints will change NotRequired[...] into ..., so not caring about it
    for key, type_ in (
        new_get_type_hints(structure).items()  # pyright: ignore
        if is_typeddict(structure)
        else deal_dict_not_required(structure)  # type: ignore[arg-type]
    ):
        try:
            value = dict_obj[key]
        except KeyError:
            if key in required_keys:
                yield VerifyKeyError(name, key, "missing")
            continue
        else:
            if not allow_unexpected_key:
                left_keys.remove(key)
        if is_typeddict(type_) or isinstance(type_, dict):
            if not isinstance(value, dict):
                yield VerifyTypeError(f"{name}[{key!r}]", type_, value)
            else:
                yield from check_dict(
                    value,
                    type_,  # type: ignore[arg-type]
                    name=f"{name}[{key!r}]",
                    allow_unexpected_key=allow_unexpected_key,
                )
        else:
            yield from check_simple_type(value, type_, name=f"{name}[{key!r}]")
    if not allow_unexpected_key and left_keys:
        for left_key in left_keys:
            yield VerifyKeyError(name, left_key, "leftover")


def assert_dict(
    dict_obj: dict,
    structure: DictStructure,
    name: str = "dict",
    allow_unexpected_key: bool = False,
) -> None:
    """Wrapper of check_dict, but it raises first error.

    Check type of a dict accord TypedDict.

    Args:
        dict_obj: The dict to be checked.
        structure: Expected type.
        name: Name of the dict.
        allow_unexpected_key: Allow leftover keys in dict_obj. Example::
            class AType(TypedDict):
                a: int
            check_dict(
                { "a": 114514 }, AType,
                allow_unexpected_key=False
            ) # Okay
            check_dict(
                { "a": 114514, "b": 1919810 }, AType,
                allow_unexpected_key=True
            ) # Okay
            check_dict(
                { "a": 114514, "b": 1919810 }, AType,
                allow_unexpected_key=False
            ) # Not okay

    Raises:
        VerifyTypeError: When found type error.
        VerifyKeyError: When found a type error about key.
        TypeError: When a unsupported/invaild type passed.
    """
    try:
        error = next(
            iter(
                check_dict(
                    dict_obj,
                    structure,
                    name,
                    allow_unexpected_key=allow_unexpected_key,
                )
            )
        )
    except StopIteration:
        pass
    else:
        raise error
