from sys import version_info
from typing import NoReturn

from twisted.application.service import IServiceMaker, MultiService
from twisted.plugin import IPlugin
from twisted.python.usage import Options
from zope.interface import implementer

from pyfsd.service import PyFSDService
from pyfsd.setup_loguru import setupLoguru

if version_info >= (3, 11):
    import tomllib  # type: ignore[import, unused-ignore]
else:
    import tomli as tomllib  # type: ignore[import, no-redef, unused-ignore]


DEFAULT_CONFIG = """[pyfsd.database]
url = "sqlite:///pyfsd.db"

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

    def opt_version(self) -> NoReturn:
        from platform import python_version

        from twisted.copyright import version as twisted_version

        print("Python", python_version())
        print("Twisted version:", twisted_version)
        print("PyFSD version:", PyFSDService.version)
        exit(0)


@implementer(IServiceMaker, IPlugin)
class PyFSDServiceMaker:
    tapname = "pyfsd"
    description = "PyFSD Service"
    options = PyFSDOptions

    def makeService(self, options: PyFSDOptions) -> MultiService:
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
            service.setServiceParent(root_service)  # pyright: ignore
        return root_service


serviceMaker = PyFSDServiceMaker()
