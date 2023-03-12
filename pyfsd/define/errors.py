__all__ = ["FSDErrors"]


class FSDErrors:
    ERR_OK = 0
    ERR_CSINUSE = 1
    ERR_CSINVALID = 2
    ERR_REGISTERED = 3
    ERR_SYNTAX = 4
    ERR_SRCINVALID = 5
    ERR_CIDINVALID = 6
    ERR_NOSUCHCS = 7
    ERR_NOFP = 8
    ERR_NOWEATHER = 9
    ERR_REVISION = 10
    ERR_LEVEL = 11
    ERR_SERVFULL = 12
    ERR_CSSUSPEND = 13
    error_names = [
        "No error",
        "Callsign in use",
        "Callsign invalid",
        "Already registered",
        "Syntax error",
        "Invalid source in packet",
        "Invalid CID/password",
        "No such callsign",
        "No flightplan",
        "No such weather",
        "Invalid protocol revision",
        "Requested level too high",
        "No more clients",
        "CID/PID suspended",
    ]
