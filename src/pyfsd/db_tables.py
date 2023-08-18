from sqlalchemy import Column, Integer, MetaData, String, Table

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("callsign", String, primary_key=True),
    Column("password", String(64)),
    Column("rating", Integer()),
)
