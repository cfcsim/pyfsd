from twisted.application.service import IServiceMaker, MultiService
from twisted.plugin import IPlugin
from twisted.python.usage import Options
from zope.interface import implementer

from pyfsd.pyfsd import PyFSDService

class PyFSDOptions(Options):
    optParameters = [["client-port", "c", "tcp:6810", "Client interface port."]]


@implementer(IServiceMaker, IPlugin)
class PyFSDServiceMaker:
    tapname = "pyfsd"
    description = "PyFSD Service"
    options = PyFSDOptions

    def makeService(self, options: PyFSDOptions):
        service = MultiService()
        pyfsd_service = PyFSDService()
        pyfsd_service.setServiceParent(service)
        return service


serviceMaker = PyFSDServiceMaker()
