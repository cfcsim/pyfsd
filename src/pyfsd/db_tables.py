"""PyFSD database tables.

Attributes:
    metadata (MetaData): SQLAlchemy metadata.
    users_table (Table): Table used to store user info.

Note:
    These databases were initialized in [pyfsd.main.main][]
"""

from sqlalchemy import Column, Integer, MetaData, String, Table

__all__ = ["metadata", "users_table"]

metadata = MetaData()
users_table = Table(
    "users",
    metadata,
    Column("callsign", String, primary_key=True),
    Column("password", String(32)),
    Column("rating", Integer()),
)
