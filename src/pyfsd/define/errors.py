"""FSD client protocol errors."""

__all__ = ["FSDClientError"]


from enum import IntEnum


class FSDClientError(IntEnum):
    """Errno constants."""

    OK = 0
    CSINUSE = 1
    CSINVALID = 2
    REGISTERED = 3
    SYNTAX = 4
    SRCINVALID = 5
    CIDINVALID = 6
    NOSUCHCS = 7
    NOFP = 8
    NOWEATHER = 9
    REVISION = 10
    LEVEL = 11
    SERVFULL = 12
    CSSUSPEND = 13

    def __str__(self) -> str:
        """Return the error string."""
        return (
            "No error",
            "Callsign in use",
            "Invalid callsign",
            "Already registerd",  # codespell:ignore registerd
            "Syntax error",
            "Invalid source callsign",
            "Invalid CID/password",
            "No such callsign",
            "No flightplan",
            "No such weather profile",
            "Invalid protocol revision",
            "Requested level too high",
            "Too many clients connected",
            "CID/PID was suspended",
        )[int(self)]
