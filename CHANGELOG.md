# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `pyfsd.*`: Add docstrings
- `pyfsd.dependensics`: Add dependency inject
- `tests/pyfsd.define.test_simuation`: Add `.simulation` test case

### Changed

- `pyfsd.*`: Use asyncio instead of Twisted
- `pyfsd.*`: use snake\_case instead of camelCase in function naming
- `pyfsd.define.{config_check => check_dict, packet, utils}`: Rewrite
- `pyfsd.{factory, protocol}.client`: Rewrite
- `pyfsd.factory.client`: Use argon2 encrypt (include failsafe support of sha256)
- `{twisted.plugins.pyfsd_launcher => pyfsd.main}`: Rewrite application entry
- `pyfsd.metar.{fetch, manager, service}`: Rewrite
- `pyfsd.plugin[.{collect, interfaces, manager, types}]`: Rewrite, use `abc` instead of `zope.interface`
- `pyfsd.plugins`: Use `pkgutil.extend_path`, change plugin directory to `pyfsd_plugins` 
- `pyfsd.protocol`: Add `LineReceiver`, `LineProtocol`
- `pyfsd.{setup_loguru => setup_logger}`: Use `structlog` instead of `loguru`
- `pyfsd.utils.import_users`: Rewrite
- `tests/pyfsd.define.test_{config_check => check_dict}`: Rewrite `.config_check` test case
- `tests/pyfsd.define.test_packet`: Rewrite `.packet` test case
- `tests/pyfsd.define.test_utils`: Rewrite `.utils` test case

### Removed

- `Twisted`, replaced by `asyncio`
- `constantly`, replaced by `enum`
- `zope.interface`, replaced by `abc`
- `pyfsd.define.config_check`, replaced by `.check_dict`
- `pyfsd.prompt`
- `pyfsd.service`
- `under_dev/`: Remove
