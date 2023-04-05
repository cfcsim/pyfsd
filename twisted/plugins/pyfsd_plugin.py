try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from twisted.application.service import IServiceMaker, MultiService
from twisted.plugin import IPlugin
from twisted.python.usage import Options
from zope.interface import implementer

from pyfsd.define.utils import verifyConfigStruct
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
        verifyConfigStruct(
            config,
            {
                "pyfsd": {
                    "database_name": str,
                    "client": {"port": int, "motd": str, "blacklist": list},
                    "metar": {"mode": str, "fetchers": list},
                }
            },
        )
        if config["pyfsd"]["metar"]["mode"] == "cron":
            verifyConfigStruct(
                config["pyfsd"]["metar"], {"cron_time": int}, prefix="pyfsd.metar"
            )
        service = MultiService()
        pyfsd_service = PyFSDService(config)
        pyfsd_service.setServiceParent(service)
        pyfsd_service.getClientService().setServiceParent(service)
        pyfsd_service.getMetarService().setServiceParent(service)
        return service


serviceMaker = PyFSDServiceMaker()
