from pyfsd.pyfsd import makeApplication
from pyfsd.setup_loguru import setupLoguru

setupLoguru()

application = makeApplication("tcp:6810")
