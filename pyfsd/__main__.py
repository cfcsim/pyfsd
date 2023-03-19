from .pyfsd import PyFSD
from .setup_loguru import setup_loguru

setup_loguru()

pyfsd = PyFSD()
pyfsd.run()
