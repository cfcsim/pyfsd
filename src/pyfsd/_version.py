# Will replaced by pdm while building wheel
__all__ = ["version"]
DEFAULT_VERSION = "0.0.1.1.dev0"
PackageNotFoundError = Exception
version: str

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as version_lookup
except ImportError:
    version_lookup = lambda _: DEFAULT_VERSION  # noqa: E731, F821

try:
    version = version_lookup("pyfsd")
except PackageNotFoundError:
    version = DEFAULT_VERSION

del PackageNotFoundError, version_lookup, DEFAULT_VERSION
