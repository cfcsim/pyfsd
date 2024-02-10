"""Run PyFSD."""
from argparse import ArgumentParser
from asyncio import CancelledError, ensure_future, gather, get_event_loop
from signal import SIGINT, SIGTERM
from typing import Literal, Union

from dependency_injector.wiring import register_loader_containers
from loguru import logger

from ._version import version
from .db_tables import metadata
from .define.check_dict import assert_dict
from .dependencies import Container
from .metar.manager import suppress_metar_parser_warning

try:
    # Python 3.11+
    from typing import NotRequired  # type: ignore[attr-defined]

    from tomllib import load
except ImportError:
    from tomli import load
    from typing_extensions import NotRequired


async def launch(config: dict) -> None:
    """Launch PyFSD."""
    container = Container()
    container.config.from_dict(config)
    register_loader_containers(container)  # Register
    # Then load plugins to load them
    container.pyfsd_plugin_manager().pick_plugins(config["plugin"])
    container.metar_manager().pick_fetchers()

    async with container.db_engine().begin() as conn:
        await conn.run_sync(metadata.create_all)

    loop = get_event_loop()
    client_server = await loop.create_server(
        container.client_factory(), port=config["pyfsd"]["client"]["port"]
    )
    tasks = (
        container.metar_manager().get_cron_task(),
        client_server.serve_forever(),
        container.client_factory().get_heartbeat_task(),
    )
    await container.pyfsd_plugin_manager().trigger_event("before_start", (), {})
    logger.info(f"PyFSD {version}")
    try:
        async with client_server:
            await gather(*tasks)
    except CancelledError:
        await container.pyfsd_plugin_manager().trigger_event("before_stop", (), {})
        await container.db_engine().dispose()
        logger.info("Stopping")


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
    with open(args.config_path, "rb") as config_file:
        config = load(config_file)
    assert_dict(
        config,
        {
            "pyfsd": {
                "database": {"url": str},
                "client": {
                    "port": int,
                    "motd": str,
                    "motd_encoding": str,
                    "blacklist": list,
                },
                "metar": {
                    "mode": Literal["cron", "once"],
                    "fallback_once": NotRequired[bool],
                    "fetchers": list,
                    "cron_time": NotRequired[Union[float, int]],
                },
            },
            "plugin": NotRequired[dict],
        },
        "config",
    )
    if "plugin" not in config:
        config["plugin"] = {}
    suppress_metar_parser_warning()
    loop = get_event_loop()
    main_task = ensure_future(launch(config))
    for signal in [SIGINT, SIGTERM]:
        loop.add_signal_handler(signal, main_task.cancel)
    loop.run_until_complete(main_task)
