from twisted.application.service import IServiceMaker
from twisted.plugin import IPlugin
from twisted.python.usage import Options
from zope.interface import implementer

from .pyfsd import makeApplication


class PyFSDOptions(Options):
    optParameters = [["client-port", "c", 6810, "Client interface port."]]


@implementer(IServiceMaker, IPlugin)
class PyFSDServiceMaker:
    tapname = "pyfsd"
    description = ""
    options = PyFSDOptions

    def makeService(self, options: PyFSDOptions):
        return makeApplication(options["client-port"])


serviceMaker = PyFSDServiceMaker()
