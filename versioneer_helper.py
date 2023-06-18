from os import getcwd
from os.path import abspath, realpath

import versioneer

versioneer.get_root = lambda: realpath(abspath(getcwd()))
get_version = versioneer.get_version
