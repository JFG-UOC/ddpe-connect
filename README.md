# ddpe-connect

`ddpe-connect` is a small Python wrapper that creates an authenticated PySpark
`SparkSession` for Dell Data Processing Engine (DDPE). It obtains an access token
from Keycloak, configures Spark Connect TLS trust, and returns a normal
`pyspark.sql.SparkSession`.

```python
from ddpe.connect import DDPESession

spark = (
    DDPESession.builder
    .remote("spark-connect.example:443")
    .getOrCreate()
)
```

The library focuses on client connection setup. Catalogs, storage, the application
name, and server-side Spark extensions remain DDPE server responsibilities.
Supported client-visible Spark properties can be supplied with `.config()`, except
`spark.app.name`.

## Features

* Fluent `DDPESession.builder.getOrCreate()` API
* Keycloak resource-owner password grant
* Process-local, thread-safe token cache with expiry awareness
* Configuration through TOML, environment variables, or the builder
* Keycloak TLS verification using system trust or a custom CA bundle
* Custom CA support for the Spark Connect gRPC channel
* Direct access-token override for automation and testing
* Secret redaction from connection exceptions
* No import-time dependency on PySpark

## Requirements

* Python 3.11 or newer
* Git, when installing directly from GitHub
* A PySpark Connect client compatible with the DDPE Spark server
* Network access to Keycloak and the DDPE Spark Connect endpoint

The project installs `pyspark[connect]>=3.5,<4.0`. Pin the exact PySpark minor
version required by your DDPE environment in the consuming application.

## Installation from GitHub

The package is distributed from GitHub rather than a Python package index.
Install the latest code from the `main` branch:

```bash
python -m pip install "git+https://github.com/JFG-UOC/ddpe-connect.git@main"
```

For reproducible deployments, install a release tag:

```bash
python -m pip install "git+https://github.com/JFG-UOC/ddpe-connect.git@v0.1.0"
```

Upgrade an existing installation from GitHub:

```bash
python -m pip install --upgrade --force-reinstall \
  "git+https://github.com/JFG-UOC/ddpe-connect.git@main"
```

For a private repository, Git must already be authenticated with an account or
Personal Access Token that can read the repository.

### Corporate proxy certificates

When a corporate proxy intercepts TLS, configure Git with the corporate CA bundle:

```bash
git config --global http.sslCAInfo /path/to/corporate-proxy-ca.pem
```

On Git for Windows, use the Windows certificate store when the corporate CA is
already installed there:

```bash
git config --global http.sslBackend schannel
```

Avoid disabling certificate validation permanently.

## Installation from a local checkout

```bash
git clone https://github.com/JFG-UOC/ddpe-connect.git
cd ddpe-connect
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

For development:

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
python -m build
```

## Quick start

```bash
export DDPE_SPARK_CONNECT_URL="spark-connect.example:443"
export DDPE_SPARK_CONNECT_CA="/path/to/ddpe-spark-ca.pem"
export DDPE_KEYCLOAK_TOKEN_URL="https://keycloak.example/realms/ddpe/protocol/openid-connect/token"
export DDPE_OIDC_CLIENT_ID="ddpe-client"
export DDPE_OIDC_CLIENT_SECRET="..."
export DDPE_USERNAME="..."
export DDPE_PASSWORD="..."
```

```python
from ddpe.connect import DDPESession

spark = DDPESession.builder.getOrCreate()
spark.sql("SHOW DATABASES").show(truncate=False)
spark.stop()
```

## TOML configuration

The default configuration file is `~/.config/ddpe/config.toml`. The file itself
is optional, but the Spark Connect endpoint is mandatory. Supply it as
`DDPE_SPARK_CONNECT_URL`, as `spark_connect_url` in TOML, or through
`.remote(...)`. To select a different file, set `DDPE_CONFIG_FILE` or call
`.config_file(...)`.

```toml
[ddpe]
spark_connect_url = "spark-connect.example:443"
spark_connect_ca = "/path/to/ddpe-spark-ca.pem"

[ddpe.auth]
token_url = "https://keycloak.example/realms/ddpe/protocol/openid-connect/token"
client_id = "ddpe-client"
scope = "openid"
verify_ssl = true

[ddpe.spark]
"spark.sql.shuffle.partitions" = "16"
```

Keep secrets in environment variables rather than TOML:

