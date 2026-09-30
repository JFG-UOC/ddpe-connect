# Changelog

All notable changes to this project will be documented in this file.

## [0.1.2] - 2026-09-30

### Fixed

* Added Python 3.10 support through the conditional `tomli` dependency.
* Added `setup.cfg` and `setup.py` compatibility metadata for older pip/setuptools.
* Added an installation check that verifies the installed `ddpe.connect` version.

## [0.1.1] - 2026-09-29

### Changed

* Separated the Keycloak HTTPS CA from the Spark Connect gRPC CA.
* Added explicit `keycloak_ca_cert(...)` and `spark_ca_cert(...)` builder methods.
* Added `DDPE_KEYCLOAK_CA` while retaining legacy builder aliases.

* Documented installation and upgrades directly from the GitHub repository.
* Removed the unsupported client-side application-naming API from code and examples.
* Updated every file in `examples/` to rely on the server-managed application name.
* Rejected the unsupported `spark.app.name` client configuration.
* Changed the project license from MIT to GNU GPLv3 (`GPL-3.0-only`).

## [0.1.0] - 2026-09-29

### Added

* `ddpe.connect.DDPESession` builder API
* Keycloak password-grant authentication
* In-memory access-token caching
* TOML, environment, and builder configuration
* Keycloak and Spark Connect CA support
* Direct token override
* Tests, examples, packaging metadata, and CI
