# Will replaced by pdm while building wheel
PackageNotFoundError = Exception
try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("pyfsd")
except (ImportError, PackageNotFoundError):
    __version__ = "0.0.0.dev2"
