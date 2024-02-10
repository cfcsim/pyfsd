# Will replaced by pdm while building wheel
__all__ = ["version"]
DEFAULT_VERSION = "0.0.1.2.dev0"
version: str

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as version_lookup

    try:
        version = version_lookup("pyfsd")
    except PackageNotFoundError:
        version = DEFAULT_VERSION

    del PackageNotFoundError, version_lookup
except ImportError:
    version = DEFAULT_VERSION
