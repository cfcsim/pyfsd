# mypy: disable-error-code="abstract, method-assign, attr-defined"
"""This module tests pyfsd.protocol."""

from unittest import TestCase
from unittest.mock import Mock, call, patch

from pyfsd.protocol import LineProtocol, LineReceiver


class TestLineReceiver(TestCase):
    """tests if linereceiver works."""

    protocol: LineReceiver

    @patch.object(LineReceiver, "__abstractmethods__", set())
    def setUp(self) -> None:
        """Prepare LineReceiver."""
        self.protocol = LineReceiver()
        self.protocol.buffer_size = 64
        self.protocol.line_received = Mock()
        self.protocol.buffer_size_exceed = Mock()

    def test_line_received(self) -> None:
        """Tests if LineReceiver.line_received works."""
        self.protocol.data_received(b"1234\r\n5678\r\n")
        self.protocol.line_received.assert_has_calls([call(b"1234"), call(b"5678")])
        self.protocol.line_received.reset_mock()
        self.protocol.data_received(b"1234\r\n5678")
        self.protocol.line_received.assert_called_once_with(b"1234")
        self.protocol.data_received(b"1234\r\n")
        self.protocol.line_received.assert_called_with(b"56781234")
        self.protocol.line_received.reset_mock()
        self.protocol.data_received(b"abcdefg\r")
        self.protocol.data_received(b"\nhijk")
        self.protocol.line_received.assert_called_once_with(b"abcdefg")
        self.protocol.line_received.reset_mock()
        self.protocol.data_received(b"\r\n")
        self.protocol.line_received.assert_called_once_with(b"hijk")

    def test_buffer_size_exceed(self) -> None:
        """Tests if LineReceiver.buffer_size_exceed works."""
        self.protocol.data_received(b"X" * 65 + b"\r\n")
        self.protocol.buffer_size_exceed.assert_called_with(67)
        self.protocol.buffer_size_exceed.reset_mock()
        self.protocol.buffer = b""
        self.protocol.data_received(b"X" * 64)
        self.protocol.buffer_size_exceed.assert_not_called()
        self.protocol.data_received(b"X")
        self.protocol.buffer_size_exceed.assert_called_with(65)


class TestLineProtocol(TestLineReceiver):
    """Tests if LineProtocol works."""

    @patch.object(LineProtocol, "__abstractmethods__", set())
    def setUp(self) -> None:
        """Prepare LineProtocol."""
        self.protocol = LineProtocol()
        self.protocol.buffer_size = 64
        self.protocol.line_received = Mock()
        self.protocol.buffer_size_exceed = Mock()
