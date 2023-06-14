try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from twisted.application.service import IServiceMaker, MultiService
from twisted.plugin import IPlugin
from twisted.python.usage import Options
from zope.interface import implementer

from pyfsd.service import PyFSDService
from pyfsd.setup_loguru import setupLoguru


class PyFSDOptions(Options):
    optFlags = [
        ["disable-loguru", "l", "Use default logger instead of loguru."],
    ]
    optParameters = [
        ["config-path", "c", "pyfsd.toml", "Path to the config file."],
    ]


@implementer(IServiceMaker, IPlugin)
class PyFSDServiceMaker:
    tapname = "pyfsd"
    description = "PyFSD Service"
    options = PyFSDOptions

    def makeService(self, options: PyFSDOptions):
        if not options["disable-loguru"]:
            setupLoguru()
        with open(options["config-path"], "rb") as config_file:
            config = tomllib.load(config_file)
        root_service = MultiService()
        pyfsd_service = PyFSDService(config)
        pyfsd_service.setServiceParent(root_service)
        pyfsd_service.getMetarService().setServiceParent(root_service)
        pyfsd_service.getClientService().setServiceParent(root_service)
        for service in pyfsd_service.getServicePlugins():
            service.setServiceParent(root_service)  # type: ignore
        return root_service


serviceMaker = PyFSDServiceMaker()
