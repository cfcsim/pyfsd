"""PyFSD dependencies container."""

from typing import TYPE_CHECKING

from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import create_async_engine

from .factory.client import ClientFactory
from .metar.manager import MetarManager
from .plugin.manager import PluginManager

if TYPE_CHECKING:
    from .main import RootPyFSDConfig


class RootPyFSDConfigProvider(providers.Configuration):
    """Customized providers.Configuration with correct type annotation."""

    def from_dict(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        options: "RootPyFSDConfig",  # type: ignore[override]
        *,
        required: bool = False,
    ) -> None:
        """Load configuration from dict."""
        return super().from_dict(options, required=required)  # type: ignore[arg-type]


class Container(containers.DeclarativeContainer):
    """PyFSD dependencies container.

    Attributes:
        config (RootPyFSDConfigProvider): The root config.
        db_engine (providers.Singleton[sqlalchemy.ext.asyncio.AsyncEngine]): sqlalchemy
            database engine.
        plugin_manager (providers.Singleton[PluginManager]): Plugin manager.
        metar_manager (providers.Singleton[MetarManager]): Metar manager.
        client_factory (providers.Singleton[ClientFactory]): Client protocol factory,
            which stores clients and do something else.
    """

    config = RootPyFSDConfigProvider()
    db_engine = providers.Singleton(
        create_async_engine, config.pyfsd.database.url, pool_pre_ping=True
    )
    plugin_manager = providers.Singleton(PluginManager)
    metar_manager = providers.Singleton(MetarManager, config.pyfsd.metar)
    client_factory = providers.Singleton(
        ClientFactory,
        config.pyfsd.client.motd.as_(bytes, config.pyfsd.client.motd_encoding),
        config.pyfsd.client.blacklist,
        metar_manager,
        plugin_manager,
        db_engine,
    )
