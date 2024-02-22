"""This module tests pyfsd.define.utils."""
from asyncio import create_task, new_event_loop, sleep
from unittest import TestCase

from haversine import Unit
from pyfsd.define.utils import (
    MRand,
    ascii_only,
    assert_no_duplicate,
    asyncify,
    calc_distance,
    is_callsign_vaild,
    is_empty_iterable,
    iter_callable,
    iterables,
    str_to_float,
    str_to_int,
    task_keeper,
)


class TestUtils(TestCase):
    """Test if pyfsd.define.utils works."""

    def test_ascii_only(self) -> None:
        """Test if ascii_only works."""
        self.assertTrue(ascii_only("abcd"))
        self.assertTrue(ascii_only(b"abcd"))
        self.assertFalse(ascii_only("好好好"))
        self.assertFalse(ascii_only(chr(114514).encode()))

    def test_assert_no_duplicate(self) -> None:
        """Test if ascii_only works."""
        assert_no_duplicate((1, 2, 3, 4, 5, 6))
        with self.assertRaises(AssertionError):
            assert_no_duplicate((1, 1, 4, 5, 1, 4))

    def test_is_callsign_vaild(self) -> None:
        """Test if is_callsign_vaild works."""
        self.assertFalse(is_callsign_vaild("*P"))
        self.assertFalse(is_callsign_vaild("CSN:1012"))
        self.assertTrue(is_callsign_vaild("1012"))

    def test_iter_callable(self) -> None:
        """Test if iter_callable works."""

        class TestClass:
            """A simple class with a publoc function."""

            def abc(self) -> None:
                """A simple function."""

        self.assertEqual(len(list(iter_callable(TestClass(), ignore_private=True))), 1)

    def test_str_to_number(self) -> None:
        """Test if str_to_int and str_to_float works."""
        self.assertEqual(str_to_int("1234"), 1234)
        self.assertEqual(str_to_float("1234"), 1234)
        self.assertEqual(str_to_int("zzzz", default_value=-114), -114)
        self.assertEqual(str_to_float("zzzz", default_value=-514.0), -514.0)

    def test_calc_distance(self) -> None:
        """Test if calc_distance works."""
        self.assertEqual(calc_distance((0, 0), (0, 3), unit=Unit.DEGREES), 3)

    def test_is_empty_iterable(self) -> None:
        """Test if is_empty_iterable works."""
        self.assertTrue(is_empty_iterable([]))
        self.assertFalse(is_empty_iterable([1]))

    def test_iterables(self) -> None:
        """Test if iterables works."""
        self.assertEqual(list(iterables([1, 2], [3, 4])), [1, 2, 3, 4])

    def test_asyncify(self) -> None:
        """Test if asyncify works."""
        k = False

        @asyncify
        def func() -> int:
            """Docstring."""
            nonlocal k
            k = True
            return 1

        async def check() -> None:
            self.assertEqual(await func(), 1)

        self.assertEqual(func.__doc__, "Docstring.")
        new_event_loop().run_until_complete(check())
        self.assertTrue(k)

    def test_task_keeper(self) -> None:
        """Test if task_keeper works."""
        loop = new_event_loop()

        def make_task() -> None:
            async def func() -> None:
                pass

            task = create_task(func())
            task_keeper.add(task)

        loop.call_soon(make_task)
        loop.run_until_complete(sleep(0))
        self.assertFalse(task_keeper.tasks)

    def test_MRand(self) -> None:  # noqa: N802
        """Test if MRand works."""
        mrand = MRand()
        mrand.srand(0)
        self.assertEqual(mrand(), 1726686868)
