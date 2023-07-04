try:
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[import, no-redef]

from twisted.application.service import IServiceMaker, MultiService
from twisted.plugin import IPlugin
from twisted.python.usage import Options
from zope.interface import implementer

from pyfsd.service import PyFSDService
from pyfsd.setup_loguru import setupLoguru

DEFAULT_CONFIG = """[pyfsd.database]
source = "sqlite3"
filename = "pyfsd.db"

[pyfsd.client]
port = 6809
motd = \"\"\"Modify motd in pyfsd.toml.\"\"\"
motd_encoding = "ascii"
blacklist = []

[pyfsd.metar]
mode = "cron"
cron_time = 3600
fetchers = ["NOAA"]"""


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
        try:
            with open(options["config-path"], "rb") as config_file:
                config = tomllib.load(config_file)
        except FileNotFoundError:
            with open(options["config-path"], "w") as config_file:
                config_file.write(DEFAULT_CONFIG)
            config = tomllib.loads(DEFAULT_CONFIG)

        root_service = MultiService()
        pyfsd_service = PyFSDService(config)
        pyfsd_service.setServiceParent(root_service)
        pyfsd_service.getMetarService().setServiceParent(root_service)
        pyfsd_service.getClientService().setServiceParent(root_service)
        for service in pyfsd_service.getServicePlugins():
            service.setServiceParent(root_service)  # type: ignore
        return root_service


serviceMaker = PyFSDServiceMaker()
