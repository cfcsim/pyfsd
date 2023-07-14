"""
This module deal with some UTF-8 problem.
"""

from typing import Iterable, Union


def isContinuationByte(byte: int) -> bool:
    # https://github.com/python/cpython
    # /blob/d2340ef25721b6a72d45d4508c672c4be38c67d3/Objects/stringlib/codecs.h#L20
    return 0x80 <= byte < 0xC0


def lastCBLength(
    chars: Iterable[Union[int, bytes]], skip_ncb_before: bool = False
) -> int:
    """
    Determine length of the last

    skip_ncb_before: Skip non continuation byte before continuation bytes.

    Example:
    >>> determineCharLengthBefore(b"\\x82\\xa8")
    2
    >>> determineCharLengthBefore([b"\\xe6", b"\\x82", b"\\xa8"], skip_ncb_before=True)
    2
    """
    length = 0
    have_continuation_byte = False
    for char in chars:
        if isinstance(char, bytes):
            char_ord = ord(char)
        else:
            char_ord = char
        if isContinuationByte(char_ord):
            length += 1
        else:
            if skip_ncb_before and not have_continuation_byte:
                pass
            else:
                break
    return length
