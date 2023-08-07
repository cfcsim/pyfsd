# Will replaced by pdm while building wheel
PackageNotFoundError = Exception
version_lookup = lambda _: "0.0.0.dev2"  # noqa: E731
version: str

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as version_lookup
except ImportError:
    pass
try:
    version = version_lookup("pyfsd")
except (ImportError, PackageNotFoundError):
    version = "0.0.0.dev2"
del PackageNotFoundError, version_lookup
