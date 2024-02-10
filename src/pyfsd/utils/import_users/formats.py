"""User database formats.

Attributes:
    User: description of a user, (callsign, password, rating)
    formats: All registered formats.
"""
from csv import reader
from sqlite3 import connect
from typing import ClassVar, Dict, Protocol, Tuple

User = Tuple[str, str, int]


class Format(Protocol):
    """Format of user database.

    Attributes:
        argon2_hashed: Password hashed by argon2 or not.
    """

    argon2_hashed: bool

    def read_all(self, filename: str) -> Tuple[User, ...]:
        """Read all users from database.

        Args:
            filename: The filename of the database.
        """
        raise NotImplementedError()


class PyFSDFormat:
    """User database format of PyFSD."""

    argon2_hashed: ClassVar = True

    @staticmethod
    def read_all(filename: str) -> Tuple[User, ...]:
        """Read all users."""
        db = connect(filename)
        cur = db.cursor()
        result = tuple(cur.execute("SELECT callsign, password, rating FROM users;"))
        cur.close()
        db.close()
        return result


class CFCSIMFSDFormat:
    """User database format of cfcsim modified fsd."""

    argon2_hashed: ClassVar = False

    @staticmethod
    def read_all(filename: str) -> Tuple[User, ...]:
        """Read all users."""
        db = connect(filename)
        cur = db.cursor()
        result = tuple(cur.execute("SELECT callsign, password, level FROM cert;"))
        cur.close()
        db.close()
        return result


class FSDTextFormat:
    """User database format of original fsd."""

    argon2_hashed: ClassVar = False

    @staticmethod
    def read_all(filename: str) -> Tuple[User, ...]:
        """Read all users."""
        users = []
        with open(filename) as file:
            for row in reader(file, delimiter=" "):
                if row[0].startswith(";"):
                    continue
                users.append((row[0], row[1], int(row[2])))
        return tuple(users)


formats: Dict[str, Format] = {
    "cfcsim": CFCSIMFSDFormat,
    "fsd": FSDTextFormat,
    "pyfsd": PyFSDFormat,
}
