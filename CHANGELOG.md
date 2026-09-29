# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Changed

* Made the Spark Connect endpoint mandatory and removed its implicit local default.
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