```bash
export DDPE_OIDC_CLIENT_SECRET="..."
export DDPE_USERNAME="..."
export DDPE_PASSWORD="..."
```

Configuration precedence is:

1. Builder methods
2. Environment variables
3. TOML
4. Built-in defaults for optional settings

There is no built-in Spark Connect endpoint. The client raises a configuration
error before authentication unless the URL is supplied through the builder, the
environment, or TOML. The Keycloak token URL defaults to
`http://localhost:8080/realms/ddpe/protocol/openid-connect/token`, and the client
ID defaults to `ddpe-client`. User credentials default to empty values and must be
provided unless `DDPE_ACCESS_TOKEN` is set.

## Builder configuration

```python
import os
from ddpe.connect import DDPESession

spark = (
    DDPESession.builder
    .remote("spark-connect.example:443")
    .token_url("https://keycloak.example/realms/ddpe/protocol/openid-connect/token")
    .credentials(
        username=os.environ["DDPE_USERNAME"],
        password=os.environ["DDPE_PASSWORD"],
        client_id="ddpe-client",
        client_secret=os.environ.get("DDPE_OIDC_CLIENT_SECRET", ""),
    )
    .ca_cert("/path/to/ddpe-spark-ca.pem")
    .verify_ssl("/path/to/keycloak-ca.pem")
    .config("spark.sql.shuffle.partitions", 16)
    .getOrCreate()
)
```

## Environment variables

| Variable | Purpose |
|---|---|
| `DDPE_CONFIG_FILE` | Alternative TOML path |
| `DDPE_SPARK_CONNECT_URL` | Required Spark Connect `host[:port]` unless supplied by TOML or `.remote(...)` |
| `DDPE_SPARK_CONNECT_CA` | PEM CA file for Spark Connect gRPC |
| `DDPE_KEYCLOAK_TOKEN_URL` | Keycloak token endpoint |
| `DDPE_OIDC_CLIENT_ID` | OAuth client ID |
| `DDPE_OIDC_CLIENT_SECRET` | OAuth client secret, if required |
| `DDPE_USERNAME` | DDPE username |
| `DDPE_PASSWORD` | DDPE password |
| `DDPE_OIDC_SCOPE` | OAuth scope; defaults to `openid` |
| `DDPE_VERIFY_SSL` | `true`, `false`, or a Keycloak CA path |
| `DDPE_AUTH_TIMEOUT_SECONDS` | Keycloak request timeout |
| `DDPE_TOKEN_REFRESH_SKEW_SECONDS` | Refresh-before-expiry window |
| `DDPE_ACCESS_TOKEN` | Pre-issued token; bypasses Keycloak |

## TLS and security

For production:

* Keep `DDPE_VERIFY_SSL=true`, or set it to a trusted CA-bundle path.
* Set `DDPE_SPARK_CONNECT_CA` when the DDPE gRPC certificate is signed by a
  private CA. If omitted, gRPC uses the operating system trust roots.
* Keep passwords, client secrets, tokens, and private keys out of Git.
* Use `DDPE_VERIFY_SSL=false` only for a PoC or isolated development environment.
  This bypass applies only to the HTTPS call to Keycloak.

A bearer token causes Spark Connect to use TLS. Configure a CA file or use a
certificate trusted by the operating system for the Spark Connect endpoint.
Tokens are cached only in process memory and are never intentionally logged.

## Custom Spark configuration

```python
spark = (
    DDPESession.builder
    .remote("spark-connect.example:443")
    .config("spark.sql.defaultCatalog", "iceberg")
    .configs({
        "spark.sql.shuffle.partitions": "16",
        "spark.sql.session.timeZone": "UTC",
    })
    .getOrCreate()
)
```

## Error handling

```python
from ddpe.connect import DDPESession, DDPEError

try:
    spark = (
        DDPESession.builder
        .remote("spark-connect.example:443")
        .getOrCreate()
    )
except DDPEError as exc:
    print(f"DDPE connection failed: {exc}")
```

The package exposes configuration, authentication, dependency, and connection
subclasses under `DDPEError`.

## Development and validation

```bash
pytest --cov=ddpe.connect
ruff check .
python -m build
python -m pip install --force-reinstall dist/*.whl
```

The canonical repository is
[github.com/JFG-UOC/ddpe-connect](https://github.com/JFG-UOC/ddpe-connect).

## License

GNU General Public License v3.0 only (`GPL-3.0-only`). See [LICENSE](LICENSE).
