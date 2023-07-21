from twisted.enterprise.adbapi import ConnectionPool
from zope.interface import Attribute, Interface, implementer

from .define.utils import verifyConfigStruct


class IDatabaseMaker(Interface):
    """Database maker.

    Attributes:
        db_source: Name of the database source.
    """

    db_source: str = Attribute("db_source", "Name of the database source.")

    def makeDBPool(config: dict) -> ConnectionPool:
        """Make a ConnectionPool by config and return it.

        Args:
            config: pyfsd.database section of PyFSD configure file.

        Returns:
            ConnectionPool of the database source.
        """


@implementer(IDatabaseMaker)
class SQLite3DBMaker:
    db_source = "sqlite3"

    @staticmethod
    def makeDBPool(config: dict) -> ConnectionPool:
        verifyConfigStruct(config, {"filename": str}, "pyfsd.database.")
        return ConnectionPool("sqlite3", config["filename"], check_same_thread=False)
