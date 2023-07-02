from atexit import register
from sys import platform

__all__ = ["RawMode"]


def restoreIfNotRestored(raw_mode: "RawMode"):
    if raw_mode.in_raw_mode:
        raw_mode.restore()


if platform == "win32":
    """
    Copied from
    https://github.com/prompt-toolkit/python-prompt-toolkit/blob/3.0.38/src/prompt_toolkit/input/win32.py#L701
    """
    from ctypes import c_ulong, pointer, windll  # type: ignore[attr-defined]
    from ctypes.wintypes import DWORD, HANDLE

    ENABLE_ECHO_INPUT = 0x0004
    ENABLE_LINE_INPUT = 0x0002
    ENABLE_PROCESSED_INPUT = 0x0001

    class RawMode:  # type: ignore
        def __init__(self, _=None):
            self.handle = HANDLE(windll.kernel32.GetStdHandle(c_ulong(-10)))
            self.original_mode = DWORD()
            self.in_raw_mode = False

        def setup(self):
            assert not self.in_raw_mode
            windll.kernel32.GetConsoleMode(self.handle, pointer(self.original_mode))
            windll.kernel32.SetConsoleMode(
                self.handle,
                self.original_mode.value
                & ~(ENABLE_ECHO_INPUT | ENABLE_LINE_INPUT | ENABLE_PROCESSED_INPUT),
            )
            self.in_raw_mode = True
            register(restoreIfNotRestored, self)

        def restore(self):
            assert self.in_raw_mode
            windll.kernel32.SetConsoleMode(self.handle, self.original_mode)
            self.in_raw_mode = False

else:
    """
    Copied from
    https://github.com/pypy/pyrepl/blob/master/pyrepl/unix_console.py#L355
    """
    from termios import (
        BRKINT,
        CS8,
        CSIZE,
        ECHO,
        ICANON,
        ICRNL,
        IEXTEN,
        INPCK,
        ISIG,
        ISTRIP,
        IXON,
        PARENB,
        TCSADRAIN,
        VMIN,
        VTIME,
        tcgetattr,
        tcsetattr,
    )
    from tty import CC, CFLAG, IFLAG, LFLAG

    class RawMode:  # type: ignore[no-redef]
        def __init__(self, fileno=None):
            if fileno is None:
                from sys import stdin

                fileno = stdin.fileno()
            self.fileno = fileno
            self.in_raw_mode = False

        def setup(self):
            assert not self.in_raw_mode
            self.original_mode = tcgetattr(self.fileno)
            new_mode = self.original_mode.copy()
            new_mode[IFLAG] |= ICRNL
            new_mode[IFLAG] &= ~(BRKINT | INPCK | ISTRIP | IXON)
            new_mode[CFLAG] &= ~(CSIZE | PARENB)
            new_mode[CFLAG] |= CS8
            new_mode[LFLAG] &= ~(ICANON | ECHO | IEXTEN | (ISIG * 1))
            new_mode[CC][VMIN] = 1
            new_mode[CC][VTIME] = 0
            tcsetattr(self.fileno, TCSADRAIN, new_mode)
            self.in_raw_mode = True
            register(restoreIfNotRestored, self)

        def restore(self):
            assert self.in_raw_mode
            tcsetattr(self.fileno, TCSADRAIN, self.original_mode)
            self.in_raw_mode = False
