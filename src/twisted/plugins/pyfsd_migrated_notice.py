from typing import NoReturn

from twisted.application.service import IServiceMaker
from twisted.plugin import IPlugin
from twisted.python.usage import Options
from zope.interface import implementer


@implementer(IServiceMaker, IPlugin)
class PyFSDServiceMaker:
    tapname = "pyfsd"
    description = "PyFSD Service, deprecated. Use `python -m pyfsd' instead."
    options = Options

    def makeService(self, _: Options) -> NoReturn:
        print(
            "PyFSD doesn't built on Twisted anymore, Please use `python -m pyfsd' instead.",
        )
        exit(1)


serviceMaker = PyFSDServiceMaker()
