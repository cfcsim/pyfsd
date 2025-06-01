"""Tools to perform runtime TypedDict type check.

It can be used to perform config check.
Only TypedDict, Literal, NotRequired, Union, List and Dict are supported.

Attributes:
    DictStructure: Type of a object describes structure of a dict, can be TypedDict
        or dict.
    TypeHint: Type of a type hint.

Examples:
    >>> list(check_simple_type(1, Union[int, str]))
    []
    >>> list(check_simple_type(b"imbytes", Union[int, str]))
    [VerifyTypeError('object', typing.Union[int, str], b'imbytes')]
    >>> list(check_dict({ "a": 1 }, TypedDict("A", { "a": int })))
    []
    >>> list(check_dict({ "a": "imstr" }, TypedDict("A", { "a": int })))
    [VerifyTypeError("dict['a']", <class 'int'>, 'imstr')]
"""

from collections.abc import Hashable, Iterable, Mapping
from sys import version_info
from typing import (
    Literal,
    TypedDict,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

if version_info >= (3, 11):
    from typing import (  # type: ignore[attr-defined,unused-ignore]
        NotRequired,
        is_typeddict,
    )
    from typing import (
        get_type_hints as new_get_type_hints,
    )
else:
    # ruff: noqa: UP035
    from typing_extensions import (
        NotRequired,
        is_typeddict,
    )

    # We'll use only compatible signature so that should be ok
    from typing_extensions import (  # type: ignore[assignment]
        get_type_hints as new_get_type_hints,
    )

from typing_extensions import NotRequired as NotRequired_ext

from .utils import is_empty_iterable

__all__ = [
    "DictStructure",
    "TypeHint",
    "VerifyKeyError",
    "VerifyTypeError",
    "assert_dict",
    "assert_simple_type",
    "check_dict",
    "check_simple_type",
    "explain_type",
    "lookup_required",
]

# Currently we have no choice to make Literal[...] works, so temporarily type it as Any
TypeHint = object  # Union[TypeAlias, Type]


def explain_type(typ: TypeHint) -> str:
    """Explain a type.

    Args:
        typ: The type to be explained.

    Returns:
        Description of the type.

    Raises:
        TypeError: When an unsupported/invalid type passed.
    """
    if isinstance(typ, dict) or is_typeddict(typ):
        return "dict"
    if type_origin := get_origin(typ):  # elif (t_o is not None)
        if type_origin is Union:
            return " or ".join(explain_type(sub_type) for sub_type in get_args(typ))
        if type_origin is Literal:
            return " or ".join(repr(sub_value) for sub_value in get_args(typ))
        if type_origin in (list, dict):
            return str(typ).removeprefix(typ.__module__ + ".")
        raise TypeError(f"Unsupported type: {type_origin!r}")
    if isinstance(typ, type):
        return typ.__name__
    raise TypeError(f"Invalid type: {typ!r}")


class VerifyTypeError(TypeError):
    """A exception describes a value does not match specified type.

    Attributes:
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
            The formatted string, includes name, expected type and actually value
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
        if self is other:
            return True
        if isinstance(other, VerifyTypeError):
            return (
                self.name == other.name
                and self.excepted == other.excepted
                and self.actually == other.actually
            )
        return NotImplemented


class VerifyKeyError(KeyError):
    """A exception describes a missing or extra key in a dict.

    Attributes:
        dict_name: The dict name.
        key: The key name.
        type: Type of error, a missing or extra key found.
    """

    dict_name: str
    key: Hashable
    type: Literal["missing", "extra"]

    def __init__(
        self, dict_name: str, key: Hashable, type_: Literal["missing", "extra"]
    ) -> None:
        """Create a VerifyKeyError instance.

        Args:
            dict_name: The dict name.
            key: The key name.
            type_: Type of error, a missing or extra key found.
        """
        self.dict_name = dict_name
        self.key = key
        self.type = type_
        super().__init__(dict_name, key, type_)

    def __str__(self) -> str:
        """Format a VerifyKeyError to string.

        Returns:
            The formatted string, includes name, error type
        """
        return f"{self.dict_name}[{self.key!r}] is {self.type}"

    def __eq__(self, other: object) -> bool:
        """Return self==other."""
        if self is other:
            return True
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
        TypeError: When an unsupported type is specified.
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
            raise TypeError(f"Unsupported type: {type_origin!r}")
    elif isinstance(typ, type):
        if not isinstance(obj, typ):
            yield VerifyTypeError(name, typ, obj)
    else:
        raise TypeError(f"Invalid type: {typ!r}")


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
        TypeError: When an unsupported type is specified.
    """
    try:
        error = next(iter(check_simple_type(obj, typ, name)))
    except StopIteration:
        pass
    else:
        raise error


DictStructure = Union[
    type[TypedDict],  # type: ignore[valid-type]
    Mapping,  # It should be Mapping[Hashable, Union[TypeHint, DictStructure]
    # (but it's invariant)
]


def lookup_required(structure: DictStructure) -> Iterable[Hashable]:
    """Yields all required key in a TypedDict.

    Args:
        structure: The type structure, TypedDict or dict.

    Yields:
        Keys that are required, str normally.
    """
    if is_typeddict(structure):
        # Python < 3.9 not supported
        # ---------
        # Mypy bug, ignore it
        if not structure.__total__:  # type: ignore[union-attr]
            # Nothing is required
            return
        if NotRequired.__module__ == "typing":  # Python 3.11+, not need to Workaround
            yield from structure.__required_keys__  # type: ignore[union-attr]
            return
        # Python 3.9, 3.10
        type_hints = get_type_hints(structure)
        for may_required_keys in structure.__required_keys__:  # type: ignore[union-attr]
            if get_origin(type_hints[may_required_keys]) not in (
                NotRequired,
                NotRequired_ext,
            ):
                yield may_required_keys
    else:
        for may_required_keys, type_ in structure.items():  # type: ignore[union-attr]
            if get_origin(type_) not in (NotRequired, NotRequired_ext):
                yield may_required_keys


# ruff: noqa: C901, PLR0912
def check_dict(
    dict_obj: dict,
    structure: DictStructure,
    *,
    name: str = "dict",
    allow_extra_keys: bool = False,
) -> Iterable[Union[VerifyTypeError, VerifyKeyError]]:
    """Check type of a dict accord TypedDict.

    Args:
        dict_obj: The dict to be checked.
        structure: Expected type.
        name: Name of the dict.
        allow_extra_keys: Allow extra keys in dict_obj or not.

    Yields:
        Detected type error, in VerifyTypeError / VerifyKeyError

    Raises:
        TypeError: When an unsupported/invalid type passed.

    Examples:
        >>> class AType(TypedDict):
        ...     a: int
        ...
        >>> list(check_dict({ "a": 114514 }, AType, allow_extra_keys=False))
        []
        >>> list(check_dict({ "a": "" }, AType, allow_extra_keys=False, name="mything"))
        [VerifyTypeError("mything['a']", <class 'int'>, '')]
        >>> list(check_dict({}, AType))
        [VerifyKeyError('dict', 'a', 'missing')]
        >>> list(check_dict(
        ...     { "a": 114514, "b": 1919810 },
        ...     AType,
        ...     allow_extra_keys=True
        ... ))
        []
        >>> list(check_dict(
        ...     { "a": 114514, "b": 1919810 },
        ...     AType,
        ...     allow_extra_keys=False
        ... ))
        [VerifyKeyError('dict', 'b', 'extra')]
    """

    def deal_dict_not_required(
        dic: Mapping,
    ) -> Iterable[tuple[Hashable, Union[TypeHint, DictStructure]]]:
        for key, typ in dic.items():
            if get_origin(typ) in (NotRequired, NotRequired_ext):
                yield key, get_args(typ)[0]
            else:
                yield key, typ

    left_keys = list(dict_obj.keys())
    required_keys = tuple(lookup_required(structure))
    # New get_type_hints will change NotRequired[...] into ...
    for key, type_ in (
        new_get_type_hints(structure).items()
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
            if not allow_extra_keys:
                left_keys.remove(key)
        if is_typeddict(type_) or isinstance(type_, dict):
            if not isinstance(value, dict):
                yield VerifyTypeError(f"{name}[{key!r}]", type_, value)
            else:
                yield from check_dict(
                    value,
                    type_,  # type: ignore[arg-type]
                    name=f"{name}[{key!r}]",
                    allow_extra_keys=allow_extra_keys,
                )
        else:
            yield from check_simple_type(value, type_, name=f"{name}[{key!r}]")
    if not allow_extra_keys and left_keys:
        for left_key in left_keys:
            yield VerifyKeyError(name, left_key, "extra")


def assert_dict(
    dict_obj: dict,
    structure: DictStructure,
    *,
    name: str = "dict",
    allow_extra_keys: bool = False,
) -> None:
    """Wrapper of check_dict, which raises once an error is generated.

    Check type of a dict accord TypedDict.

    Args:
        dict_obj: The dict to be checked.
        structure: Expected type.
        name: Name of the dict.
        allow_extra_keys: Allow extra keys in dict_obj or not.

    Raises:
        VerifyTypeError: When found type error.
        VerifyKeyError: When found a type error about key.
        TypeError: When an unsupported/invalid type passed.
    """
    try:
        error = next(
            iter(
                check_dict(
                    dict_obj,
                    structure,
                    name=name,
                    allow_extra_keys=allow_extra_keys,
                )
            )
        )
    except StopIteration:
        pass
    else:
        raise error
