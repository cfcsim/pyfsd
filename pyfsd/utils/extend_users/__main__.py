"""Convert cfcsim/fsd format users database to PyFSD format."""
try:
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[import, no-redef]

from hashlib import sha256
from sys import exit

from twisted.internet.reactor import run, stop  # type: ignore[attr-defined]
from twisted.python.usage import Options, UsageError

from ...service import PyFSDService
from .formats import formats


class ConverterOptions(Options):
    optParameters = [
        ["config-path", "c", "pyfsd.toml", "Path to the config file."],
        ["filename", "f", None, "Path to the original database file."],
        ["format", "F", None, "Formst of the original database file."],
    ]


class FakePyFSDService(PyFSDService):
    def __init__(self, config: dict) -> None:
        self.config = config


def main(argv) -> int:
    options = ConverterOptions()
    try:
        options.parseOptions(argv)
    except UsageError as error:
        print(f"pyfsd.utils.extend_users: {error}")
        print("pyfsd.utils.extend_users: Try --help for usage details.")
        return 1

    if options["filename"] is None:
        print("Must specify filename.")
        return 1
    if options["format"] is None:
        print("Must specify format.")
        return 1

    with open(options["config-path"], "rb") as config_file:
        config = tomllib.load(config_file)

    try:
        reader = formats[options["format"]]
    except KeyError:
        print("Unknown format")
        return 1

    users = reader.readAll(options["filename"])
    left = len(users)

    def stopIfFinish(_):
        nonlocal left

        left -= 1
        if left == 0:
            stop()

    serv = FakePyFSDService(config)
    serv.connectDatabase()
    for user in users:
        if not reader.sha256_hashed:
            user = (user[0], sha256(user[1].encode()).hexdigest(), user[2])
        assert serv.db_pool is not None
        serv.db_pool.runQuery(
            "INSERT INTO users (callsign, password, rating) VALUES (?, ?, ?)", user
        ).addCallback(stopIfFinish)
    run()
    return 0


if __name__ == "__main__":
    from sys import argv

    exit(main(argv[1:]))
