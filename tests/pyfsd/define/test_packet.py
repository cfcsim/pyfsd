"""This module tests pyfsd.define.packet."""
# ruff: noqa: N802

from unittest import TestCase

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
        str1 = CompatibleString("1234")
        self.assertEqual(len(str1), 4)
        self.assertEqual(str1 + "test", "1234test")
        self.assertEqual(str1 + b"test", b"1234test")
        self.assertEqual(str1 + CompatibleString("test"), CompatibleString("1234test"))
        self.assertIn("1", str1)
        self.assertIn(b"2", str1)
        self.assertIn(CompatibleString("3"), str1)
        self.assertEqual(str1.as_type(str), "1234")
        self.assertEqual(str1.as_type(bytes), b"1234")

    def test_CLIENT_USED_COMMAND(self) -> None:
        """Test if CLIENT_USED_COMMAND works."""
        for command in CLIENT_USED_COMMAND:
            with self.subTest(command=command):
                self.assertIn(command, FSDClientCommand)

    def test_SPLIT_SIGN(self) -> None:
        """Test if SPLIT_SIGN works."""
        self.assertEqual(str(SPLIT_SIGN), ":")
        self.assertEqual(bytes(SPLIT_SIGN), b":")
