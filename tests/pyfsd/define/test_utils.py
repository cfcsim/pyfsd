from unittest import TestCase

from constantly import ValueConstant

from pyfsd.define.utils import (
    asciiOnly,
    assertNoDuplicate,
    constToAnyStr,
    isCallsignVaild,
    iterCallable,
    joinLines,
    strToFloat,
    strToInt,
)


class TestUtils(TestCase):
    def test_asciiOnly(self) -> None:
        self.assertTrue(asciiOnly("abcd"))
        self.assertTrue(asciiOnly(b"abcd"))
        self.assertFalse(asciiOnly("好好好"))
        self.assertFalse(asciiOnly(chr(114514).encode()))

    def test_assertNoDuplicate(self) -> None:
        assertNoDuplicate((1, 2, 3, 4, 5, 6))
        with self.assertRaises(AssertionError):
            assertNoDuplicate((1, 1, 4, 5, 1, 4))

    def test_constToAnyStr(self) -> None:
        self.assertEqual(constToAnyStr(str, ValueConstant("abcd")), "abcd")
        self.assertEqual(constToAnyStr(bytes, ValueConstant("abcd")), b"abcd")

    def test_isCallsignVaild(self) -> None:
        self.assertFalse(isCallsignVaild("*P"))
        self.assertFalse(isCallsignVaild("CSN:1012"))
        self.assertTrue(isCallsignVaild("1012"))

    def test_iterCallable(self) -> None:
        class TestClass:
            def abc(self) -> None:
                pass

        self.assertEqual(len(list(iterCallable(TestClass(), ignore_private=True))), 1)

    def test_joinLines(self) -> None:
        self.assertEqual(joinLines("a", "b"), "a\r\nb\r\n")
        self.assertEqual(joinLines(b"a\r\n", b"b", newline=False), b"a\r\nb")

    def test_strToNumbet(self) -> None:
        self.assertEqual(strToInt("1234"), 1234)
        self.assertEqual(strToFloat("1234"), 1234)
        self.assertEqual(strToInt("zzzz", default_value=-114), -114)
        self.assertEqual(strToFloat("zzzz", default_value=-514.0), -514.0)
