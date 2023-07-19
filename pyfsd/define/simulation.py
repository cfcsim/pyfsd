"""This module simulates some feature in C++ like integer overflow."""

from .utils import MRand

INT_MIN = -2147483648
INT_MAX = +2147483647


class Int32MRand(MRand):
    _really_randseed = 0

    @property
    def mrandseed(self) -> int:
        return self._really_randseed

    @mrandseed.setter
    def mrandseed(self, value: int) -> None:
        # https://stackoverflow.com/a/7771363
        if not INT_MIN <= value <= INT_MAX:
            value = (value + (INT_MAX + 1)) % (2 * (INT_MAX + 1)) - INT_MAX - 1
        self._really_randseed = value
