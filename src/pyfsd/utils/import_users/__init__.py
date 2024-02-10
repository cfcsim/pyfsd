"""A tool used to convert users database in other format into PyFSD's format."""
from argparse import ArgumentParser

from argon2 import PasswordHasher
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from ...db_tables import users_table
from ...define.check_dict import assert_dict
from .formats import formats

try:
    import tomllib  # type: ignore[import, unused-ignore]
except ImportError:
    import tomli as tomllib  # type: ignore[import, no-redef, unused-ignore]


def main() -> None:
    """Main function of the tool."""
    parser = ArgumentParser(
        description="convert users database in other format into PyFSD's format"
    )
    parser.add_argument("filename", help="filename of the original file")
    parser.add_argument(
        "format",
        help="format of the original file",
        choices=["cfcsim", "pyfsd", "fsd"],
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "-c", "--config-path", help="path to the config of PyFSD", default="pyfsd.toml"
    )
    args = parser.parse_args()

    with open(args.config_path, "rb") as config_file:
        config = tomllib.load(config_file)

    assert_dict(
        config,
        {
            "pyfsd": {
                "database": {"url": str},
            }
        },
        allow_unexpected_key=True,
    )

    reader = formats[args.format]
    users = reader.read_all(args.filename)
    db_engine = create_engine(config["pyfsd"]["database"]["url"])
    hasher = PasswordHasher()
    import_users = 0

    with db_engine.connect() as conn:
        for user in users:
            if args.verbose:
                print("Converting", *user)
            if not reader.argon2_hashed:
                user = (user[0], hasher.hash(user[1]), user[2])
            try:
                conn.execute(users_table.insert().values(user))
            except IntegrityError:
                print("Callsign already exist:", user[0])
            else:
                import_users += 1
        conn.commit()

    print(f"Done. ({import_users})")
