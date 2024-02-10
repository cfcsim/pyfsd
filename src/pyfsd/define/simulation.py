"""This module simulates some feature in C++ like integer overflow."""

from .utils import MRand

INT_MIN = -2147483648
INT_MAX = +2147483647


class Int32MRand(MRand):
    """MRand that simulates int32 overflow."""
    _really_randseed: int

    def __init__(self) -> None:
        """Create a MRand instance."""
        self._really_randseed = 0

    @property
    def mrandseed(self) -> int:
        """Get mrandseed."""
        return self._really_randseed

    @mrandseed.setter
    def mrandseed(self, value: int) -> None:  # pyright: ignore
        """Set mrandseed. Simulates int32 overflow."""
        # https://stackoverflow.com/a/7771363
        if not INT_MIN <= value <= INT_MAX:
            value = (value + (INT_MAX + 1)) % (2 * (INT_MAX + 1)) - INT_MAX - 1
        self._really_randseed = value
