from typing import Iterable, assert_type

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

__all__ = ["config"]


with open("pyfsd.toml", "rb") as file:
    config = tomllib.load(file)
