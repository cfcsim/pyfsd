from twisted.enterprise.adbapi import ConnectionPool
from zope.interface import Attribute, Interface, implementer

from .define.utils import verifyConfigStruct


class IDatabaseMaker(Interface):  # type: ignore[misc, valid-type]
    db_source = Attribute("db_source", "Database source.")

    def makeDBPool(config: dict) -> ConnectionPool:  # type: ignore[empty-body]
        """Make a ConnectionPool by config and return it."""


@implementer(IDatabaseMaker)
class SQLite3DBMaker:
    db_source = "sqlite3"

    @staticmethod
    def makeDBPool(config: dict) -> ConnectionPool:
        verifyConfigStruct(config, {"filename": str}, "pyfsd.database.")
        return ConnectionPool("sqlite3", config["filename"], check_same_thread=False)
