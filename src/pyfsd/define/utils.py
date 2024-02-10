"""Collection of tools that are used frequently.

Attributes:
    task_keeper: Helper to keep your asyncio.Task's strong reference.
"""
from re import compile
from typing import (
    TYPE_CHECKING,
    Callable,
    Hashable,
    Iterable,
    Set,
    TypeVar,
    Union,
    cast,
    overload,
)

# Not yet typed
from haversine import Unit, haversine

if TYPE_CHECKING:
    from asyncio import Task

    from ..object.client import Position

__all__ = [
    "str_to_int",
    "str_to_float",
    "is_callsign_vaild",
    "calc_distance",
    "ascii_only",
    "assert_no_duplicate",
    "is_empty_iterable",
    "iterables",
    "iter_callable",
    "task_keeper",
    "MRand",
]
__str_invaild_char_regex = compile("[!@#$%*:& \t]")
__bytes_invaild_char_regex = compile(b"[!@#$%*:& \t]")
T = TypeVar("T")


def str_to_int(string: Union[str, bytes], default_value: int = 0) -> int:
    """Convert a str or bytes into int.

    Args:
        string: The string to be converted.
        default_value: Default value when convert failed.

    Returns:
        The int.
    """
    try:
        return int(string)
    except ValueError:
        return default_value


def str_to_float(string: Union[str, bytes], default_value: float = 0.0) -> float:
    """Convert a str or bytes into float.

    Args:
        string: The string to be converted.
        default_value: Default value when convert failed.

    Returns:
        The float number.
    """
    try:
        return float(string)
    except ValueError:
        return default_value


def calc_distance(
    from_position: "Position",
    to_position: "Position",
    unit: Unit = Unit.NAUTICAL_MILES,
) -> float:
    """Calculate the distance from one point to another point.

    A wrapper of haversine since it's not typed well

    Args:
        from_position: The first point.
        to_position: The second point.
        unit: Unit of the distance. Default nm

    Returns:
        The distance.
    """
    return cast(float, haversine(from_position, to_position, unit=unit))


def is_callsign_vaild(callsign: Union[str, bytes]) -> bool:
    """Check if a callsign is vaild or not."""
    global __str_invaild_char_regex, __bytes_invaild_char_regex
    if len(callsign) < 2 or len(callsign) > 12:
        return False
    if (  # type: ignore[attr-defined]
        __str_invaild_char_regex
        if isinstance(callsign, str)
        else __bytes_invaild_char_regex
    ).search(
        callsign,  # pyright: ignore
    ) is not None:
        return False
    return True


def ascii_only(string: Union[str, bytes]) -> bool:
    """Check if a string contains only ascii chars."""
    if isinstance(string, str):
        return all(ord(char) < 128 for char in string)
    return all(char < 128 for char in string)


def assert_no_duplicate(
    iterator: Iterable[Hashable],
) -> None:
    """Assert nothing duplicated in a iterable object.

    Args:
        iterator: The iterable object.

    Raises:
        AssertionError: When a duplicated value detected
    """
    list_val = list(iterator)
    nodup_list_val = list(set(list_val))

    if len(list_val) != len(nodup_list_val):
        for nodup_val in nodup_list_val:
            list_val.remove(nodup_val)
        msg = f"Duplicated value: {list_val}"
        raise AssertionError(msg)


def is_empty_iterable(iter_obj: Iterable) -> bool:
    """Check if a iterable object is empty."""
    try:
        next(iter(iter_obj))
    except StopIteration:
        return True
    else:
        return False


@overload
def iterables(*iterators: Iterable[T]) -> Iterable[T]:
    ...


@overload
def iterables(*iterators: Iterable) -> Iterable:
    ...


def iterables(*iterators: Iterable) -> Iterable:
    """Iterate multiple iterable objects at once.

    Args:
        iterators: Iterable objects.

    Yields:
        Iterate result.
    """
    for iterator in iterators:
        yield from iterator


def iter_callable(obj: object, ignore_private: bool = True) -> Iterable[Callable]:
    """Yields all callable attribute in a object.

    Args:
        obj: The object.
        ignore_private: Don't yield attributes which name starts with '_'.

    Yields:
        Callable attributes.
    """
    for attr_name in dir(obj):
        if ignore_private and attr_name.startswith("_"):
            continue
        attr = getattr(obj, attr_name)
        if callable(attr):
            yield attr


class MRand:
    """Python implemention of FSD MRand.

    Note:
        This class does not simulate int32 overflow.
        See also: pyfsd.define.simulation.Int32MRand

    Attributes:
        mrandseed: Random seed.
    """

    mrandseed: int = 0

    def __call__(self) -> int:
        """Generate a random number."""
        self.mrandseed ^= 0x22591D8C
        part1 = (self.mrandseed << 1) & 0xFFFFFFFF
        part2 = self.mrandseed >> 31
        self.mrandseed ^= part1 | part2
        # self.mrandseed &= 0xFFFFFFFF
        return self.mrandseed

    def srand(self, seed: int) -> None:
        """Set random seed."""
        self.mrandseed = seed


class TaskKeeper:
    """Keep strong reference to running tasks.

    Note:
        You're advised not to create new instance,
        use `pyfsd.define.utils.task_keeper` instead.
    """

    tasks: Set["Task"]

    def __init__(self) -> None:
        """Create a TaskKeeper instance."""
        self.tasks = set()

    def add(self, task: "Task") -> None:
        """Add a task that to be kept."""
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


task_keeper = TaskKeeper()
