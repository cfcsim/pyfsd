"""Run PyFSD.

Attributes:
    DEFAULT_CONFIG: Default config of PyFSD.
"""

from argparse import ArgumentParser
from asyncio import (
    CancelledError,
    Task,
    all_tasks,
    create_task,
    current_task,
    gather,
    get_event_loop,
    wait,
)
from signal import SIGHUP, SIGINT, SIGTERM
from typing import Awaitable, List, TypedDict, cast

from dependency_injector.wiring import register_loader_containers
from structlog import get_logger
from typing_extensions import NotRequired

from ._version import version
from .db_tables import metadata
from .define.check_dict import assert_dict
from .define.utils import task_keeper
from .dependencies import Container
from .factory.client import PyFSDClientConfig
from .metar.manager import PyFSDMetarConfig, suppress_metar_parser_warning
from .plugin.interfaces import AwaitableMaker
from .setup_logger import PyFSDLoggerConfig, setup_logger

try:
    # Python 3.11+
    from tomllib import loads  # type: ignore[import-not-found,unused-ignore]
except ImportError:
    from tomli import loads  # type: ignore[no-redef,import-not-found,unused-ignore]


class PyFSDDatabaseConfig(TypedDict):
    """PyFSD database config.

    Attributes:
        url: The database url.
        See `SQLALchemy docs <https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls>`_.
    """

    url: str


class PyFSDConfig(TypedDict):
    """PyFSD config."""

    database: PyFSDDatabaseConfig
    client: PyFSDClientConfig
    metar: PyFSDMetarConfig
    logger: PyFSDLoggerConfig


class RootPyFSDConfig(TypedDict):
    """PyFSD root config."""

    pyfsd: PyFSDConfig
    plugin: NotRequired[dict]


logger = get_logger(__name__)

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
fetchers = ["NOAA"]

[pyfsd.logger.logger]
handlers = ["default"]
level = "DEBUG"
propagate = true

[pyfsd.logger.handlers.default]
level = "INFO"
class = "logging.StreamHandler"
formatter = "colored"
"""


async def launch(config: RootPyFSDConfig, wait_all_tasks_done: bool = True) -> None:
    """Launch PyFSD."""
    # =============== Initialize dependencies
    container = Container()
    container.config.from_dict(config)
    register_loader_containers(container)  # Register
    # Then load plugins to wire them
    pm = container.plugin_manager()
    pm.pick_plugins(config.get("plugin", {}))
    container.metar_manager().load_fetchers()
    # Initialize database
    async with container.db_engine().begin() as conn:
        await conn.run_sync(metadata.create_all)
    # =============== Load AwaitableMaker plugins
    awaitable_generators = []
    awaitables: List[Awaitable] = []
    for plugin in pm.get_plugins(AwaitableMaker):  # type: ignore[type-abstract]
        generator = plugin()
        awaitable = next(generator)
        if awaitable is not None:
            awaitables.append(awaitable)
        awaitable_generators.append(generator)
    # =============== Startup
    loop = get_event_loop()
    client_server = await loop.create_server(
        container.client_factory(), port=config["pyfsd"]["client"]["port"]
    )
    await container.plugin_manager().trigger_event("before_start", (), {})
    await logger.ainfo(f"PyFSD {version}")
    await logger.ainfo(f"{pm.plugins_count()} plugins: {pm!s}")
    tasks_pyfsd = (
        container.metar_manager().get_cron_task(),
        container.client_factory().get_heartbeat_task(),
        create_task(client_server.serve_forever()),
    )
    try:
        async with client_server:
            await gather(
                *tasks_pyfsd,
                *awaitables,
            )
    except CancelledError:
        # =========== Stop
        container.client_factory().remove_all_clients()
        await container.plugin_manager().trigger_event("before_stop", (), {})
        await logger.ainfo("Stopping")
        client_server.close()
        await client_server.wait_closed()
        for generator in awaitable_generators:
            try:  # noqa: SIM105
                next(generator)
            except StopIteration:
                pass
        for task in tasks_pyfsd:
            task.cancel()
        for task in task_keeper.tasks:
            task.cancel()

        tasks = all_tasks()
        tasks.discard(cast(Task, current_task()))
        if wait_all_tasks_done and tasks:
            total_wait_seconds = 0
            while True:
                total_wait_seconds += 5
                _, pending = await wait(tasks, timeout=5)
                if not pending:
                    break
                await logger.adebug(
                    "Waited %d second, but some tasks are still running: \n    %s",
                    total_wait_seconds,
                    "\n    ".join(str(task) for task in tasks),
                )
        await container.db_engine().dispose()


def main() -> None:
    """Main function of PyFSD."""
    parser = ArgumentParser()
    parser.add_argument(
        "-c",
        "--config-path",
        help="Path to the config file.",
        default="pyfsd.toml",
        type=str,
    )
    args = parser.parse_args()
    try:
        with open(args.config_path) as config_file:
            config = loads(config_file.read())
    except FileNotFoundError:
        with open(args.config_path, "w") as config_file:
            config_file.write(DEFAULT_CONFIG)
        config = loads(DEFAULT_CONFIG)

    assert_dict(
        config,
        RootPyFSDConfig,
        "config",
    )
    # Replace database scheme with async dialect
    db_url: str = config["pyfsd"]["database"]["url"]
    if "://" not in db_url:
        raise ValueError("Invalid database url")
    scheme, url = db_url.split("://", 1)
    if "+" not in scheme:  # if user didn't specified driver
        if scheme == "postgresql":
            db_url = "postgresql+asyncpg://" + url
        elif scheme in ("mysql", "mariadb"):
            db_url = "mysql+asyncmy://" + url
        elif scheme == "sqlite":
            db_url = "sqlite+aiosqlite://" + url
        elif scheme == "oracle":
            db_url = "oracle+oracledb_async://" + url
        elif scheme == "mssql":
            db_url = "mssql+aioodbc://" + url
        # else I have nothing to do :(
        config["pyfsd"]["database"]["url"] = db_url

    suppress_metar_parser_warning()
    setup_logger(config["pyfsd"]["logger"])

    loop = get_event_loop()

    def handle_main_task_finished(task: Task) -> None:
        try:
            task.result()
        except BaseException:
            logger.exception("Error happened when launching PyFSD")
        loop.stop()

    main_task = loop.create_task(launch(cast(RootPyFSDConfig, config)))
    main_task.add_done_callback(handle_main_task_finished)

    for signal in [SIGINT, SIGTERM, SIGHUP]:
        loop.add_signal_handler(signal, main_task.cancel)
    loop.run_forever()  # complete after loop.stop()
    loop.close()
