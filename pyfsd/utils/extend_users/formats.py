from csv import reader
from sqlite3 import connect
from typing import Dict, Protocol, Tuple

User = Tuple[str, str, int]  # callsign, password, rating


class Format(Protocol):
    sha256_hashed: bool

    def readAll(self, filename: str) -> Tuple[User, ...]:
        ...


class CfcsimFSDFormat:
    sha256_hashed = False

    @staticmethod
    def readAll(filename: str) -> Tuple[User, ...]:
        db = connect(filename)
        cur = db.cursor()
        result = tuple(cur.execute("SELECT callsign, password, level FROM cert;"))
        cur.close()
        db.close()
        return result


class FSDTextFormat:
    sha256_hashed = False

    @staticmethod
    def readAll(filename: str) -> Tuple[User, ...]:
        users = []
        with open(filename) as file:
            for row in reader(file, delimiter=" "):
                if row[0].startswith(";"):
                    continue
                users.append((row[0], row[1], int(row[2])))
        return tuple(users)


formats: Dict[str, Format] = {"cfcsim": CfcsimFSDFormat, "fsd": FSDTextFormat}
