# flake8: noqa
"""This tool can convert users database in other format into PyFSD format."""
from hashlib import sha256
from sys import version_info
from typing import TYPE_CHECKING, Generator, NoReturn, Optional

from alchimia import wrap_engine
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import react
from twisted.python.usage import Options, UsageError

from ...db_tables import users as usersTable
from ...define.config_check import verifyConfigStruct
from .formats import formats

if version_info >= (3, 11):
    import tomllib  # type: ignore[import, unused-ignore]
else:
    import tomli as tomllib  # type: ignore[import, no-redef, unused-ignore]

if TYPE_CHECKING:
    from twisted.internet.interfaces import IReactorCore


class ConverterOptions(Options):
    optParameters = [
        ["config-path", "c", "pyfsd.toml", "Path to the config file.", str],
    ]

    longdesc = """
    This tool can convert users database in other format into PyFSD format.            
    Example:                                                                               
        $ python -m pyfsd.utils.import_users -f cfcsim cert.sqlitedb3                      
        $ python -m pyfsd.utils.import_users -f fsd -c env_pyfsd.toml cert.txt             
    """

    def opt_version(self) -> NoReturn:
        from platform import python_version

        from twisted.copyright import version as twisted_version

        from ..._version import version as pyfsd_version

        print("Python", python_version())
        print("Twisted version:", twisted_version)
        print("PyFSD version:", pyfsd_version)
        exit(0)

    def parseArgs(  # type: ignore[override]
        self, filename: str, format_: Optional[str] = None
    ) -> None:
        self["filename"] = filename
        if format_ is None:
            print("No format specified, ", end="")
            if filename.endswith(".sqlitedb3"):
                print("assuming cfcsim fsd format.")
                format_ = "cfcsim"
            elif filename.endswith(".db"):
                print("assuming PyFSD format.")
                format_ = "pyfsd"
            elif filename.endswith(".txt"):
                print("assuming fsd text format.")
                format_ = "fsd"
            else:
                print("please specify one.")
                exit(1)
        if not format_ in formats.keys():
            print(f"Invaild format: {format_}")
            exit(1)
        self["format"] = format_

    def getSynopsis(self) -> str:
        return "Usage: python -m pyfsd.utils.import_users [options] [filename] [format]"


@inlineCallbacks
def main(reactor: "IReactorCore", *argv: str) -> Generator:
    options = ConverterOptions()
    try:
        options.parseOptions(argv)
    except UsageError as error:
        print(f"pyfsd.utils.import_users: {error}")
        print("pyfsd.utils.import_users: Try --help for usage details.")
        exit(1)

    with open(options["config-path"], "rb") as config_file:
        config = tomllib.load(config_file)

    verifyConfigStruct(
        config,
        {
            "pyfsd": {
                "database": {"url": str},
            }
        },
    )

    reader = formats[options["format"]]
    users = reader.readAll(options["filename"])
    db_engine = wrap_engine(reactor, create_engine(config["pyfsd"]["database"]["url"]))

    for user in users:
        if not reader.sha256_hashed:
            user = (user[0], sha256(user[1].encode()).hexdigest(), user[2])
        try:
            yield db_engine.execute(usersTable.insert().values(user))
        except IntegrityError as error:
            print("Callsign already exist:", error.params[0])
    print("Done.")
    exit(0)


if __name__ == "__main__":
    from sys import argv

    react(main, argv[1:])
