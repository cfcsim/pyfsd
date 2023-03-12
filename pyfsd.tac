from twisted.application import service, strports
from twisted.internet import reactor

from pyfsd.factory.client import FSDClientFactory
from pyfsd.setup_loguru import setup_loguru

setup_loguru()

application = service.Application("PyFSD")
strports.service("tcp:6810", FSDClientFactory(None), reactor=reactor).setServiceParent(
    service.IServiceCollection(application)
)
