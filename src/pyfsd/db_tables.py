"""PyFSD database tables.

Note:
    These databases were initialized in pyfsd.main.main().
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
