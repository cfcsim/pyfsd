from unittest import TestCase

from pyfsd.define.packet import FSDCLIENTPACKET, breakPacket, makePacket


class TestPacket(TestCase):
    def test_concat(self) -> None:
        self.assertEqual(FSDCLIENTPACKET.ADD_PILOT + "CSN1012", "#APCSN1012")
        self.assertEqual(b"CSN1012" + FSDCLIENTPACKET.MESSAGE, b"CSN1012#TM")

    def test_makePacket(self) -> None:
        self.assertEqual(makePacket(b"abcd", b"efgh"), b"abcd:efgh")
        self.assertEqual(makePacket("abcd", "efgh"), "abcd:efgh")
        self.assertEqual(
            makePacket(FSDCLIENTPACKET.ADD_PILOT, "CSN1012"), "#AP:CSN1012"
        )
        self.assertEqual(
            makePacket(b"CSN1012", FSDCLIENTPACKET.MESSAGE), b"CSN1012:#TM"
        )

    def test_breakPacket(self) -> None:
        self.assertEqual(
            breakPacket("#APCSN1012:114514:1919810", FSDCLIENTPACKET),
            (FSDCLIENTPACKET.ADD_PILOT, ("CSN1012", "114514", "1919810")),
        )
        self.assertEqual(
            breakPacket("$NMCSN1012:114514:1919810", FSDCLIENTPACKET),
            (None, ("$NMCSN1012", "114514", "1919810")),
        )
        self.assertEqual(
            breakPacket(b"#APCSN1012:114514:1919810", FSDCLIENTPACKET),
            (FSDCLIENTPACKET.ADD_PILOT, (b"CSN1012", b"114514", b"1919810")),
        )
        self.assertEqual(
            breakPacket(b"$NMCSN1012:114514:1919810", FSDCLIENTPACKET),
            (None, (b"$NMCSN1012", b"114514", b"1919810")),
        )
