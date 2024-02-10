"""PyFSD dependencies container."""
from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import create_async_engine

from .factory.client import ClientFactory
from .metar.manager import MetarManager
from .plugin.manager import PyFSDPluginManager


class Container(containers.DeclarativeContainer):
    """PyFSD dependencies container.

    Attributes:
        config: The root config.
        db_engine: Async sqlalchemy database engine.
        pyfsd_plugin_manager: 'PyFSD plugin' manager.
        metar_manager: Metar manager.
        client_factory: Client protocol factory, which stores clients and so on.
    """

    config = providers.Configuration()
    metar_manager = providers.Singleton(MetarManager, config.pyfsd.metar)
    db_engine = providers.Singleton(create_async_engine, config.pyfsd.database.url)
    pyfsd_plugin_manager = providers.Singleton(PyFSDPluginManager)
    client_factory = providers.Singleton(
        ClientFactory,
        config.pyfsd.client.motd.as_(bytes, config.pyfsd.client.motd_encoding),
        metar_manager,
        pyfsd_plugin_manager,
        db_engine,
    )
