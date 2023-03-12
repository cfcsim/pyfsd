import configparser

__all__ = ["config"]

config = configparser.ConfigParser()
config.read("pyfsd.ini")
