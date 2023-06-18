from typing import List

from twisted.plugin import pluginPackagePaths

__path__.extend(pluginPackagePaths(__name__))  # type: ignore
__all__: List[str] = []
del pluginPackagePaths, List
