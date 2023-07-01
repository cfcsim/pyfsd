from os import getcwd
from os.path import abspath, realpath

# Will install while building wheel
import versioneer  # type: ignore[import]

versioneer.get_root = lambda: realpath(abspath(getcwd()))
get_version = versioneer.get_version
