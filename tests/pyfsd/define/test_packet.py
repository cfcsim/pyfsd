"""This module tests pyfsd.define.packet."""
# ruff: noqa: N802

from unittest import TestCase

from hypothesis import given
from hypothesis import strategies as st

from pyfsd.define.packet import (
    CLIENT_USED_COMMAND,
    SPLIT_SIGN,
    CompatibleString,
    FSDClientCommand,
    break_packet,
    join_lines,
    make_packet,
)


class TestPacket(TestCase):
    """Test if pyfsd.define.packet works."""

    def test_make_packet(self) -> None:
        """Test if make_packet works."""
        self.assertEqual(make_packet(b"abcd", b"efgh"), b"abcd:efgh")
        self.assertEqual(make_packet("abcd", "efgh"), "abcd:efgh")
        self.assertEqual(
            make_packet(FSDClientCommand.ADD_PILOT, "CSN1012"), "#AP:CSN1012"
        )
        self.assertEqual(
            make_packet(b"CSN1012", FSDClientCommand.MESSAGE), b"CSN1012:#TM"
        )

    def test_break_packet(self) -> None:
        """Test if break_packet works."""
        self.assertEqual(
            break_packet("#APCSN1012:114514:1919810", FSDClientCommand),
            (FSDClientCommand.ADD_PILOT, ("CSN1012", "114514", "1919810")),
        )
        self.assertEqual(
            break_packet("$NMCSN1012:114514:1919810", FSDClientCommand),
            (None, ("$NMCSN1012", "114514", "1919810")),
        )
        self.assertEqual(
            break_packet(b"#APCSN1012:114514:1919810", FSDClientCommand),
            (FSDClientCommand.ADD_PILOT, (b"CSN1012", b"114514", b"1919810")),
        )
        self.assertEqual(
            break_packet(b"$NMCSN1012:114514:1919810", FSDClientCommand),
            (None, (b"$NMCSN1012", b"114514", b"1919810")),
        )

    def test_join_lines(self) -> None:
        """Test if join_lines works."""
        self.assertEqual(join_lines("a", "b"), "a\r\nb\r\n")
        self.assertEqual(join_lines(b"a", b"b", newline=False), b"ab")

    def test_CompatibleString(self) -> None:
        """Test if CompatibleString works."""
        str1 = CompatibleString("0123456789ABCDEF")
        self.assertEqual(str(str1), "0123456789ABCDEF")
        self.assertEqual(bytes(str1), b"0123456789ABCDEF")
        self.assertEqual(repr(str1), "CompatibleString('0123456789ABCDEF')")
        # richcmp tests taken from cpython/Lib/test/test_bytes.py
        self.assertEqual(CompatibleString("abc") == b"abc", True)
        self.assertEqual(CompatibleString("ab") != b"abc", True)
        self.assertEqual(CompatibleString("ab") <= b"abc", True)
        self.assertEqual(CompatibleString("ab") < b"abc", True)
        self.assertEqual(CompatibleString("abc") >= b"ab", True)
        self.assertEqual(CompatibleString("abc") > b"ab", True)
        self.assertEqual(CompatibleString("abc") != b"abc", False)
        self.assertEqual(CompatibleString("ab") == b"abc", False)
        self.assertEqual(CompatibleString("ab") > b"abc", False)
        self.assertEqual(CompatibleString("ab") >= b"abc", False)
        self.assertEqual(CompatibleString("abc") < b"ab", False)
        self.assertEqual(CompatibleString("abc") <= b"ab", False)
        self.assertEqual(CompatibleString("abc") == "abc", True)
        self.assertEqual(CompatibleString("ab") != "abc", True)
        self.assertEqual(CompatibleString("ab") <= "abc", True)
        self.assertEqual(CompatibleString("ab") < "abc", True)
        self.assertEqual(CompatibleString("abc") >= "ab", True)
        self.assertEqual(CompatibleString("abc") > "ab", True)
        self.assertEqual(CompatibleString("abc") != "abc", False)
        self.assertEqual(CompatibleString("ab") == "abc", False)
        self.assertEqual(CompatibleString("ab") > "abc", False)
        self.assertEqual(CompatibleString("ab") >= "abc", False)
        self.assertEqual(CompatibleString("abc") < "ab", False)
        self.assertEqual(CompatibleString("abc") <= "ab", False)
        self.assertEqual(str1.__getnewargs__(), ("0123456789ABCDEF",))
        self.assertEqual(CompatibleString("A%dC") % 3, CompatibleString("A3C"))
        self.assertEqual(str1 + "test", "0123456789ABCDEFtest")
        self.assertEqual(str1 + b"test", b"0123456789ABCDEFtest")
        self.assertEqual(
            str1 + CompatibleString("test"), CompatibleString("0123456789ABCDEFtest")
        )
        self.assertIn("ABCD", str1)
        self.assertIn(b"ABCD", str1)
        self.assertIn(CompatibleString("ABCD"), str1)
        self.assertNotIn("ABCDEFG", str1)
        self.assertNotIn(b"ABCDEFG", str1)
        self.assertNotIn(CompatibleString("ABCDEFG"), str1)
        self.assertEqual(str(str1 * 10), "0123456789ABCDEF" * 10)
        self.assertEqual(bytes(str1 * 10), b"0123456789ABCDEF" * 10)
        self.assertEqual(str1 * 10, CompatibleString("0123456789ABCDEF" * 10))

    @given(st.slices(20))
    def test_CompatibleString_slice(self, s: slice) -> None:
        """Test if CompatibleString subscript works."""
        self.assertEqual(
            CompatibleString("0123456789ABCDEF")[s], b"0123456789ABCDEF"[s]
        )

    def test_CLIENT_USED_COMMAND(self) -> None:
        """Test if CLIENT_USED_COMMAND works."""
        for command in CLIENT_USED_COMMAND:
            with self.subTest(command=command):
                self.assertIn(command, FSDClientCommand)

    def test_SPLIT_SIGN(self) -> None:
        """Test if SPLIT_SIGN works."""
        self.assertEqual(str(SPLIT_SIGN), ":")
        self.assertEqual(bytes(SPLIT_SIGN), b":")
